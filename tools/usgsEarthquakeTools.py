# Suggested filename: tools/usgsEarthquakeTools.py

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from langchain_core.tools import tool

from config.settings import settings


def _get_base_url() -> str:
    """
    Read base URL from settings if present; otherwise use default USGS Earthquake Catalog endpoint root.
    """
    base_url = (
        getattr(settings, "usgsEarthquakeApiBaseUrl", None)
        or getattr(settings, "usgsApiBaseUrl", None)
        or getattr(settings, "usgs_base_url", None)
    )
    if isinstance(base_url, str) and base_url.strip():
        return base_url.strip().rstrip("/")
    return "https://earthquake.usgs.gov/fdsnws/event/1"


def _validate_timeout(timeout_s: int) -> Optional[str]:
    if not isinstance(timeout_s, int):
        return "Error: timeout_s must be an integer."
    if timeout_s < 3 or timeout_s > 30:
        return "Error: timeout_s must be between 3 and 30."
    return None


def _validate_iso_date(date_str: str, field_name: str) -> Optional[str]:
    if not isinstance(date_str, str) or not date_str.strip():
        return f"Error: {field_name} must be a non-empty string in YYYY-MM-DD format."
    s = date_str.strip()
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return f"Error: {field_name} must be in YYYY-MM-DD format (got '{date_str}')."
    return None


def _request_json(url: str, params: Dict[str, Any], timeout_s: int) -> Tuple[Optional[Any], Optional[str]]:
    headers = {
        "User-Agent": "corque-plugin/1.0 (USGS Earthquake tool)",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout_s)
    except Exception as e:
        return None, f"request error: {str(e)}"

    if resp.status_code != 200:
        return None, f"http {resp.status_code}: {(resp.text or '')[:300]}"

    try:
        return resp.json(), None
    except Exception:
        return None, "failed to parse json response"


def _ms_to_iso_utc(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    try:
        return datetime.utcfromtimestamp(ms / 1000.0).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


@tool
def usgs_earthquake_search(
    start_date: str,
    end_date: str,
    min_magnitude: float = 0.0,
    max_results: int = 20,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: Optional[float] = None,
    order_by: str = "time",
    timeout_s: int = 12,
) -> str:
    """
    Search earthquakes using the USGS Earthquake Catalog API (no-auth).
    Use this tool when the user asks for earthquakes in a date range, optionally near a location within a radius.

    Args:
        start_date (str): Required. YYYY-MM-DD.
        end_date (str): Required. YYYY-MM-DD.
        min_magnitude (float): Optional. Minimum magnitude. Default 0.0.
        max_results (int): Optional. Max number of events (1-200). Default 20.
        latitude (Optional[float]): Optional. Latitude for geo filter; requires longitude and radius_km too.
        longitude (Optional[float]): Optional. Longitude for geo filter.
        radius_km (Optional[float]): Optional. Radius in km for geo filter.
        order_by (str): Optional. "time" or "magnitude". Default "time".
        timeout_s (int): Optional. HTTP timeout seconds (3-30). Default 12.

    Returns:
        str: JSON string {"query":{...},"count":N,"events":[{time_ms,time_iso,place,mag,url,lat,lon,depth_km}]}.
             On failure returns "Error: ...".
    """
    err = _validate_timeout(timeout_s)
    if err:
        return err

    e1 = _validate_iso_date(start_date, "start_date")
    if e1:
        return e1
    e2 = _validate_iso_date(end_date, "end_date")
    if e2:
        return e2

    if not isinstance(min_magnitude, (int, float)):
        return "Error: min_magnitude must be a number."
    if not isinstance(max_results, int) or max_results < 1 or max_results > 200:
        return "Error: max_results must be an integer between 1 and 200."
    if order_by not in ("time", "magnitude"):
        return "Error: order_by must be 'time' or 'magnitude'."

    using_geo = latitude is not None or longitude is not None or radius_km is not None
    if using_geo:
        if latitude is None or longitude is None or radius_km is None:
            return "Error: latitude, longitude, and radius_km must all be provided together."
        if not isinstance(latitude, (int, float)) or latitude < -90 or latitude > 90:
            return "Error: latitude must be between -90 and 90."
        if not isinstance(longitude, (int, float)) or longitude < -180 or longitude > 180:
            return "Error: longitude must be between -180 and 180."
        if not isinstance(radius_km, (int, float)) or radius_km <= 0 or radius_km > 2000:
            return "Error: radius_km must be between 0 and 2000."

    base = _get_base_url()
    url = f"{base}/query"
    params: Dict[str, Any] = {
        "format": "geojson",
        "starttime": start_date.strip(),
        "endtime": end_date.strip(),
        "minmagnitude": float(min_magnitude),
        "limit": int(max_results),
        "orderby": order_by,
    }
    if using_geo:
        params["latitude"] = float(latitude)  # type: ignore[arg-type]
        params["longitude"] = float(longitude)  # type: ignore[arg-type]
        params["maxradiuskm"] = float(radius_km)  # type: ignore[arg-type]

    payload, e = _request_json(url, params=params, timeout_s=timeout_s)
    if e:
        return f"Error: failed to fetch USGS earthquake data. {e}"
    if not isinstance(payload, dict):
        return "Error: unexpected USGS response format."

    events: List[Dict[str, Any]] = []
    features = payload.get("features", [])
    if isinstance(features, list):
        for f in features:
            if not isinstance(f, dict):
                continue
            props = f.get("properties", {}) if isinstance(f.get("properties"), dict) else {}
            geom = f.get("geometry", {}) if isinstance(f.get("geometry"), dict) else {}
            coords = geom.get("coordinates", []) if isinstance(geom.get("coordinates"), list) else []

            time_ms = props.get("time")
            time_ms_int = int(time_ms) if isinstance(time_ms, (int, float)) else None

            lon = coords[0] if len(coords) > 0 else None
            lat = coords[1] if len(coords) > 1 else None
            depth_km = coords[2] if len(coords) > 2 else None

            events.append(
                {
                    "time_ms": time_ms_int,
                    "time_iso": _ms_to_iso_utc(time_ms_int),
                    "place": props.get("place"),
                    "mag": props.get("mag"),
                    "url": props.get("url"),
                    "lat": lat,
                    "lon": lon,
                    "depth_km": depth_km,
                }
            )

    out = {
        "query": {
            "start_date": start_date.strip(),
            "end_date": end_date.strip(),
            "min_magnitude": float(min_magnitude),
            "max_results": int(max_results),
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km,
            "order_by": order_by,
            "base_url": base,
        },
        "count": len(events),
        "events": events,
    }

    try:
        return json.dumps(out, ensure_ascii=False)
    except Exception as ex:
        return f"Error: failed to serialize result to JSON. {str(ex)}"