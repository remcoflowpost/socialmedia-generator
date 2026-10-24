from datetime import UTC, datetime, timedelta

from app.domain.quality import can_mark_ready, embargo_issue, max_severity, with_embargo
from app.schema import LayoutReport, QualityIssue

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


def report(*issues: QualityIssue) -> LayoutReport:
    return LayoutReport(
        format_key="instagram/story", width=1080, height=1920, layers=[], issues=list(issues)
    )


def issue(severity: str, code: str = "resolution_low") -> QualityIssue:
    return QualityIssue(code=code, severity=severity, message="x")


def test_max_severity() -> None:
    assert max_severity([]) is None
    assert max_severity([issue("warning")]) == "warning"
    assert max_severity([issue("warning"), issue("error", "text_overflow")]) == "error"


def test_embargo_issue_only_for_future_dates() -> None:
    assert embargo_issue(NOW + timedelta(days=1), NOW).code == "embargo_active"
    assert embargo_issue(NOW - timedelta(days=1), NOW) is None


def test_with_embargo_adds_format_key() -> None:
    result = with_embargo(report(), NOW + timedelta(days=1), NOW)
    assert result.issues[0].format_key == "instagram/story"


def test_errors_block_ready_status() -> None:
    ok, reasons = can_mark_ready(
        [report(issue("error", "outside_safe_zone"))], client_approved=True
    )
    assert not ok
    assert "kwaliteitsfout" in reasons[0]


def test_warnings_do_not_block() -> None:
    assert can_mark_ready([report(issue("warning"))], client_approved=True) == (True, [])


def test_client_approval_required() -> None:
    ok, reasons = can_mark_ready([report()], client_approved=False)
    assert not ok
    assert reasons == ["Klantakkoord ontbreekt."]
