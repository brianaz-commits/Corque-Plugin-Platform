# Suggested filename: tools/openLibraryTools.py

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import requests
from langchain_core.tools import tool

from config.settings import settings


def _get_base_url() -> str:
    """
    Read base URL from settings if present; otherwise use default Open Library.
    """
    base_url = (
        getattr(settings, "openLibraryApiBaseUrl", None)
        or getattr(settings, "openlibraryApiBaseUrl", None)
        or getattr(settings, "openlibrary_base_url", None)
    )
    if isinstance(base_url, str) and base_url.strip():
        return base_url.strip().rstrip("/")
    return "https://openlibrary.org"


def _validate_timeout(timeout_s: int) -> Optional[str]:
    if not isinstance(timeout_s, int):
        return "Error: timeout_s must be an integer."
    if timeout_s < 3 or timeout_s > 30:
        return "Error: timeout_s must be between 3 and 30."
    return None


def _request_json(url: str, params: Dict[str, Any], timeout_s: int) -> Tuple[Optional[Any], Optional[str]]:
    headers = {
        "User-Agent": "corque-plugin/1.0 (Open Library tool)",
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


@tool
def openlibrary_search_books(query: str, limit: int = 10, page: int = 1, timeout_s: int = 12) -> str:
    """
    Search books using Open Library (no-auth).
    Use this tool when the user wants to find books by title/author/keyword.

    Args:
        query (str): Required. Search query (non-empty).
        limit (int): Optional. Results to return (1-50). Default 10.
        page (int): Optional. Page number (>=1). Default 1.
        timeout_s (int): Optional. HTTP timeout seconds (3-30). Default 12.

    Returns:
        str: JSON string {"query":{...},"count":N,"num_found":...,"results":[...]}.
             Each result includes title, author_name, first_publish_year, isbn, olid, cover_i (if available).
             On failure returns "Error: ...".
    """
    err = _validate_timeout(timeout_s)
    if err:
        return err

    if not isinstance(query, str) or not query.strip():
        return "Error: query must be a non-empty string."
    if not isinstance(limit, int) or limit < 1 or limit > 50:
        return "Error: limit must be an integer between 1 and 50."
    if not isinstance(page, int) or page < 1:
        return "Error: page must be an integer >= 1."

    base = _get_base_url()
    url = f"{base}/search.json"
    params = {"q": query.strip(), "limit": int(limit), "page": int(page)}

    payload, e = _request_json(url, params=params, timeout_s=timeout_s)
    if e:
        return f"Error: failed to search Open Library. {e}"
    if not isinstance(payload, dict):
        return "Error: unexpected Open Library response format."

    docs = payload.get("docs", [])
    results: List[Dict[str, Any]] = []
    if isinstance(docs, list):
        for d in docs:
            if not isinstance(d, dict):
                continue
            results.append(
                {
                    "title": d.get("title"),
                    "author_name": d.get("author_name"),
                    "first_publish_year": d.get("first_publish_year"),
                    "isbn": d.get("isbn"),
                    "olid": d.get("edition_key") or d.get("key"),
                    "cover_i": d.get("cover_i"),
                }
            )

    out = {
        "query": {"q": query.strip(), "limit": int(limit), "page": int(page), "base_url": base},
        "count": len(results),
        "num_found": payload.get("numFound"),
        "results": results,
    }

    try:
        return json.dumps(out, ensure_ascii=False)
    except Exception as ex:
        return f"Error: failed to serialize result to JSON. {str(ex)}"


@tool
def openlibrary_isbn_lookup(isbn: str, timeout_s: int = 12) -> str:
    """
    Lookup book metadata by ISBN using Open Library Books API (no-auth).
    Use this tool when the user has an ISBN and wants the title/authors/publish info/cover.

    Args:
        isbn (str): Required. ISBN-10 or ISBN-13. Hyphens/spaces allowed.
        timeout_s (int): Optional. HTTP timeout seconds (3-30). Default 12.

    Returns:
        str: JSON string {"isbn_input":..., "isbn":..., "data":{...}}.
             On failure returns "Error: ...".
    """
    err = _validate_timeout(timeout_s)
    if err:
        return err

    if not isinstance(isbn, str) or not isbn.strip():
        return "Error: isbn must be a non-empty string."

    cleaned = "".join(ch for ch in isbn.strip() if ch.isdigit() or ch.upper() == "X")
    if len(cleaned) not in (10, 13):
        return "Error: isbn must be 10 or 13 characters after removing separators."

    base = _get_base_url()
    url = f"{base}/api/books"
    bibkey = f"ISBN:{cleaned}"
    params = {"bibkeys": bibkey, "format": "json", "jscmd": "data"}

    payload, e = _request_json(url, params=params, timeout_s=timeout_s)
    if e:
        return f"Error: failed to fetch Open Library ISBN data. {e}"
    if not isinstance(payload, dict):
        return "Error: unexpected Open Library response format."

    data = payload.get(bibkey)
    if not data:
        return f"Error: no Open Library record found for ISBN {cleaned}."

    try:
        return json.dumps({"isbn_input": isbn.strip(), "isbn": cleaned, "data": data}, ensure_ascii=False)
    except Exception as ex:
        return f"Error: failed to serialize result to JSON. {str(ex)}"