"""PDF reading module with pdfplumber as primary and PyMuPDF as fallback.

Each pdfplumber table is emitted as a separate group of rows so the parser
can treat each table as one product block.
"""

import logging
from pathlib import Path
from typing import Optional

import pdfplumber
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

TABLE_BOUNDARY = "__TABLE_BOUNDARY__"


def read_with_pdfplumber(pdf_path: str) -> Optional[list[dict]]:
    """Extract data from PDF using pdfplumber, preserving table boundaries."""
    results = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                logger.info(f"pdfplumber: processing page {page_num}/{len(pdf.pages)}")

                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        # Insert a boundary marker so the parser knows where each table starts
                        results.append({
                            "source": "boundary",
                            "page": page_num,
                            "cells": [],
                            "raw": TABLE_BOUNDARY,
                        })
                        for row in table:
                            if row:
                                results.append({
                                    "source": "table",
                                    "page": page_num,
                                    "cells": [str(c).strip() if c else "" for c in row],
                                    "raw": " ".join(str(c).strip() for c in row if c),
                                })
                else:
                    text = page.extract_text()
                    if text:
                        for line in text.split("\n"):
                            line = line.strip()
                            if line:
                                results.append({
                                    "source": "text",
                                    "page": page_num,
                                    "cells": [],
                                    "raw": line,
                                })
        if results:
            return results
    except Exception as e:
        logger.warning(f"pdfplumber failed: {e}")
    return None


def read_with_pymupdf(pdf_path: str) -> Optional[list[dict]]:
    """Fallback: extract text lines using PyMuPDF."""
    results = []
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc, start=1):
            logger.info(f"PyMuPDF: processing page {page_num}/{len(doc)}")
            text = page.get_text()
            if text:
                for line in text.split("\n"):
                    line = line.strip()
                    if line:
                        results.append({
                            "source": "text",
                            "page": page_num,
                            "cells": [],
                            "raw": line,
                        })
        doc.close()
        if results:
            return results
    except Exception as e:
        logger.warning(f"PyMuPDF failed: {e}")
    return None


def read_pdf_text_only(pdf_path: str) -> list[dict]:
    """Extract pure text lines (no table detection) using PyMuPDF.

    Better for text-heavy PDFs like Makro pamphlets where pdfplumber's
    table detection fragments the content.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info(f"Reading PDF (text-only mode): {path.name}")
    data = read_with_pymupdf(pdf_path)
    if data:
        logger.info(f"Text-only extracted {len(data)} rows")
        return data

    raise RuntimeError(f"Failed to extract text from {pdf_path}")


def read_pdf(pdf_path: str, mode: str = "tables") -> list[dict]:
    """Read a PDF file.

    Args:
        mode: "tables" — pdfplumber tables first, PyMuPDF fallback (good for Ultra Liquors)
              "text"   — pure text extraction via PyMuPDF (good for Makro)
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path}")

    if mode == "text":
        return read_pdf_text_only(pdf_path)

    logger.info(f"Reading PDF: {path.name}")

    data = read_with_pdfplumber(pdf_path)
    if data:
        logger.info(f"pdfplumber extracted {len(data)} rows")
        return data

    logger.info("Falling back to PyMuPDF...")
    data = read_with_pymupdf(pdf_path)
    if data:
        logger.info(f"PyMuPDF extracted {len(data)} rows")
        return data

    raise RuntimeError(f"Both parsers failed to extract data from {pdf_path}")
