"""Targeted crack for /activity/detail/filter using real activity data.

Key insight: /activity/detail/query and /activity/detail/download both use
POST form-data with {labelId, userId, sportType}. The filter endpoint likely
uses the same base params plus additional filter criteria.

This script uses the coros_api library functions (not raw HTTP) to ensure
auth and parameter formats are correct.
"""

import asyncio
import json
import sys
import os
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coros_api import (
    _base_url, _auth_headers, get_stored_auth, try_auto_login,
    fetch_activities,
)


async def try_req(method: str, url: str, headers: dict, **kwargs) -> str:
    """Single request, return compact result string."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            if method == "GET":
                resp = await client.get(url, params=kwargs.get("get_params", {}), headers=headers)
            elif method == "POST_FORM":
                resp = await client.post(url, data=kwargs.get("form_data", {}), headers=headers)
            elif method == "POST_JSON":
                h = {**headers, "Content-Type": "application/json"}
                resp = await client.post(url, json=kwargs.get("json_data", {}), headers=h)
            else:
                return f"unknown method {method}"

            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text[:200]}
        r = body.get("result", "")
        if r == "0000":
            data = body.get("data", {})
            preview = json.dumps(data, ensure_ascii=False)[:200]
            return f"OK -> {preview}"
        return f"[{r}] {body.get('message','')[:60]} | apiCode={body.get('apiCode','')}"
    except Exception as e:
        return f"[ERR] {type(e).__name__}: {e}"


async def main():
    print("=== Auth ===")
    auth = get_stored_auth()
    if auth is None:
        auth = await try_auto_login()
    if auth is None:
        print("FATAL: no auth")
        return

    headers = {k: v for k, v in _auth_headers(auth).items() if k != "Content-Type"}
    base = _base_url(auth.region)

    # Get real activities with real labelId + sportType
    print("=== Fetching activities ===")
    activities, total = await fetch_activities(auth, "20260501", "20260528", size=5)
    print(f"Got {len(activities)} activities\n")

    if not activities:
        print("No activities in range.")
        return

    for i, act in enumerate(activities[:3]):
        lid = act.activity_id
        st = str(act.sport_type or 0)
        name = act.name or "unnamed"

        print(f"[{i}] {name} | labelId={lid} | sportType={st}")

        url = f"{base}/activity/detail/filter"

        # Base params matching detail/query exactly
        bp = {"labelId": lid, "userId": auth.user_id, "sportType": st}

        # --- GET with query params ---
        for label, params in [
            ("base only", bp),
            ("+page/size", {**bp, "page": "1", "size": "20"}),
            ("+startDay/endDay", {**bp, "startDay": "20260501", "endDay": "20260528"}),
            ("+all", {**bp, "startDay": "20260501", "endDay": "20260528", "page": "1", "size": "20"}),
            ("minimal (labelId only)", {"labelId": lid}),
            ("+type=all", {**bp, "type": "all"}),
            ("+field=laps", {**bp, "field": "laps"}),
        ]:
            r = await try_req("GET", url, headers, get_params=params)
            print(f"  GET  {label:30s} -> {r}")

        # --- POST form-data ---
        for label, data in [
            ("base only", bp),
            ("+page/size", {**bp, "page": "1", "size": "20"}),
            ("+startDay/endDay", {**bp, "startDay": "20260501", "endDay": "20260528"}),
            ("+all", {**bp, "startDay": "20260501", "endDay": "20260528", "page": "1", "size": "20"}),
        ]:
            r = await try_req("POST_FORM", url, headers, form_data=data)
            print(f"  POST_FORM {label:25s} -> {r}")

        # --- POST JSON ---
        r = await try_req("POST_JSON", url, headers, json_data=bp)
        print(f"  POST_JSON base only              -> {r}")

        print()

    print("=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
