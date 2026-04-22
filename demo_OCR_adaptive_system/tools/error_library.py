"""Error Library tool backed by Qdrant.

Lưu mỗi rule như 1 point với vector = embedding(rule_text + error_tag + content_type).
Payload chứa rule metadata + exemplar (corrected_output).
"""

import uuid
import logging
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from openai import OpenAI

from config import Config

log = logging.getLogger(__name__)

_qdrant: QdrantClient | None = None
_openai: OpenAI | None = None


def _q() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=Config.QDRANT_URL, timeout=10)
    return _qdrant


def _oai() -> OpenAI:
    global _openai
    if _openai is None:
        _openai = OpenAI(api_key=Config.OPENAI_API_KEY)
    return _openai


def ensure_collection():
    client = _q()
    existing = {c.name for c in client.get_collections().collections}
    if Config.QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=Config.QDRANT_COLLECTION,
            vectors_config=qm.VectorParams(size=Config.EMBEDDING_DIM, distance=qm.Distance.COSINE),
        )
        log.info("Created Qdrant collection %s", Config.QDRANT_COLLECTION)


def embed(text: str) -> List[float]:
    resp = _oai().embeddings.create(model=Config.OPENAI_EMBEDDING_MODEL, input=text)
    return resp.data[0].embedding


def upsert_rule(
    rule_text: str,
    error_tag: str,
    content_type: str,
    exemplar: Optional[Dict[str, Any]] = None,
    rule_db_id: Optional[int] = None,
) -> str:
    ensure_collection()
    point_id = str(uuid.uuid4())
    content = f"[{content_type}][{error_tag}] {rule_text}"
    vector = embed(content)
    payload = {
        "rule_text": rule_text,
        "error_tag": error_tag,
        "content_type": content_type,
        "exemplar": exemplar or {},
        "rule_db_id": rule_db_id,
    }
    _q().upsert(
        collection_name=Config.QDRANT_COLLECTION,
        points=[qm.PointStruct(id=point_id, vector=vector, payload=payload)],
    )
    return point_id


def search_rules(
    query_text: str,
    content_type: Optional[str] = None,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    ensure_collection()
    vector = embed(query_text)
    query_filter = None
    if content_type:
        query_filter = qm.Filter(
            must=[qm.FieldCondition(key="content_type", match=qm.MatchValue(value=content_type))]
        )
    # qdrant-client >=1.14 bỏ .search(), dùng .query_points() trả về QueryResponse.points
    resp = _q().query_points(
        collection_name=Config.QDRANT_COLLECTION,
        query=vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "point_id": str(r.id),
            "score": float(r.score),
            "rule_text": r.payload.get("rule_text"),
            "error_tag": r.payload.get("error_tag"),
            "content_type": r.payload.get("content_type"),
            "exemplar": r.payload.get("exemplar") or {},
            "rule_db_id": r.payload.get("rule_db_id"),
        }
        for r in resp.points
    ]


def count_rules() -> int:
    ensure_collection()
    info = _q().get_collection(Config.QDRANT_COLLECTION)
    return info.points_count or 0


def delete_points(point_ids: List[str]) -> int:
    """Xoá 1 số point cụ thể theo id (uuid string). Trả số id truyền vào."""
    if not point_ids:
        return 0
    ensure_collection()
    _q().delete(
        collection_name=Config.QDRANT_COLLECTION,
        points_selector=qm.PointIdsList(points=point_ids),
    )
    return len(point_ids)


def delete_all() -> int:
    """Xoá sạch collection rồi tạo lại. Trả về số point đã xoá."""
    try:
        n = count_rules()
    except Exception:
        n = 0
    try:
        _q().delete_collection(collection_name=Config.QDRANT_COLLECTION)
    except Exception as e:
        log.warning("delete_collection failed (maybe not exist): %s", e)
    ensure_collection()
    return n
