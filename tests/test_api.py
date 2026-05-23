"""Integration tests for coros_api HTTP functions using mocks.

Zero external dependencies — uses only Python's built-in unittest.mock.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from coros_api import (
    _check_response,
    delete_plan,
    delete_workout,
    fetch_dashboard,
    fetch_schedule,
    fetch_schedule_summary,
    fetch_training_analysis,
    fetch_training_library,
    fetch_user_profile,
    import_training_program,
)
from models import StoredAuth


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

def make_auth(region: str = "cn") -> StoredAuth:
    return StoredAuth(
        access_token="test-token-abc",
        user_id="4647526",
        region=region,
        timestamp=1700000000000,
    )


SUCCESS = {"result": "0000", "data": {}}
API_ERROR = {"result": "1001", "message": "invalid token"}


# ---------------------------------------------------------------------------
# Mock infrastructure — real classes, no MagicMock for responses
# ---------------------------------------------------------------------------

class MockResponse:
    """A fake httpx.Response that returns controlled data."""

    def __init__(self, json_body=None, status_code=200, text="", headers=None):
        self._json = json_body or {}
        self.status_code = status_code
        self.text = text
        self._headers = headers or MockHeaders()

    def json(self):
        return self._json

    def raise_for_status(self):
        pass

    class headers:
        @staticmethod
        def get_list(_):
            return []


class MockHeaders:
    def get_list(self, _):
        return []


class MockClient:
    """A fake httpx.AsyncClient usable as an async context manager."""

    def __init__(self, get_resp=None, post_resp=None, get_error=None, post_error=None):
        self._get_resp = get_resp
        self._post_resp = post_resp
        self._get_error = get_error
        self._post_error = post_error

    async def get(self, *args, **kwargs):
        if self._get_error:
            raise self._get_error
        if callable(self._get_resp):
            return self._get_resp(*args, **kwargs)
        return self._get_resp

    async def post(self, *args, **kwargs):
        if self._post_error:
            raise self._post_error
        if callable(self._post_resp):
            return self._post_resp(*args, **kwargs)
        return self._post_resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _resp(json_body=None, text="", headers=None):
    """Build a MockResponse."""
    return MockResponse(json_body=json_body, text=text, headers=headers)


def _patch_http(get_resp=None, post_resp=None, get_error=None, post_error=None):
    """Patch httpx.AsyncClient to return a MockClient with preset responses."""
    return patch("httpx.AsyncClient",
                 return_value=MockClient(get_resp, post_resp, get_error, post_error))


# ---------------------------------------------------------------------------
# _check_response  (unit test — no HTTP needed)
# ---------------------------------------------------------------------------

class TestCheckResponse:
    def test_passes_on_result_0000(self):
        _check_response({"result": "0000"}, "dummy")

    def test_raises_on_error_result(self):
        with pytest.raises(ValueError, match="Coros dummy error: bad"):
            _check_response({"result": "9999", "message": "bad"}, "dummy")


# ---------------------------------------------------------------------------
# fetch_dashboard
# ---------------------------------------------------------------------------

class TestFetchDashboard:
    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self):
        auth = make_auth()
        with _patch_http(get_resp=_resp(SUCCESS)):
            result = await fetch_dashboard(auth)
        assert result == {}

    @pytest.mark.asyncio
    async def test_raises_on_api_error(self):
        auth = make_auth()
        with _patch_http(get_resp=_resp(API_ERROR)):
            with pytest.raises(ValueError, match="Coros dashboard error"):
                await fetch_dashboard(auth)

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self):
        auth = make_auth()
        with _patch_http(get_error=Exception("Connection refused")):
            with pytest.raises(Exception, match="Connection refused"):
                await fetch_dashboard(auth)


# ---------------------------------------------------------------------------
# fetch_training_analysis  (dual parallel API)
# ---------------------------------------------------------------------------

DAY_ITEM = {
    "happenDay": 20260515, "timestamp": 1772467200,
    "avgSleepHrv": 66.0, "sleepHrvBase": 59.0, "sleepHrvIntervalList": [5, 24, 41, 77],
    "rhr": 60, "testRhr": 58, "lthr": 180,
    "trainingLoad": 39, "trainingLoadTarget": 0.0, "trainingLoadRatio": 0.14,
    "trainingLoadRatioState": 1,
    "trainingLoadRatioZoneList": [{"max": 0.5, "min": 0.0, "type": 1}],
    "t7d": 280, "t28d": 1120, "ct7dMaxFixed": 320.0, "ct7dMin": 200.0,
    "recomendTlMax": 400.0, "recomendTlMin": 250.0,
    "tiredRate": 2.0, "tiredRateOld": 1.8,
    "tiredRateStateNew": 0, "tiredRateNewZoneList": [],
    "tib": 1.0, "ati": 30.0, "cti": 28.0, "performance": 5,
    "distance": 5000.0, "distanceTarget": 6000.0,
    "duration": 1800, "durationTarget": 2000,
    "vo2max": 52, "staminaLevel": 45.0, "staminaLevel7d": 44.0, "ltsp": 253,
    "preTiredRate": 0.0, "weekHrvAvg": 0.0,
}


def _training_analysis_get_side_effect(url, **kwargs):
    """Return different JSON depending on whether it's dayDetail or analyse."""
    if "dayDetail" in url:
        return _resp({"result": "0000", "data": {"dayList": [DAY_ITEM]}})
    return _resp({
        "result": "0000",
        "data": {
            "t7dayList": [],
            "weekList": [{"firstDayOfWeek": "20260512", "trainingLoad": 200}],
            "record": {"distanceRecord": [], "durationRecord": [], "tlRecord": []},
            "sportStatistic": [],
            "summaryInfo": {},
            "tlIntensity": {},
            "sportDataSummary": {"totalActivityCount": 42},
            "trainingWeekStageList": [],
        },
    })


