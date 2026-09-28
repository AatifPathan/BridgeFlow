"""Tests for pairing-code security: single use, guess limit, request rate limit."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from security import pairing_manager as pm


@pytest.fixture(autouse=True)
def reset_state():
    pm._pending_codes.clear()
    pm._recent_requests.clear()


def test_code_is_six_digits_and_single_use():
    code = pm.generate_pairing_code("dev-A")
    assert len(code) == 6 and code.isdigit()
    assert pm.verify_pairing_code("dev-A", code) is True
    assert pm.verify_pairing_code("dev-A", code) is False  # replay rejected


def test_code_burns_after_too_many_wrong_guesses():
    code = pm.generate_pairing_code("dev-A")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(pm.MAX_WRONG_ATTEMPTS):
        assert pm.verify_pairing_code("dev-A", wrong) is False
    # even the CORRECT code no longer works once the code is burned
    assert pm.verify_pairing_code("dev-A", code) is False


def test_pairing_requests_are_rate_limited():
    for i in range(pm.MAX_REQUESTS_PER_MINUTE):
        assert pm.generate_pairing_code(f"dev-{i}") is not None
    assert pm.generate_pairing_code("dev-flood") is None
