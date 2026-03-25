# PDF Price Extractor

Extracts item descriptions and prices from liquor store PDF pamphlets and outputs structured Excel spreadsheets.

Supports multiple PDF formats:
- **Ultra Liquors** — broadsheet-style table layouts
- **Makro** — text-heavy promotional pamphlets

## Setup

```bash
cd pdf_to_excel
pip install -r requirements.txt
```

## Usage

### Auto-detect source from filename

```bash
python main.py "../Makro.pdf"
python main.py "../16-31_March_2 Broadsheet 2026.pdf"
```

### Specify the source explicitly

```bash
python main.py "path/to/file.pdf" --source makro
python main.py "path/to/file.pdf" --source ultra
```

### Auto-find first PDF in parent folder

```bash
python main.py
```

## CLI Options

| Flag | Values | Description |
|------|--------|-------------|
| `--source` / `-s` | `ultra`, `makro`, `auto` | PDF format to use (default: `auto`) |

## Output

Results are saved to `output/<pdf_name>.xlsx` with columns:

| Column | Description |
|--------|-------------|
| Item Name | Product name and description |
| Price (R) | Retail price in Rand |
| Size | Bottle/pack size (Makro) |
| Pack Size | Case size (Ultra Liquors) |
| Savings | Discount amount (Makro) |
| Unit | Price unit — each, per case, etc. |
| Page | PDF page number |
| Source | Which parser was used |

## How It Works

1. **PDF Reading** — Uses `pdfplumber` tables for Ultra Liquors; `PyMuPDF` text extraction for Makro
2. **Price Parsing** — Format-specific parsers detect products, prices, and metadata
3. **Cleaning** — Removes duplicates, invalid rows, and normalizes data
4. **Excel Output** — Writes a formatted `.xlsx` file with auto-adjusted column widths