class TestFetchTrainingAnalysis:
    @pytest.mark.asyncio
    async def test_returns_all_8_panels(self):
        auth = make_auth()
        with _patch_http(get_resp=_training_analysis_get_side_effect):
            result = await fetch_training_analysis(auth, "20260515", "20260522")

        assert "daily_records" in result
        assert "week_list" in result
        assert "records" in result
        assert "sport_statistic" in result
        assert "summary_info" in result
        assert "tl_intensity" in result
        assert "sport_data_summary" in result
        assert "training_week_stages" in result
        assert result["sport_data_summary"]["totalActivityCount"] == 42

    @pytest.mark.asyncio
    async def test_parses_daily_record_from_day_detail(self):
        auth = make_auth()
        with _patch_http(get_resp=_training_analysis_get_side_effect):
            result = await fetch_training_analysis(auth, "20260515", "20260522")

        assert len(result["daily_records"]) == 1
        rec = result["daily_records"][0]
        assert rec["date"] == "20260515"
        assert rec["rhr"] == 60
        assert rec["avg_sleep_hrv"] == 66.0

    @pytest.mark.asyncio
    async def test_merges_t7daylist_into_daily_records(self):
        auth = make_auth()
        detail_item = {**DAY_ITEM, "avgSleepHrv": None, "rhr": 0}
        t7_item = {"happenDay": 20260515, "avgSleepHrv": 55.0, "rhr": 62}

        def side_effect(url, **kwargs):
            if "dayDetail" in url:
                return _resp({"result": "0000", "data": {"dayList": [detail_item]}})
            return _resp({
                "result": "0000",
                "data": {
                    "t7dayList": [t7_item],
                    "weekList": [], "record": {}, "sportStatistic": [],
                    "summaryInfo": {}, "tlIntensity": {},
                    "sportDataSummary": {}, "trainingWeekStageList": [],
                },
            })

        with _patch_http(get_resp=side_effect):
            result = await fetch_training_analysis(auth, "20260515", "20260522")

        rec = result["daily_records"][0]
        assert rec["avg_sleep_hrv"] == 55.0
        assert rec["rhr"] == 62

    @pytest.mark.asyncio
    async def test_raises_on_detail_error(self):
        auth = make_auth()
        with _patch_http(get_resp=_resp(API_ERROR)):
            with pytest.raises(ValueError, match="Coros analyse error"):
                await fetch_training_analysis(auth, "20260515", "20260522")


# ---------------------------------------------------------------------------
# delete_workout / delete_plan
# ---------------------------------------------------------------------------

