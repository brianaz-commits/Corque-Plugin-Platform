# Suggested filename: tools/worldBankCountryDataTools.py

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import requests
from langchain_core.tools import tool

from config.settings import settings


# Common indicator presets (World Bank indicator codes)
_INDICATOR_PRESETS: Dict[str, str] = {
    # Population & demographics
    "population": "SP.POP.TOTL",
    "population_total": "SP.POP.TOTL",
    "population_growth": "SP.POP.GROW",
    "urban_population": "SP.URB.TOTL",
    "urban_population_pct": "SP.URB.TOTL.IN.ZS",
    # Economy
    "gdp_current_usd": "NY.GDP.MKTP.CD",
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "gdp_per_capita_current_usd": "NY.GDP.PCAP.CD",
    "gni_per_capita_current_usd": "NY.GNP.PCAP.CD",
    "inflation_cpi": "FP.CPI.TOTL.ZG",
    "unemployment_pct": "SL.UEM.TOTL.ZS",
    # Health
    "life_expectancy": "SP.DYN.LE00.IN",
    "infant_mortality": "SP.DYN.IMRT.IN",
    # Environment
    "co2_emissions_kt": "EN.ATM.CO2E.KT",
    "co2_emissions_per_capita": "EN.ATM.CO2E.PC",
    "renewable_energy_pct": "EG.FEC.RNEW.ZS",
}


def _get_base_url() -> str:
    """
    Read base URL from settings if present; otherwise use the official default.
    """
    base_url = getattr(settings, "worldBankApiBaseUrl", None) or getattr(
        settings, "worldbankApiBaseUrl", None
    )
    if isinstance(base_url, str) and base_url.strip():
        return base_url.strip().rstrip("/")
    # Official World Bank API base URL (no API key required)
    return "https://api.worldbank.org"


def _request_json(url: str, params: Dict[str, Any], timeout_s: int) -> Tuple[Optional[Any], Optional[str]]:
    """
    Internal helper for GET requests that returns (json_data, error_message).
    Never raises to caller.
    """
    headers = {
        "User-Agent": "corque-plugin/1.0 (WorldBank tool)",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout_s)
    except Exception as e:
        return None, f"request error: {str(e)}"

    if resp.status_code != 200:
        text = resp.text or ""
        return None, f"http {resp.status_code}: {text[:300]}"

    try:
        return resp.json(), None
    except Exception:
        return None, "failed to parse json response"


def _normalize_country_code(country: str) -> str:
    """
    Normalize country input. If it's a 2- or 3-letter code, use it.
    Otherwise return the original (to be resolved by search).
    """
    c = country.strip()
    if len(c) in (2, 3) and c.replace("-", "").isalpha():
        return c.lower()
    return c


