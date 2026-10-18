"""CMS national Medicare Part B submitted-charge comparison.

Only a printed HCPCS/CPT code is sent to CMS. No bill text, patient, provider,
claim, service date, or uploaded document is included in the request.
"""
from __future__ import annotations

import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CMS_DATASET_ID = "6fea9d79-0129-4e4c-b1b8-23cd86a4f435"  # latest annual dataset series
CMS_DATA_URL = "https://data.cms.gov/data-api/v1/dataset/{}/data"
FLAG_MULTIPLE = 1.5


def national_average_charge(code: str) -> tuple[int, str] | None:
    """Return (average submitted charge in cents, CMS service year) for a code.

    CMS aggregates by place of service. Where both facility and non-facility
    records exist, combine the published averages weighted by service count.
    This is a Medicare Part B reference, not a universal cash-price average.
    """
    code = code.strip().upper()
    if not code or len(code) > 10 or not code.isalnum():
        return None
    dataset_id = os.getenv("CMS_PRICE_DATASET_ID", CMS_DATASET_ID)
    params = {
        "filter[filter_code][condition][path]": "HCPCS_Cd",
        "filter[filter_code][condition][operator]": "=",
        "filter[filter_code][condition][value]": code,
        "filter[filter_geo][condition][path]": "Rndrng_Prvdr_Geo_Lvl",
        "filter[filter_geo][condition][operator]": "=",
        "filter[filter_geo][condition][value]": "National",
        "size": "100",
        "offset": "0",
    }
    request = Request(CMS_DATA_URL.format(dataset_id) + "?" + urlencode(params), headers={"User-Agent": "Sana/1.0"})
    try:
        with urlopen(request, timeout=3) as response:
            payload = __import__("json").loads(response.read(2_000_000))
    except Exception:
        return None
    rows = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
    observations: list[tuple[float, float]] = []
    for row in rows:
        try:
            if str(row.get("Rndrng_Prvdr_Geo_Lvl", "")).lower() != "national":
                continue
            if str(row.get("HCPCS_Cd", "")).upper() != code:
                continue
            price = float(row["Avg_Sbmtd_Chrg"])
            count = float(row.get("Tot_Srvcs") or 0)
            if price > 0 and count > 0:
                observations.append((price, count))
        except (TypeError, ValueError, KeyError):
            continue
    if not observations:
        return None
    weighted = sum(price * count for price, count in observations) / sum(count for _, count in observations)
    return round(weighted * 100), "2024"


def is_high_vs_reference(line_total_cents: int, average_cents: int) -> bool:
    """A conservative review trigger; never means overcharge or error."""
    return line_total_cents > average_cents * FLAG_MULTIPLE
