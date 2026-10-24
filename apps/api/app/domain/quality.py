"""Beslislogica over kwaliteitsrapporten. De metingen zelf komen uit de layout-engine en
de render-service (TypeScript); hier wordt bepaald wat ze betekenen."""

from collections.abc import Iterable
from datetime import UTC, datetime

from app.schema import LayoutReport, QualityIssue


def embargo_issue(
    embargo_until: datetime | None, now: datetime | None = None
) -> QualityIssue | None:
    if not embargo_until:
        return None
    now = now or datetime.now(UTC)
    if embargo_until <= now:
        return None
    return QualityIssue(
        code="embargo_active",
        severity="warning",
        message=f"Embargo tot {embargo_until.astimezone(UTC):%d-%m-%Y %H:%M} UTC. Niet publiceren.",
    )


def with_embargo(
    report: LayoutReport, embargo_until: datetime | None, now: datetime | None = None
) -> LayoutReport:
    issue = embargo_issue(embargo_until, now)
    if not issue:
        return report
    issue.format_key = report.format_key
    return report.model_copy(update={"issues": [*report.issues, issue]})


def max_severity(issues: Iterable[QualityIssue]) -> str | None:
    severities = {issue.severity for issue in issues}
    if "error" in severities:
        return "error"
    if "warning" in severities:
        return "warning"
    return None


def can_mark_ready(
    reports: Iterable[LayoutReport], client_approved: bool
) -> tuple[bool, list[str]]:
    """Een post mag naar "approved" als de klant akkoord is en geen enkel formaat fouten
    heeft. Fouten blokkeren de status, niet de handmatige download."""
    reasons: list[str] = []
    if not client_approved:
        reasons.append("Klantakkoord ontbreekt.")
    errors = [issue for report in reports for issue in report.issues if issue.severity == "error"]
    if errors:
        reasons.append(f"{len(errors)} kwaliteitsfout(en) in de formaten.")
    return (not reasons, reasons)
