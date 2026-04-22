import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    FLASK_SECRET = os.getenv("FLASK_SECRET", "dev-secret")

    # VLM provider: "gemini" hoặc "openai". Chuyển qua lại để né 503 của Gemini.
    VLM_PROVIDER = os.getenv("VLM_PROVIDER", "gemini").strip().lower()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_VLM_MODEL = os.getenv("OPENAI_VLM_MODEL", "gpt-4o-mini")
    OPENAI_REASONING_MODEL = os.getenv("OPENAI_REASONING_MODEL", "gpt-5.4")
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "error_library")
    EMBEDDING_DIM = 1536

    DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "demo.db"))
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "data", "uploads"))

    # on_uncertain | always | off
    REASONING_MODE = os.getenv("REASONING_MODE", "on_uncertain")

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
