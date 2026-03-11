from __future__ import annotations

from pathlib import Path

from anyq.parsers.docx import DOCXParser
from anyq.parsers.pdf import PDFParser
from anyq.parsers.txt import TXTParser

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class ParserFactory:
    @staticmethod
    def get(filename: str) -> PDFParser | DOCXParser | TXTParser:
        ext = Path(filename).suffix.lower()
        match ext:
            case ".pdf":
                return PDFParser()
            case ".docx":
                return DOCXParser()
            case ".txt":
                return TXTParser()
            case ".doc":
                raise NotImplementedError(
                    "DOC format requires LibreOffice conversion. "
                    "Please convert to DOCX or PDF first."
                )
            case _:
                raise ValueError(
                    f"Unsupported file format: {ext!r}. "
                    f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
                )
