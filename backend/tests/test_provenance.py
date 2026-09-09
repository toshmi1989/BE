from app.domain.provenance import FieldStatus, Origin, assert_ai_may_write, can_ai_overwrite
import pytest


def test_ai_cannot_overwrite_verified() -> None:
    assert can_ai_overwrite(FieldStatus.VERIFIED) is False


def test_ai_can_propose_on_missing() -> None:
    assert can_ai_overwrite(FieldStatus.MISSING) is True
    assert can_ai_overwrite(FieldStatus.PROPOSED) is True
    assert can_ai_overwrite(FieldStatus.NEEDS_REVIEW) is True


def test_field_status_values_match_spec() -> None:
    expected = {
        "MISSING",
        "PROPOSED",
        "NEEDS_REVIEW",
        "VERIFIED",
        "REJECTED",
        "CALCULATED",
        "DERIVED",
        "NOT_IMPLEMENTED",
    }
    assert {s.value for s in FieldStatus} == expected


def test_assert_ai_may_write_blocks_verified() -> None:
    with pytest.raises(ValueError):
        assert_ai_may_write(FieldStatus.VERIFIED, Origin.AI_PROPOSED)
