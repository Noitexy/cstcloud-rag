"""Reserved DeepSeek-OCR integration boundary.

The current release uses pypdf for text PDFs. Scanned PDFs fail with an explicit
message; this service can later implement /deepseek-ocr/convert and status polling
without changing the ingestion API.
"""


class DeepSeekOCRService:
    async def submit_pdf(self, *_: object, **__: object) -> str:
        raise NotImplementedError("DeepSeek-OCR 扩展尚未启用")