class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_workout_succeeds_on_valid_id(self):
        auth = make_auth()
        with _patch_http(post_resp=_resp(SUCCESS)):
            await delete_workout(auth, "workout-123")  # no raise

    @pytest.mark.asyncio
    async def test_delete_workout_raises_on_error(self):
        auth = make_auth()
        with _patch_http(post_resp=_resp(API_ERROR)):
            with pytest.raises(ValueError, match="Coros workout delete error"):
                await delete_workout(auth, "bad-id")

    @pytest.mark.asyncio
    async def test_delete_plan_succeeds_on_valid_id(self):
        auth = make_auth()
        with _patch_http(post_resp=_resp(SUCCESS)):
            await delete_plan(auth, "plan-456")  # no raise

    @pytest.mark.asyncio
    async def test_delete_plan_raises_on_error(self):
        auth = make_auth()
        with _patch_http(post_resp=_resp(API_ERROR)):
            with pytest.raises(ValueError, match="Coros plan delete error"):
                await delete_plan(auth, "bad-id")


# ---------------------------------------------------------------------------
# fetch_schedule / fetch_schedule_summary
# ---------------------------------------------------------------------------

class TestSchedule:
    @pytest.mark.asyncio
    async def test_fetch_schedule_returns_data(self):
        auth = make_auth()
        sched_data = {"result": "0000", "data": {"key1": "val1"}}
        with _patch_http(get_resp=_resp(sched_data)):
            result = await fetch_schedule(auth, "20260501", "20260531")

        assert isinstance(result, dict)
        assert result["key1"] == "val1"

    @pytest.mark.asyncio
    async def test_fetch_schedule_summary_returns_aggregates(self):
        auth = make_auth()
        s = {"result": "0000", "data": {"duration": 3600, "trainingLoad": 150, "count": 3}}
        with _patch_http(get_resp=_resp(s)):
            result = await fetch_schedule_summary(auth, "20260501", "20260531")

        assert result["duration"] == 3600
        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_fetch_schedule_raises_on_error(self):
        auth = make_auth()
        with _patch_http(get_resp=_resp(API_ERROR)):
            with pytest.raises(ValueError, match="Coros schedule error"):
                await fetch_schedule(auth, "20260501", "20260531")


# ---------------------------------------------------------------------------
# fetch_user_profile
# ---------------------------------------------------------------------------

class TestUserProfile:
    @pytest.mark.asyncio
    async def test_returns_zones_and_baselines(self):
        auth = make_auth()
        data = {
            "result": "0000",
            "data": {
                "userId": "4647526", "nickname": "Eric",
                "stature": 181.0, "weight": 60.0,
                "maxHr": 202, "rhr": 56, "hrZoneType": 2,
                "zoneData": {
                    "lthr": 181, "ltsp": 253, "ftp": 180,
                    "maxHrZone": [121, 142, 165, 179, 189],
                    "rhrZone": [142, 152, 165, 179, 189],
                    "lthrZone": [145, 153, 165, 179, 189],
                    "ltspZone": [],
                    "cyclePowerZone": [],
                },
                "userProfile": {"language": "zh-CN", "gender": "male"},
                "unit": 0, "sex": "male",
                "sportDataSummary": {"count": 226},
            },
        }
        with _patch_http(get_resp=_resp(data)):
            result = await fetch_user_profile(auth)

        assert result["user_id"] == "4647526"
        assert result["nickname"] == "Eric"
        assert result["max_hr"] == 202
        assert result["rhr"] == 56
        assert 2 in result["zones"]
        assert len(result["zones"][2]) == 5  # 5 boundaries = 6 zones

    @pytest.mark.asyncio
    async def test_raises_on_error(self):
        auth = make_auth()
        with _patch_http(get_resp=_resp(API_ERROR)):
            with pytest.raises(ValueError, match="Coros account query error"):
                await fetch_user_profile(auth)


# ---------------------------------------------------------------------------
# fetch_training_library  (SSR page + paginated API, no auth)
# ---------------------------------------------------------------------------

SSR_HTML = '<html><body><script>window.__INITIAL_STATE__ = {"csrf":"csrf-abc","country":"cn"};</script></body></html>'

LIBRARY_API_RESP = {
    "result": "0000",
    "data": {
        "list": [
            {
                "_id": "abc123",
                "linked_id": "476133458610143331",
                "title": "VO2max Interval",
                "content": "HIIT to boost VO2max",
                "category": "workout",
                "sport_type": ["run"],
                "workout_target": ["vo2max"],
                "difficulty": ["advanced"],
                "author": "coros",
                "author_i18n": "COROS Coaches",
                "download_count": 1520,
                "iconType": 1, "region": 1,
                "createdAt": "2024-01-01", "updatedAt": "2025-06-01",
            },
        ],
        "pagination": {"total": 1, "offset": 0, "limit": 50},
    },
}


