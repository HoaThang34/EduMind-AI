# Demo OCR Adaptive System

Demo Challenge 1: OCR viết tay (toán / sơ đồ / text) + Active Learning vòng kín.

## Kiến trúc

- **VLM (Gemini 3.0 Flash)**: đọc ảnh → JSON (text/latex/graph) kèm `notes` và `conditions`.
- **Reasoning Agent (GPT-5.4)**: xét output, gọi tool khi cần.
- **Tools**:
  - `error_library_lookup` — retrieval từ Qdrant (text embedding).
  - `validate_latex` / `validate_graph` — rule-based.
- **Correction Store (SQLite)**: lưu diff + rule rút ra từ bản sửa của giáo viên.
- **Feedback loop**: rule + exemplar được inject vào prompt lần sau → đo v1 vs v2 trên cùng ảnh.

## Chạy

```bash
cp .env.example .env   # điền GEMINI_API_KEY + OPENAI_API_KEY
docker compose up -d --build
# mở http://localhost:8985
```

## Demo flow

1. Upload ảnh viết tay.
2. Xem output v1 (chưa có rule).
3. Sửa inline → submit.
4. Hệ thống tự diff → lưu correction → rút rule → upsert Qdrant.
5. Bấm "Chạy lại trên cùng ảnh" → v2 có rule + exemplar → so sánh.
