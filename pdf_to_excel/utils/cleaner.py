"""Data cleaning and normalization for extracted price data."""

import logging
import re

logger = logging.getLogger(__name__)

BOTTLE_SIZE_ONLY = re.compile(r"^[\d.]+\s*(ml|L|lt)$", re.IGNORECASE)


def _normalize_item(name: str) -> str:
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[^\w\s&'+.,/()-]", "", name)
    return name.strip()


def clean(records: list[dict]) -> list[dict]:
    """Clean and deduplicate extracted item-price records."""
    cleaned = []
    seen = set()

    for rec in records:
        item = _normalize_item(rec.get("item", ""))
        price = rec.get("price", 0)

        if not item or price <= 0:
            continue

        if BOTTLE_SIZE_ONLY.match(item):
            continue

        price = round(float(price), 2)

        dedup_key = (item.lower(), price)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        out = {"item": item, "price": price}
        # Carry through any extra fields present in the record
        passthrough_keys = [
            "retail_price", "case_price", "unit_price", "pack_size",
            "bottle_size", "size", "unit", "savings",
            "page", "confidence", "source",
        ]
        for key in passthrough_keys:
            if key in rec:
                val = rec[key]
                if val is None:
                    continue
                if isinstance(val, float) and val > 0:
                    out[key] = round(val, 2)
                elif val:
                    out[key] = val

        cleaned.append(out)

    removed = len(records) - len(cleaned)
    if removed:
        logger.info(f"Cleaning removed {removed} rows (invalid or duplicate)")
    logger.info(f"{len(cleaned)} clean rows remaining")
    return cleaned
