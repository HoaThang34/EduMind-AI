import hashlib
import json
import logging
import os
import time
from pathlib import Path
from queue import Queue, Empty
from threading import Thread

from flask import Flask, Response, render_template, request, jsonify, send_from_directory, abort, stream_with_context

from config import Config
from db import (
    init_db,
    log_inference,
    save_correction,
    save_rule,
    list_rules,
    delete_all_rules,
    delete_rules_by_ids,
    list_corrections,
    list_inferences_by_hash,
    stats_summary,
    get_inference,
)
from agents import vlm as vlm_agent
from agents import reasoning as reasoning_agent
from agents import rule_extractor
from tools import validator as val_mod
from tools import error_library
from tools import differ
from tools.step_logger import StepLogger
from tools.errors import PipelineAbort

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = Config.FLASK_SECRET
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15MB

init_db()
try:
    error_library.ensure_collection()
except Exception as e:
    log.warning("Qdrant not ready yet: %s", e)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _save_upload(image_bytes: bytes, filename: str) -> tuple[str, str]:
    h = _hash_bytes(image_bytes)
    ext = os.path.splitext(filename or "")[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    path = os.path.join(Config.UPLOAD_DIR, f"{h}{ext}")
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(image_bytes)
    return h, path


def _infer_once(
    image_bytes: bytes,
    mime: str,
    image_hash: str,
    image_path: str,
    version_label: str,
    use_library: bool,
    steps: StepLogger | None = None,
) -> dict:
    if steps is None:
        steps = StepLogger(run_id=image_hash)
    steps.log(
        "pipeline.start",
        status="start",
        detail=f"hash={image_hash} · version={version_label} · use_library={use_library}",
        meta={"version": version_label, "use_library": use_library},
    )

    try:
        return _run_pipeline(
            image_bytes, mime, image_hash, image_path, version_label, use_library, steps
        )
    except PipelineAbort as e:
        steps.error(
            "pipeline.abort",
            detail=f"[{e.step}] {e} (status={e.status_code})",
            meta={"step": e.step, "status_code": e.status_code, "total_ms": steps.total_ms()},
        )
        raise


def _run_pipeline(
    image_bytes: bytes,
    mime: str,
    image_hash: str,
    image_path: str,
    version_label: str,
    use_library: bool,
    steps: StepLogger,
) -> dict:
    rules_ctx = []
    exemplars_ctx = []
    used_rule_point_ids: list[str] = []
    used_exemplar_ids: list[int] = []

    if use_library:
        steps.log("library.retrieve", status="start", detail="Qdrant top-k=3")
        try:
            hits = error_library.search_rules(
                query_text="ảnh viết tay học sinh cần nhận diện",
                content_type=None,
                top_k=3,
            )
            rules_ctx = [
                {"error_tag": h["error_tag"], "rule_text": h["rule_text"]} for h in hits
            ]
            exemplars_ctx = [h.get("exemplar") for h in hits if h.get("exemplar")]
            used_rule_point_ids = [h["point_id"] for h in hits]
            tags_preview = ", ".join([h["error_tag"] for h in hits]) or "(không có rule)"
            steps.done(
                "library.retrieve",
                detail=f"{len(hits)} rule · {tags_preview}",
                meta={"n_hits": len(hits), "tags": [h["error_tag"] for h in hits]},
            )
        except Exception as e:
            log.warning("Library lookup skipped: %s", e)
            steps.warn("library.retrieve", detail=f"skip: {type(e).__name__}: {e}")
    else:
        steps.log("library.retrieve", status="info", detail="bỏ qua (mode fresh)")

    vlm_out = vlm_agent.read_image(
        image_bytes=image_bytes,
        mime_type=mime,
        rules=rules_ctx,
        exemplars=exemplars_ctx,
        logger=steps,
    )

    ok, reason = val_mod.validate_output(vlm_out)
    steps.log(
        "validator.run",
        status="ok" if ok else "warn",
        detail=f"{'pass' if ok else reason}",
        meta={"pass": ok, "reason": reason},
    )

    reasoning_verdict = None
    if Config.REASONING_MODE != "off":
        trigger = (
            Config.REASONING_MODE == "always"
            or not ok
            or (vlm_out.get("self_confidence") or 0) < 0.7
            or "ok" not in (vlm_out.get("conditions") or [])
        )
        if trigger:
            steps.log(
                "reasoning.trigger",
                status="info",
                detail=(
                    f"validator_pass={ok} · conf={vlm_out.get('self_confidence')} · "
                    f"conditions={vlm_out.get('conditions') or []}"
                ),
            )
            reasoning_verdict = reasoning_agent.review(
                vlm_output=vlm_out,
                validator_pass=ok,
                validator_reason=reason,
                logger=steps,
            )
            if reasoning_verdict.get("verdict") == "reprompt_vlm":
                extra = reasoning_verdict.get("additional_context") or ""
                steps.log(
                    "vlm.reprompt",
                    status="start",
                    detail=f"additional_context={len(extra)} ký tự",
                )
                vlm_out = vlm_agent.read_image(
                    image_bytes=image_bytes,
                    mime_type=mime,
                    rules=rules_ctx,
                    exemplars=exemplars_ctx,
                    extra_instruction=extra,
                    logger=steps,
                )
                ok, reason = val_mod.validate_output(vlm_out)
                steps.log(
                    "validator.rerun",
                    status="ok" if ok else "warn",
                    detail=f"{'pass' if ok else reason}",
                )
            used_rule_point_ids += reasoning_verdict.get("used_rule_ids") or []
        else:
            steps.log(
                "reasoning.skip",
                status="info",
                detail="validator pass + confidence cao → không cần reasoning",
            )

    inf_id = log_inference(
        image_hash=image_hash,
        image_path=image_path,
        version=version_label,
        content_type=vlm_out.get("type"),
        vlm_output=vlm_out,
        notes=vlm_out.get("notes") or "",
        conditions=vlm_out.get("conditions") or [],
        used_rules=list(dict.fromkeys(used_rule_point_ids)),
        used_exemplars=used_exemplar_ids,
        validator_pass=ok,
        validator_reason=reason,
    )
    steps.done(
        "pipeline.end",
        detail=f"inference_id={inf_id} · total={steps.total_ms()} ms",
        meta={"inference_id": inf_id, "total_ms": steps.total_ms()},
    )

    return {
        "inference_id": inf_id,
        "version": version_label,
        "image_hash": image_hash,
        "output": vlm_out,
        "validator": {"pass": ok, "reason": reason},
        "reasoning": reasoning_verdict,
        "used_rules": rules_ctx,
        "steps": steps.steps,
        "total_ms": steps.total_ms(),
    }


@app.route("/")
def index():
    stats = stats_summary()
    return render_template("ocr_demo.html", stats=stats)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    safe = Path(Config.UPLOAD_DIR).resolve()
    target = (safe / filename).resolve()
    if not str(target).startswith(str(safe)):
        abort(404)
    return send_from_directory(Config.UPLOAD_DIR, filename)


def _parse_infer_request():
    """Extract ảnh + mode + tính version/use_library. Dùng chung cho cả stream & non-stream."""
    f = request.files.get("image")
    if not f:
        return None, jsonify({"error": "missing_image"}), 400
    mode = request.form.get("mode", "auto")
    data = f.read()
    mime = f.mimetype or "image/jpeg"
    h, path = _save_upload(data, f.filename or "upload.jpg")
    prev = list_inferences_by_hash(h, limit=20)
    use_library = (mode != "fresh") and (mode == "with_library" or len(prev) > 0)
    version = f"v{len(prev) + 1}"
    return {
        "data": data, "mime": mime, "hash": h, "path": path,
        "version": version, "use_library": use_library,
    }, None, None


@app.post("/api/infer")
def api_infer():
    parsed, err, code = _parse_infer_request()
    if err is not None:
        return err, code
    try:
        result = _infer_once(
            image_bytes=parsed["data"],
            mime=parsed["mime"],
            image_hash=parsed["hash"],
            image_path=parsed["path"],
            version_label=parsed["version"],
            use_library=parsed["use_library"],
        )
    except PipelineAbort as e:
        return jsonify({
            "error": "pipeline_abort",
            "step": e.step,
            "status_code": e.status_code,
            "detail": str(e),
        }), 502
    result["image_url"] = f"/uploads/{os.path.basename(parsed['path'])}"
    result["use_library"] = parsed["use_library"]
    return jsonify(result)


@app.post("/api/infer_stream")
def api_infer_stream():
    """Stream NDJSON: mỗi dòng 1 event {type: step|result|error, ...}.
    Trả về realtime — step nào xong là client thấy ngay, không chờ toàn bộ pipeline.
    """
    parsed, err, code = _parse_infer_request()
    if err is not None:
        return err, code

    q: Queue = Queue()
    result_holder: dict = {}

    def on_log(entry):
        q.put(("step", entry))

    steps_logger = StepLogger(run_id=parsed["hash"], on_log=on_log)

    def worker():
        try:
            result = _infer_once(
                image_bytes=parsed["data"],
                mime=parsed["mime"],
                image_hash=parsed["hash"],
                image_path=parsed["path"],
                version_label=parsed["version"],
                use_library=parsed["use_library"],
                steps=steps_logger,
            )
            result["image_url"] = f"/uploads/{os.path.basename(parsed['path'])}"
            result["use_library"] = parsed["use_library"]
            # Bỏ trùng: frontend đã nhận từng step qua stream rồi
            result.pop("steps", None)
            result_holder["result"] = result
        except PipelineAbort as e:
            log.warning("Pipeline aborted at %s: %s", e.step, e)
            result_holder["error"] = {
                "kind": "pipeline_abort",
                "step": e.step,
                "status_code": e.status_code,
                "detail": str(e),
            }
        except Exception as e:
            log.exception("infer_stream worker failed")
            result_holder["error"] = {
                "kind": type(e).__name__,
                "detail": str(e),
            }
        finally:
            q.put(("done", None))

    Thread(target=worker, daemon=True).start()

    @stream_with_context
    def generate():
        # Flush ngay 1 dòng để client mở stream sớm (tránh proxy buffering)
        yield json.dumps({"type": "open", "hash": parsed["hash"]}, ensure_ascii=False) + "\n"
        while True:
            try:
                kind, payload = q.get(timeout=120)
            except Empty:
                yield json.dumps({"type": "timeout"}) + "\n"
                return
            if kind == "done":
                break
            yield json.dumps({"type": "step", "data": payload}, ensure_ascii=False) + "\n"
        if "error" in result_holder:
            yield json.dumps({"type": "error", **result_holder["error"]}, ensure_ascii=False) + "\n"
        else:
            yield json.dumps({"type": "result", "data": result_holder.get("result", {})}, ensure_ascii=False) + "\n"

    return Response(
        generate(),
        mimetype="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@app.post("/api/correction")
def api_correction():
    body = request.get_json(silent=True) or {}
    inference_id = body.get("inference_id")
    corrected = body.get("corrected")
    teacher_note = body.get("teacher_note", "")
    if not inference_id or not isinstance(corrected, dict):
        return jsonify({"error": "invalid_payload"}), 400

    inf = get_inference(int(inference_id))
    if not inf:
        return jsonify({"error": "inference_not_found"}), 404

    vlm_output = json.loads(inf["vlm_output"])
    content_type = corrected.get("type") or vlm_output.get("type") or inf.get("content_type") or "text"

    diff_info = differ.diff_and_tag(vlm_output, corrected)
    corr_id = save_correction(
        inference_id=int(inference_id),
        image_hash=inf["image_hash"],
        image_path=inf["image_path"],
        content_type=content_type,
        vlm_output=vlm_output,
        corrected_output=corrected,
        diff_summary=diff_info["summary"],
        error_tags=diff_info["error_tags"],
        teacher_note=teacher_note,
    )

    # rút rule bằng LLM
    rule_obj = rule_extractor.extract_rule(
        content_type=content_type,
        error_tags=diff_info["error_tags"],
        diff_summary=diff_info["summary"],
    )

    rule_saved = None
    if rule_obj.get("rule_text") and rule_obj.get("confidence", 0) >= 0.3:
        tag = diff_info["error_tags"][0] if diff_info["error_tags"] else "generic"
        try:
            point_id = error_library.upsert_rule(
                rule_text=rule_obj["rule_text"],
                error_tag=tag,
                content_type=content_type,
                exemplar={
                    "before": vlm_output,
                    "after": corrected,
                    "teacher_note": teacher_note,
                },
            )
            rule_db_id = save_rule(
                qdrant_point_id=point_id,
                content_type=content_type,
                error_tag=tag,
                rule_text=rule_obj["rule_text"],
                source_correction_ids=[corr_id],
            )
            rule_saved = {
                "id": rule_db_id,
                "point_id": point_id,
                "rule_text": rule_obj["rule_text"],
                "error_tag": tag,
            }
        except Exception as e:
            log.exception("Upsert rule failed: %s", e)

    return jsonify(
        {
            "correction_id": corr_id,
            "diff": diff_info,
            "rule": rule_saved,
        }
    )


@app.get("/api/rules")
def api_rules():
    return jsonify({"rules": list_rules(limit=100)})


@app.delete("/api/rules")
def api_rules_clear():
    """Xoá rules: nếu body có ids=[...] → xoá đúng các id đó, không thì xoá toàn bộ."""
    body = request.get_json(silent=True) or {}
    ids = body.get("ids")
    if isinstance(ids, list) and ids:
        try:
            id_ints = [int(x) for x in ids]
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_ids"}), 400
        n_sql, point_ids = delete_rules_by_ids(id_ints)
        n_qdrant = 0
        try:
            n_qdrant = error_library.delete_points(point_ids)
        except Exception as e:
            log.warning("Qdrant delete_points failed: %s", e)
        return jsonify({
            "ok": True, "mode": "selected",
            "qdrant_deleted": n_qdrant, "sqlite_deleted": n_sql,
        })
    n_qdrant = error_library.delete_all()
    n_sql = delete_all_rules()
    return jsonify({
        "ok": True, "mode": "all",
        "qdrant_deleted": n_qdrant, "sqlite_deleted": n_sql,
    })


@app.get("/api/stats")
def api_stats():
    s = stats_summary()
    try:
        s["qdrant_points"] = error_library.count_rules()
    except Exception:
        s["qdrant_points"] = None
    return jsonify(s)


@app.get("/api/history/<image_hash>")
def api_history(image_hash: str):
    inferences = list_inferences_by_hash(image_hash, limit=50)
    corrections = list_corrections(image_hash, limit=50)
    return jsonify({"inferences": inferences, "corrections": corrections})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8985, debug=True)
