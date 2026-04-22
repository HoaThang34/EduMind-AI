"""Exceptions dùng chung cho pipeline."""


class PipelineAbort(Exception):
    """Lỗi khiến pipeline dừng ngay (VLM 503/401, OpenAI auth, ...).

    Mang theo step_name để frontend hiển thị đúng bước fail.
    """

    def __init__(self, step: str, message: str, status_code: int | None = None):
        self.step = step
        self.status_code = status_code
        super().__init__(message)
