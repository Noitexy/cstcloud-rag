from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.document_parser import ParsedSection


@dataclass(slots=True)
class TextChunk:
    content: str
    index: int
    page: int | None
    section_title: str | None


class SemanticTextSplitter:
    """Heading/paragraph-aware splitter with sentence fallback and controlled overlap."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120) -> None:
        if chunk_size < 1 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("切片参数无效")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, sections: list[ParsedSection]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for section in sections:
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n|(?=^#{1,6}\s)", section.text, flags=re.MULTILINE) if part.strip()]
            buffer = ""
            for paragraph in paragraphs:
                units = self._split_long(paragraph)
                for unit in units:
                    candidate = f"{buffer}\n\n{unit}".strip() if buffer else unit
                    if len(candidate) <= self.chunk_size:
                        buffer = candidate
                    else:
                        if buffer:
                            chunks.append(self._make_chunk(buffer, len(chunks), section))
                            overlap = self._tail(buffer)
                            combined = f"{overlap}\n{unit}".strip() if overlap else unit
                            # A full-size semantic unit takes priority over overlap.
                            buffer = combined if len(combined) <= self.chunk_size else unit
                        else:
                            chunks.append(self._make_chunk(unit, len(chunks), section))
                            buffer = ""
            if buffer:
                chunks.append(self._make_chunk(buffer, len(chunks), section))
        return chunks

    def _split_long(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]
        sentences = [part.strip() for part in re.split(r"(?<=[。！？!?；;\.])", text) if part.strip()]
        result: list[str] = []
        current = ""
        for sentence in sentences:
            if len(sentence) > self.chunk_size:
                if current:
                    result.append(current)
                    current = ""
                step = self.chunk_size - self.chunk_overlap
                result.extend(sentence[start : start + self.chunk_size] for start in range(0, len(sentence), step))
            elif len(current) + len(sentence) <= self.chunk_size:
                current += sentence
            else:
                result.append(current)
                overlap = self._tail(current)
                combined = overlap + sentence
                current = combined if len(combined) <= self.chunk_size else sentence
        if current:
            result.append(current)
        return result

    def _tail(self, text: str) -> str:
        return text[-self.chunk_overlap :] if self.chunk_overlap else ""

    @staticmethod
    def _make_chunk(text: str, index: int, section: ParsedSection) -> TextChunk:
        return TextChunk(text.strip(), index, section.page, section.section_title)
