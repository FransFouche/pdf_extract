import io
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from extractor.pdf_reader import read_pdf
from extractor.price_parser import extract_prices as extract_ultra
from extractor.makro_parser import extract_prices as extract_makro
from utils.cleaner import clean


SOURCE_CONFIG = {
    "ultra": {"parser": extract_ultra, "read_mode": "tables"},
    "makro": {"parser": extract_makro, "read_mode": "text"},
}


def detect_source_from_name(name: str) -> str:
    n = name.lower()
    if "makro" in n:
        return "makro"
    if "broadsheet" in n or "ultra" in n:
        return "ultra"
    return "ultra"


def records_to_xlsx_bytes(records: list[dict]) -> bytes:
    df = pd.DataFrame(records)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Prices")
    return output.getvalue()


st.set_page_config(page_title="PDF Price Extractor", layout="centered")
st.title("PDF Price Extractor")
st.caption("Upload a PDF, extract item descriptions and prices, download Excel.")

uploaded = st.file_uploader("Upload PDF", type=["pdf"])
source = st.selectbox(
    "Source format",
    options=["auto", "ultra", "makro"],
    help="Use auto unless you know the PDF format.",
)

if uploaded is not None:
    suggested = detect_source_from_name(uploaded.name)
    st.write(f"File: `{uploaded.name}`")
    if source == "auto":
        st.info(f"Auto-selected source: **{suggested}**")

    if st.button("Extract to Excel", type="primary"):
        chosen = suggested if source == "auto" else source
        config = SOURCE_CONFIG[chosen]

        with st.spinner("Reading PDF..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = Path(tmpdir) / uploaded.name
                pdf_path.write_bytes(uploaded.getvalue())

                raw_rows = read_pdf(str(pdf_path), mode=config["read_mode"])

        with st.spinner("Parsing prices..."):
            records = config["parser"](raw_rows)

        with st.spinner("Cleaning data..."):
            records = clean(records)

        if not records:
            st.error("No items found in this PDF.")
        else:
            st.success(f"Extracted {len(records)} items.")
            xlsx_bytes = records_to_xlsx_bytes(records)
            out_name = f"{Path(uploaded.name).stem}.xlsx"
            st.download_button(
                label="Download Excel",
                data=xlsx_bytes,
                file_name=out_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