def _resolve_country_to_iso2(base_url: str, country_input: str, timeout_s: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve a country name/alias to ISO2 code by scanning World Bank country list.
    Returns (iso2, error). Never raises.
    """
    # If already ISO2, accept as-is
    c = country_input.strip()
    if len(c) == 2 and c.isalpha():
        return c.lower(), None

    # World Bank countries list is paginated; we fetch up to 400 per page.
    # This is still lightweight enough for a tool call.
    url = f"{base_url}/v2/country"
    params = {"format": "json", "per_page": 400, "page": 1}

    data, err = _request_json(url, params=params, timeout_s=timeout_s)
    if err:
        return None, f"failed to fetch country list: {err}"

    # Response shape: [metadata, [countryObj...]]
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
        return None, "unexpected country list response format"

    target = country_input.strip().lower()
    # Try exact match on name first, then substring
    exact_candidates: List[Dict[str, Any]] = []
    partial_candidates: List[Dict[str, Any]] = []

    for item in data[1]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        iso2 = str(item.get("iso2Code", "")).strip().lower()
        if not name or not iso2:
            continue

        name_l = name.lower()
        if name_l == target:
            exact_candidates.append(item)
        elif target in name_l:
            partial_candidates.append(item)

    chosen = (exact_candidates or partial_candidates)
    if not chosen:
        return None, f"country not found for input='{country_input}'"

    # Choose the first match; return its ISO2
    iso2 = str(chosen[0].get("iso2Code", "")).strip().lower()
    if not iso2:
        return None, "matched country missing iso2Code"
    return iso2, None


def _pick_indicator_code(indicator: str) -> str:
    """
    Map human-friendly indicator names to World Bank indicator codes.
    If user passes a code like 'SP.POP.TOTL', keep it.
    """
    s = indicator.strip()
    if not s:
        return _INDICATOR_PRESETS["population"]
    key = s.lower().replace(" ", "_")
    return _INDICATOR_PRESETS.get(key, s)


def _extract_series(json_payload: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Extract time series from World Bank indicator response.
    Response shape: [metadata, [ {date, value, country, indicator, ...}, ... ]]
    Returns (parsed, error). Never raises.
    """
    if not isinstance(json_payload, list) or len(json_payload) < 2 or not isinstance(json_payload[1], list):
        # Sometimes the API returns {"message":[...]} on error
        if isinstance(json_payload, dict) and "message" in json_payload:
            return None, f"api message: {json_payload.get('message')}"
        return None, "unexpected indicator response format"

    rows = [r for r in json_payload[1] if isinstance(r, dict)]
    if not rows:
        return None, "no data returned"

    # Parse metadata from the first row
    first = rows[0]
    country_obj = first.get("country", {}) if isinstance(first.get("country"), dict) else {}
    indicator_obj = first.get("indicator", {}) if isinstance(first.get("indicator"), dict) else {}

    country_name = str(country_obj.get("value", "")).strip()
    indicator_name = str(indicator_obj.get("value", "")).strip()
    indicator_id = str(indicator_obj.get("id", "")).strip()

    # Build datapoints: year(int), value(number|None)
    points: List[Dict[str, Any]] = []
    for r in rows:
        date_str = str(r.get("date", "")).strip()
        try:
            year = int(date_str)
        except Exception:
            continue
        value = r.get("value", None)
        points.append({"year": year, "value": value})

    # Points usually come newest->oldest; keep as-is but also provide sorted_asc
    points_asc = sorted(points, key=lambda x: x["year"])

    return {
        "country_name": country_name or None,
        "indicator_name": indicator_name or None,
        "indicator_code": indicator_id or indicator_id,
        "data": points,
        "data_asc": points_asc,
    }, None


@tool
def get_worldbank_country_stats(
    country: str,
    indicator: str = "population",
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    latest_only: bool = True,
    timeout_s: int = 12,
) -> str:
    """
    Query World Bank country statistics (e.g., population, GDP, life expectancy) by country and indicator.
    Use this tool when the user asks for official country-level metrics like population, GDP, unemployment, CO2, etc.

    Args:
        country (str): Required. Country ISO2/ISO3 code (e.g., "US", "CHN") or country name (e.g., "United States", "China").
        indicator (str): Optional. Indicator preset name (e.g., "population", "gdp_current_usd", "life_expectancy")
            or a World Bank indicator code (e.g., "SP.POP.TOTL"). Default is "population".
        start_year (Optional[int]): Optional. Start year (e.g., 2000). If provided with end_year, queries a range.
        end_year (Optional[int]): Optional. End year (e.g., 2023). If omitted while start_year provided, uses start_year only.
        latest_only (bool): Optional. If True, returns only the latest available datapoint in the requested range. Default True.
        timeout_s (int): Optional. Request timeout in seconds (3-30). Default is 12.

    Returns:
        str: A JSON string that can be parsed by json.loads, with keys:
            - query: resolved country/indicator and parameters
            - result: {country_name, indicator_name, indicator_code, latest?, series?}
            - warnings: list of non-fatal notes
        On failure, returns an error string starting with "Error:".
    """
    # Validate inputs
    if not isinstance(country, str) or not country.strip():
        return "Error: country parameter cannot be empty."

    if not isinstance(indicator, str):
        return "Error: indicator must be a string."

    if start_year is not None and (not isinstance(start_year, int) or start_year < 1900 or start_year > 2100):
        return "Error: start_year must be an integer between 1900 and 2100."
    if end_year is not None and (not isinstance(end_year, int) or end_year < 1900 or end_year > 2100):
        return "Error: end_year must be an integer between 1900 and 2100."
    if start_year is not None and end_year is not None and start_year > end_year:
        return "Error: start_year cannot be greater than end_year."

    if not isinstance(latest_only, bool):
        return "Error: latest_only must be a boolean."

    if not isinstance(timeout_s, int) or timeout_s < 3 or timeout_s > 30:
        return "Error: timeout_s must be an integer between 3 and 30."

    base_url = _get_base_url()
    warnings: List[str] = []

    # Resolve country to ISO2 if needed
    country_norm = _normalize_country_code(country)
    iso2: Optional[str] = None
    if len(country_norm) == 2 and country_norm.isalpha():
        iso2 = country_norm.lower()
    else:
        iso2, err = _resolve_country_to_iso2(base_url, country_norm, timeout_s=timeout_s)
        if err:
            return f"Error: {err}"
        warnings.append("country input resolved via World Bank country list; verify if multiple matches are possible.")

    # Resolve indicator code
    indicator_code = _pick_indicator_code(indicator)
    if indicator_code != indicator.strip() and indicator.strip().lower().replace(" ", "_") in _INDICATOR_PRESETS:
        warnings.append(f"indicator preset '{indicator}' mapped to World Bank code '{indicator_code}'.")

    # Build indicator request
    url = f"{base_url}/v2/country/{iso2}/indicator/{indicator_code}"
    params: Dict[str, Any] = {"format": "json", "per_page": 200}

    # Date range handling
    if start_year is not None and end_year is None:
        params["date"] = f"{start_year}:{start_year}"
    elif start_year is not None and end_year is not None:
        params["date"] = f"{start_year}:{end_year}"

    # Fetch data
    payload, err = _request_json(url, params=params, timeout_s=timeout_s)
    if err:
        return f"Error: failed to fetch World Bank data. {err}"

    series, err2 = _extract_series(payload)
    if err2:
        return f"Error: failed to parse World Bank data. {err2}"

    # Compose output
    data_points = series.get("data", []) if isinstance(series, dict) else []
    latest_point = None
    for p in data_points:
        # API is typically newest-first; pick first with non-null value
        if isinstance(p, dict) and p.get("value", None) is not None:
            latest_point = p
            break
    if latest_point is None and data_points:
        # No non-null value found; pick first anyway
        latest_point = data_points[0]

    result: Dict[str, Any] = {
        "country_name": series.get("country_name"),
        "indicator_name": series.get("indicator_name"),
        "indicator_code": indicator_code,
    }

    if latest_only:
        result["latest"] = latest_point
        if latest_point is None:
            warnings.append("No datapoint with a non-null value was found in the requested range.")
    else:
        result["series"] = series.get("data_asc")

    out = {
        "query": {
            "country_input": country.strip(),
            "country_iso2": iso2,
            "indicator_input": indicator.strip(),
            "indicator_code": indicator_code,
            "start_year": start_year,
            "end_year": end_year,
            "latest_only": latest_only,
            "base_url": base_url,
        },
        "result": result,
        "warnings": warnings,
    }

    try:
        return json.dumps(out, ensure_ascii=False)
    except Exception as e:
        return f"Error: failed to serialize result to JSON. {str(e)}"