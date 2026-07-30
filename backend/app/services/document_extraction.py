"""
Text extraction for supporting documents uploaded during ingestion
(architecture doc Section 3.1's `documents` table, Implementation Plan
Phase 3: "multipart upload -> documents row, text extraction
(pdf/docx/txt/md), folds extracted_text into project_idea.raw").

Kept dependency-light and hackathon-pragmatic: pypdf for PDFs (text
layer only, no OCR), python-docx for .docx, plain decode for txt/md.
A file that fails to parse (e.g. a scanned/image-only PDF) degrades to
an empty string rather than raising -- the upload still succeeds and
the byte count is still reported.
"""

from __future__ import annotations

import io
import logging

import docx as python_docx
from pypdf import PdfReader

logger = logging.getLogger(__name__)

SUPPORTED_DOCUMENT_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "md",
}


def extract_text(raw: bytes, content_type: str) -> str:
    """Best-effort text extraction. Never raises -- returns "" on
    failure so the caller can still record the upload."""
    kind = SUPPORTED_DOCUMENT_MIME_TYPES.get(content_type)
    try:
        if kind in ("txt", "md"):
            return raw.decode("utf-8", errors="replace")
        if kind == "pdf":
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if kind == "docx":
            document = python_docx.Document(io.BytesIO(raw))
            return "\n".join(p.text for p in document.paragraphs).strip()
    except Exception:
        logger.exception("document_text_extraction_failed", extra={"content_type": content_type})
        return ""
    return ""
