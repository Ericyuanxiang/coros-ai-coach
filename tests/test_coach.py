"""Tests for coach/ package — recommendation + safety (the unique-value modules)."""

import pytest
import coach


# ============================================================================
# generate_recommendation
# ============================================================================

class TestGenerateRecommendation:
    def test_ready_optimized_hard_training(self):
        r = coach.generate_recommendation(
            readiness={"score": "Ready"},
            fatigue={"level": "Fresh"},
            training_status={"state": "Optimized"},
        )
        assert r["intensity"] == "Hard"

    def test_moderate_easy_training(self):
        r = coach.generate_recommendation(
            readiness={"score": "Moderate"},
            fatigue={"level": "Fatigued"},
            training_status={"state": "Optimized"},
        )
        assert r["intensity"] == "Easy"

    def test_recovery_day(self):
        r = coach.generate_recommendation(
            readiness={"score": "Recover"},
            fatigue={"level": "Normal"},
            training_status={"state": "Optimized"},
        )
        assert r["intensity"] == "Easy"

    def test_rest_day(self):
        r = coach.generate_recommendation(
            readiness={"score": "Rest"},
            fatigue={"level": "Fatigued"},
            training_status={"state": "Excessive"},
        )
        assert r["intensity"] == "Rest"

    def test_race_ready(self):
        r = coach.generate_recommendation(
            readiness={"score": "Ready"},
            fatigue={"level": "Fresh"},
            training_status={"state": "Performance"},
        )
        assert r["intensity"] == "Hard"
        assert r["duration_minutes"] >= 60

    def test_overtrained_always_rest(self):
        r = coach.generate_recommendation(
            readiness={"score": "Ready"},
            fatigue={"level": "Overtrained"},
            training_status={"state": "Performance"},
        )
        assert r["intensity"] == "Rest"

    def test_return_keys_structure(self):
        r = coach.generate_recommendation(
            readiness={"score": "Moderate"},
            fatigue={"level": "Normal"},
            training_status={"state": "Maintaining"},
        )
        for k in ("primary", "alternative", "intensity", "duration_minutes", "why"):
            assert k in r

    def test_alternative_from_schedule(self):
        r = coach.generate_recommendation(
            readiness={"score": "Ready"},
            fatigue={"level": "Fresh"},
            training_status={"state": "Optimized"},
            schedule=[{"happenDay": "20260529", "name": "Z2 Long Run"}],
        )
        assert "alternative" in r

    def test_zone_target_from_profile(self):
        profile = {
            "rhr": 55, "max_hr": 185, "lthr": 172, "hr_zone_type": 1,
            "zones": {
                1: [
                    {"hrLow": 0, "hrHigh": 120},
                    {"hrLow": 120, "hrHigh": 145},
                    {"hrLow": 145, "hrHigh": 160},
                    {"hrLow": 160, "hrHigh": 172},
                    {"hrLow": 172, "hrHigh": 185},
                    {"hrLow": 185, "hrHigh": 200},
                ],
            },
        }
        r = coach.generate_recommendation(
            readiness={"score": "Ready"},
            fatigue={"level": "Fresh"},
            training_status={"state": "Optimized"},
            user_profile=profile,
        )
        assert "zone_target" in r
        zt = r["zone_target"]
        assert zt["model"] == "MaxHR"
        assert zt["bpm_low"] > 0
        assert zt["bpm_high"] > zt["bpm_low"]


# ============================================================================
# generate_alerts (safety)
# ============================================================================

class TestGenerateAlerts:
    def test_no_alerts_when_normal(self):
        alerts = coach.generate_alerts(
            [], [],
            training_status={"state": "Optimized", "load_impact": 0.8},
            hrv={"status": "Normal"},
            fatigue={"level": "Fresh"},
        )
        assert len(alerts) == 0

    def test_alerts_on_overtrained(self):
        alerts = coach.generate_alerts(
            [], [],
            training_status={"state": "Excessive", "load_impact": 1.5},
            hrv={"status": "Low"},
            fatigue={"level": "Overtrained"},
        )
        assert len(alerts) > 0

    def test_empty_data_no_alerts(self):
        alerts = coach.generate_alerts(
            [], [],
            training_status={"state": "Insufficient Data", "load_impact": 0},
            hrv={"status": "Insufficient Data"},
            fatigue={"level": "Normal"},
        )
        assert len(alerts) == 0