def _library_get_side_effect(url, **kwargs):
    """SSR page OR paginated API, depending on URL."""
    if "api" not in url:
        return MockResponse(text=SSR_HTML)
    return _resp(LIBRARY_API_RESP)


class TestFetchTrainingLibrary:
    @pytest.mark.asyncio
    async def test_parses_programs_from_api(self):
        with _patch_http(get_resp=_library_get_side_effect):
            programs = await fetch_training_library("cn", "zh-CN")

        assert len(programs) == 1
        p = programs[0]
        assert p.title == "VO2max Interval"
        assert p.linked_id == "476133458610143331"
        assert p.category == "workout"
        assert "run" in p.sport_types
        assert "advanced" in p.difficulties

    @pytest.mark.asyncio
    async def test_filters_by_category(self):
        with _patch_http(get_resp=_library_get_side_effect):
            programs = await fetch_training_library("cn", "zh-CN", category="plan")
        assert len(programs) == 0  # only workout in mock data

    @pytest.mark.asyncio
    async def test_filters_by_sport_type(self):
        with _patch_http(get_resp=_library_get_side_effect):
            programs = await fetch_training_library("cn", "zh-CN", sport_type="cycling")
        assert len(programs) == 0

    @pytest.mark.asyncio
    async def test_filters_by_difficulty(self):
        with _patch_http(get_resp=_library_get_side_effect):
            programs = await fetch_training_library("cn", "zh-CN", difficulty="beginner")
        assert len(programs) == 0

    @pytest.mark.asyncio
    async def test_raises_when_no_ssr_state(self):
        with _patch_http(get_resp=_resp(text="<html>no state here</html>")):
            with pytest.raises(ValueError, match="__INITIAL_STATE__"):
                await fetch_training_library("cn", "zh-CN")


# ---------------------------------------------------------------------------
# import_training_program  (GET detail -> POST copy)
# ---------------------------------------------------------------------------

DETAIL_RESP = {
    "result": "0000",
    "data": {
        "id": "workout-789", "name": "W30050", "programType": 1,
        "exercises": [{"name": "Warm-up", "duration": 600}],
    },
}

IMPORT_RESP = {
    "result": "0000",
    "data": {
        "id": "imported-001",
        "name": "VO2max Interval",
        "exerciseNum": 7,
        "estimatedTime": 3540,
    },
}


def _import_mock_client():
    """Build a MagicMock-based client for import tests that need call_args."""
    client = MagicMock()
    client.get = AsyncMock(return_value=_resp(DETAIL_RESP))
    client.post = AsyncMock(return_value=_resp(IMPORT_RESP))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


class TestImportTrainingProgram:
    @pytest.mark.asyncio
    async def test_imports_workout_with_get_then_post(self):
        auth = make_auth()
        with patch("httpx.AsyncClient", return_value=_import_mock_client()):
            result = await import_training_program(
                auth, "linked-123", "workout", 1, name="VO2max Interval")

        assert result["imported_id"] == "imported-001"
        assert result["name"] == "VO2max Interval"

    @pytest.mark.asyncio
    async def test_injects_custom_name(self):
        auth = make_auth()
        client = _import_mock_client()
        with patch("httpx.AsyncClient", return_value=client):
            await import_training_program(auth, "linked-123", "workout", 1,
                                          name="My Custom VO2max")

        post_body = client.post.call_args[1]["json"]
        assert post_body["name"] == "My Custom VO2max"

    @pytest.mark.asyncio
    async def test_uses_plan_endpoints_for_category_plan(self):
        auth = make_auth()
        client = _import_mock_client()
        with patch("httpx.AsyncClient", return_value=client):
            await import_training_program(auth, "linked-plan", "plan", 1,
                                          name="Test Plan")

        get_url = client.get.call_args[0][0]
        assert "plan/detail" in get_url
        post_url = client.post.call_args[0][0]
        assert "plan/copy" in post_url

    @pytest.mark.asyncio
    async def test_raises_on_detail_error(self):
        auth = make_auth()
        with _patch_http(get_resp=_resp(API_ERROR)):
            with pytest.raises(ValueError, match="Coros workout detail error"):
                await import_training_program(auth, "bad", "workout", 1)
