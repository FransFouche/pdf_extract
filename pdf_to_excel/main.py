"""PDF-to-Excel price extractor — CLI entry point.

Usage:
    python main.py <path-to-pdf>                        # auto-detect source
    python main.py <path-to-pdf> --source ultra         # Ultra Liquors format
    python main.py <path-to-pdf> --source makro         # Makro format
    python main.py                                      # auto-find PDF in parent folder
"""

import argparse
import logging
import sys
from pathlib import Path

from extractor.pdf_reader import read_pdf
from extractor.price_parser import extract_prices as extract_ultra
from extractor.makro_parser import extract_prices as extract_makro
from utils.cleaner import clean
from output.writer import write_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SOURCE_CONFIG = {
    "ultra": {"parser": extract_ultra, "read_mode": "tables"},
    "makro": {"parser": extract_makro, "read_mode": "text"},
}


def detect_source(pdf_path: str) -> str:
    """Auto-detect PDF source based on filename or content hints."""
    name = Path(pdf_path).name.lower()
    if "makro" in name:
        return "makro"
    if "broadsheet" in name or "ultra" in name:
        return "ultra"

    # Peek at text content for clues
    try:
        raw_rows = read_pdf(pdf_path)
        text_blob = " ".join(r["raw"] for r in raw_rows[:50]).lower()
        if "makro" in text_blob or "massmart" in text_blob:
            return "makro"
        if "ultraliquors" in text_blob or "ultra liquors" in text_blob:
            return "ultra"
    except Exception:
        pass

    return "ultra"  # default fallback


def find_pdf_in_parent() -> str:
    parent = Path(__file__).resolve().parent.parent
    pdfs = sorted(parent.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(
            f"No PDF files found in {parent}. Pass a path explicitly."
        )
    logger.info(f"Auto-detected PDF: {pdfs[0].name}")
    return str(pdfs[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract prices from PDF pamphlets to Excel")
    parser.add_argument("pdf", nargs="?", default=None, help="Path to PDF file")
    parser.add_argument(
        "--source", "-s",
        choices=["ultra", "makro", "auto"],
        default="auto",
        help="PDF source format: ultra (Ultra Liquors), makro (Makro), or auto-detect (default)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  PDF Price Extractor")
    print("=" * 60)

    pdf_path = args.pdf or find_pdf_in_parent()

    source = args.source
    if source == "auto":
        source = detect_source(pdf_path)
        logger.info(f"Auto-detected source: {source}")
    else:
        logger.info(f"Source: {source}")

    config = SOURCE_CONFIG[source]

    logger.info(f"[1/4] Reading PDF: {Path(pdf_path).name}")
    raw_rows = read_pdf(pdf_path, mode=config["read_mode"])
    logger.info(f"       -> {len(raw_rows)} raw rows extracted")

    logger.info("[2/4] Parsing prices...")
    items = config["parser"](raw_rows)
    logger.info(f"       -> {len(items)} item-price pairs found")

    logger.info("[3/4] Cleaning data...")
    items = clean(items)
    logger.info(f"       -> {len(items)} rows after cleaning")

    if not items:
        logger.warning("No items found — nothing to write.")
        sys.exit(1)

    output_dir = Path(__file__).resolve().parent / "output"
    stem = Path(pdf_path).stem.replace(" ", "_")
    output_file = output_dir / f"{stem}.xlsx"
    logger.info(f"[4/4] Writing Excel: {output_file}")
    final_path = write_excel(items, str(output_file))

    print()
    print(f"Done!  {len(items)} items written to:")
    print(f"  {final_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
