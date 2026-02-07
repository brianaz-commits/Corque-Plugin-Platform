# Suggested filename: tools/stooqTools.py

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from langchain_core.tools import tool

from config.settings import settings


def _get_base_url() -> str:
    """
    Read base URL from settings if present; otherwise use default Stooq.
    """
    base_url = getattr(settings, "stooqApiBaseUrl", None) or getattr(settings, "stooq_base_url", None)
    if isinstance(base_url, str) and base_url.strip():
        return base_url.strip().rstrip("/")
    return "https://stooq.com"


def _validate_timeout(timeout_s: int) -> Optional[str]:
    if not isinstance(timeout_s, int):
        return "Error: timeout_s must be an integer."
    if timeout_s < 3 or timeout_s > 30:
        return "Error: timeout_s must be between 3 and 30."
    return None


def _validate_date_yyyy_mm_dd(date_str: str, field: str) -> Optional[str]:
    if not isinstance(date_str, str) or not date_str.strip():
        return f"Error: {field} must be a non-empty string in YYYY-MM-DD format."
    s = date_str.strip()
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return f"Error: {field} must be in YYYY-MM-DD format (got '{date_str}')."
    return None


def _request_text(url: str, params: Dict[str, Any], timeout_s: int) -> Tuple[Optional[str], Optional[str]]:
    headers = {
        "User-Agent": "corque-plugin/1.0 (Stooq tool)",
        "Accept": "text/csv,*/*",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout_s)
    except Exception as e:
        return None, f"request error: {str(e)}"

    if resp.status_code != 200:
        return None, f"http {resp.status_code}: {(resp.text or '')[:300]}"

    return resp.text, None


def _parse_stooq_csv(csv_text: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Parse Stooq historical CSV (Date,Open,High,Low,Close,Volume).
    """
    if not csv_text or not isinstance(csv_text, str):
        return [], "empty csv response"

    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)
    rows: List[Dict[str, Any]] = []

    def _to_float(x: Any) -> Optional[float]:
        try:
            if x is None:
                return None
            s = str(x).strip()
            if not s or s.lower() == "null":
                return None
            return float(s)
        except Exception:
            return None

    def _to_int(x: Any) -> Optional[int]:
        try:
            if x is None:
                return None
            s = str(x).strip()
            if not s or s.lower() == "null":
                return None
            return int(float(s))
        except Exception:
            return None

    for r in reader:
        if not isinstance(r, dict):
            continue
        date = (r.get("Date") or "").strip()
        if not date:
            continue

        rows.append(
            {
                "date": date,
                "open": _to_float(r.get("Open")),
                "high": _to_float(r.get("High")),
                "low": _to_float(r.get("Low")),
                "close": _to_float(r.get("Close")),
                "volume": _to_int(r.get("Volume")),
            }
        )

    if not rows:
        return [], "no rows parsed (symbol may be invalid or no data)"
    return rows, None


def _filter_rows_by_date(
    rows: List[Dict[str, Any]], start_date: Optional[str], end_date: Optional[str]
) -> List[Dict[str, Any]]:
    if not start_date and not end_date:
        return rows

    def _in_range(d: str) -> bool:
        if start_date and d < start_date:
            return False
        if end_date and d > end_date:
            return False
        return True

    return [r for r in rows if isinstance(r.get("date"), str) and _in_range(r["date"])]


def _sparkline(values: List[Optional[float]]) -> Optional[str]:
    """
    Unicode sparkline with 8 levels. Missing values -> '·'.
    """
    clean = [v for v in values if isinstance(v, (int, float))]
    if len(clean) < 2:
        return None

    mn, mx = min(clean), max(clean)
    if mx == mn:
        return "▁" * len(values)

    ticks = "▁▂▃▄▅▆▇█"
    out: List[str] = []
    for v in values:
        if not isinstance(v, (int, float)):
            out.append("·")
            continue
        idx = int((v - mn) / (mx - mn) * (len(ticks) - 1))
        idx = max(0, min(len(ticks) - 1, idx))
        out.append(ticks[idx])
    return "".join(out)


@tool
def stooq_get_history(
    symbol: str,
    interval: str = "d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
    include_sparkline: bool = True,
    timeout_s: int = 12,
) -> str:
    """
    Download historical OHLCV price data from Stooq (no-auth) and return it as JSON time series + optional ASCII sparkline.
    Use this tool when the user asks for stock/ETF/index/FX/crypto historical prices without needing any API key.

    Args:
        symbol (str): Required. Stooq symbol, e.g. "aapl.us", "msft.us", "spx", "eurusd".
        interval (str): Optional. "d" (daily), "w" (weekly), "m" (monthly). Default "d".
        start_date (Optional[str]): Optional. Filter start date "YYYY-MM-DD".
        end_date (Optional[str]): Optional. Filter end date "YYYY-MM-DD".
        limit (int): Optional. Max rows returned after filtering (1-2000). Default 200.
        include_sparkline (bool): Optional. If True, include ASCII sparkline based on close prices. Default True.
        timeout_s (int): Optional. HTTP timeout seconds (3-30). Default 12.

    Returns:
        str: JSON string (parseable by json.loads) with keys:
            {
              "query": {...},
              "count": N,
              "data": [{"date","open","high","low","close","volume"}, ...],
              "sparkline_close": "▁▂▃..." or null,
              "warnings": [...]
            }
        On failure returns an error string starting with "Error:".
    """
    err = _validate_timeout(timeout_s)
    if err:
        return err

    if not isinstance(symbol, str) or not symbol.strip():
        return "Error: symbol must be a non-empty string."
    sym = symbol.strip().lower()

    if interval not in ("d", "w", "m"):
        return "Error: interval must be one of 'd', 'w', 'm'."

    if start_date is not None:
        e = _validate_date_yyyy_mm_dd(start_date, "start_date")
        if e:
            return e
        start_date = start_date.strip()

    if end_date is not None:
        e = _validate_date_yyyy_mm_dd(end_date, "end_date")
        if e:
            return e
        end_date = end_date.strip()

    if not isinstance(limit, int) or limit < 1 or limit > 2000:
        return "Error: limit must be an integer between 1 and 2000."

    if not isinstance(include_sparkline, bool):
        return "Error: include_sparkline must be a boolean."

    base = _get_base_url()

    url = f"{base}/q/d/l/"
    params: Dict[str, Any] = {"s": sym, "i": interval}

    csv_text, e = _request_text(url, params=params, timeout_s=timeout_s)
    if e:
        return f"Error: failed to fetch Stooq CSV. {e}"

    rows, e2 = _parse_stooq_csv(csv_text)
    if e2:
        return f"Error: failed to parse Stooq CSV. {e2}"

    rows = _filter_rows_by_date(rows, start_date, end_date)

    if not rows:
        return "Error: no data after applying date filters."

    warnings: List[str] = []

    # Stooq typically returns oldest->newest
    if len(rows) > limit:
        warnings.append(f"Truncated results from {len(rows)} to limit={limit}.")
        rows = rows[-limit:]  # keep most recent

    spark = None
    if include_sparkline:
        spark = _sparkline([r.get("close") for r in rows])

    out = {
        "query": {
            "symbol": sym,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
            "base_url": base,
        },
        "count": len(rows),
        "data": rows,
        "sparkline_close": spark,
        "warnings": warnings,
    }

    try:
        return json.dumps(out, ensure_ascii=False)
    except Exception as ex:
        return f"Error: failed to serialize result to JSON. {str(ex)}"