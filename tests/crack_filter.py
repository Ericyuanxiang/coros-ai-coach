"""Crack /activity/detail/filter — filtering sub-data WITHIN a single activity.

Discovery: only params including 'labelId' get past the 1001 error to 1031
("Parameter input error"), proving the endpoint filters data inside a single
activity detail, not across activities.

Usage: python tests/crack_filter.py [--team] [--label-id ID]
"""

import asyncio
import json
import sys
import os
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coros_api import (
    _base_url, _auth_headers, get_stored_auth, try_auto_login, fetch_activities,
)

# With labelId as the required base param, test additional params
# These are likely sub-data filters within an activity's detail
PARAM_GROUPS = [
    # --- Lap / segment filters ---
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "lap": "1"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "lapId": "1"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "segment": "1"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "split": "1"},

    # --- Metric filters ---
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "metric": "heartRate"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "dataType": "hr"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "type": "hr"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "field": "heartRate"},

    # --- Time range filters within activity ---
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "startSeconds": "0", "endSeconds": "3600"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "startTime": "0", "endTime": "3600"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "offset": "0", "duration": "3600"},

    # --- Graph / chart data queries ---
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "graphType": "pace"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "chartType": "pace"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "graph": "pace"},

    # --- Generic filter/query within activity ---
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "sportType": "100"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "sportType": "100", "page": "1", "size": "20"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "page": "1", "size": "20"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "startDay": "20260101", "endDay": "20260528"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "startDay": "20260101", "endDay": "20260528", "page": "1", "size": "20"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "startDay": "20260101", "endDay": "20260528", "sportType": "100","page": "1", "size": "20"},

    # --- Frequency / interval ---
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "interval": "1000"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "resolution": "high"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "sample": "60"},

    # --- Minimal with just labelId + userId ---
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER"},
    {"labelId": "PLACEHOLDER"},

    # --- Detail sub-query (like the detail/query endpoint but with extra filter) ---
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "sportType": "100"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "sportType": "100", "field": "laps"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "sportType": "100", "field": "hrData"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "sportType": "100", "field": "graphs"},
    {"labelId": "PLACEHOLDER", "userId": "PLACEHOLDER", "sportType": "100", "field": "intervals"},
]


async def try_get(url: str, params: dict, headers: dict) -> str:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params, headers=headers)
            body = resp.json() if resp.status_code == 200 else {"http": resp.status_code}
        r = body.get("result", "")
        if r == "0000":
            return f"GET  [OK] data={json.dumps(body.get('data'), ensure_ascii=False)[:200]} | params={params}"
        return f"GET  [{r}] {body.get('message','')[:80]} | params={params}"
    except Exception as e:
        return f"GET  [ERR] {e}"


async def try_post(url: str, data: dict, headers: dict) -> str:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, data=data, headers=headers)
            body = resp.json() if resp.status_code == 200 else {"http": resp.status_code}
        r = body.get("result", "")
        if r == "0000":
            return f"POST [OK] data={json.dumps(body.get('data'), ensure_ascii=False)[:200]} | data={data}"
        return f"POST [{r}] {body.get('message','')[:80]} | data={data}"
    except Exception as e:
        return f"POST [ERR] {e}"


async def main():
    is_team = "--team" in sys.argv
    label_id_override = None
    for a in sys.argv:
        if a.startswith("--label-id="):
            label_id_override = a.split("=", 1)[1]

    print("=== Authenticating ===")
    auth = get_stored_auth()
    if auth is None:
        auth = await try_auto_login()
    if auth is None:
        print("FATAL: No stored auth.")
        return

    headers = {k: v for k, v in _auth_headers(auth).items() if k != "Content-Type"}
    base = _base_url(auth.region)

    # Get a real labelId from activities list
    label_id = label_id_override
    if label_id is None:
        activities, _ = await fetch_activities(auth, "20260101", "20260528")
        if activities:
            label_id = activities[0].activity_id
            print(f"Using labelId from latest activity: {label_id} ({activities[0].sport_name})")
        else:
            label_id = auth.user_id  # fallback
            print(f"No activities found, using userId: {label_id}")

    if is_team:
        from coros_api import _get_primary_team_id
        team_id = await _get_primary_team_id(auth)
        url = f"{base}/activity/detail/team/filter"
        print(f"Team ID: {team_id}")
    else:
        url = f"{base}/activity/detail/filter"
    print(f"URL: {url}\n")

    # Substitute placeholders
    for g in PARAM_GROUPS:
        for k, v in list(g.items()):
            if v == "PLACEHOLDER":
                g[k] = label_id if "labelId" in k else (auth.user_id if "userId" in k else v)

    results_ok = []
    results_1031 = []
    results_1001 = []

    for i, params in enumerate(PARAM_GROUPS):
        label = f"[{i:02d}]"
        r = await try_get(url, params, headers)
        p = await try_post(url, params, headers)

        if "[OK]" in r:
            results_ok.append(f"  GET  {r}")
            print(f"  {label} {r}")
        elif "[1031]" in r:
            results_1031.append(f"  GET  {r}")
            print(f"  {label} {r}")
        else:
            print(f"  {label} {r}")

        if "[OK]" in p:
            results_ok.append(f"  POST {p}")
            print(f"  {label} {p}")
        elif "1031" in p:
            results_1031.append(f"  POST {p}")
        # Skip printing 1001 POST results to reduce noise

    print(f"\n=== Summary ===")
    print(f"OK (result=0000):    {len(results_ok)}")
    print(f"1031 (param error):  {len(results_1031)}")
    print(f"1001 (service exc):  all others")

    if results_ok:
        print("\n*** SUCCESSFUL CALLS ***")
        for r in results_ok:
            print(r)
    elif results_1031:
        print(f"\n{len(results_1031)} calls returned 1031 (parameter error).")
        print("The endpoint IS real and requires labelId, but we haven't found")
        print("the right set of companion parameters yet.")
        print("\nTry adding: sportType (from the labelId's actual sport), or")
        print("check the JS bundle for the exact field names at this call site.")


if __name__ == "__main__":
    asyncio.run(main())
