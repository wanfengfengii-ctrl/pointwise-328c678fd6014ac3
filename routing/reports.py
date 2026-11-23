from __future__ import annotations

from typing import Iterable

from intake.store import IntakeStore
from routing.eligibility import build_eligible_network
from routing.history import ReportStore, SignedReport
from routing.requests import Location, bind_request
from routing.search import shortest_route


def route(
    intake: IntakeStore,
    reports: ReportStore,
    package_ids: Iterable[str],
    start: Location,
    end: Location,
    notice_id: str | None = None,
) -> SignedReport:
    if intake.connection is not reports.connection:
        raise ValueError('intake and report stores must share the offline connection')
    request = bind_request(intake, package_ids, start, end, notice_id)
    network = build_eligible_network(request)
    return reports.sign(request, shortest_route(network))
