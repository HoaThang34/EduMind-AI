"""Lightweight step recorder passed through the infer pipeline.

Mỗi bước được append vào list, kèm timestamp tương đối (ms) và status.
Frontend dùng list này để render timeline minh bạch quá trình AI xử lý.
"""
from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("pipeline")


class StepLogger:
    def __init__(self, run_id: str = "", on_log=None):
        self.run_id = run_id
        self._t0 = time.time()
        self.steps: list[dict[str, Any]] = []
        self._on_log = on_log  # callable(entry) - gọi ngay khi có step mới (để stream realtime)

    def _now_ms(self) -> int:
        return int((time.time() - self._t0) * 1000)

    def log(
        self,
        step: str,
        status: str = "info",
        detail: str = "",
        meta: dict | None = None,
    ) -> None:
        entry = {
            "t_ms": self._now_ms(),
            "step": step,
            "status": status,  # info | ok | warn | error | start | end
            "detail": detail,
            "meta": meta or {},
        }
        self.steps.append(entry)
        log.info("[%s] %s %s %s", self.run_id or "-", step, status, detail)
        if self._on_log is not None:
            try:
                self._on_log(entry)
            except Exception as e:
                log.warning("on_log callback failed: %s", e)

    def done(self, step: str, detail: str = "", meta: dict | None = None) -> None:
        self.log(step, status="ok", detail=detail, meta=meta)

    def warn(self, step: str, detail: str = "", meta: dict | None = None) -> None:
        self.log(step, status="warn", detail=detail, meta=meta)

    def error(self, step: str, detail: str = "", meta: dict | None = None) -> None:
        self.log(step, status="error", detail=detail, meta=meta)

    def total_ms(self) -> int:
        return self._now_ms()
