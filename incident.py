import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from intake.receipts import receive
from issue.build import issue
from issue.cli import initialize_source, record_file, register_file
from routing.cli import initialize_offline
from routing.reports import route
from routing.requests import Location
from routing.search import RouteResult


SAMPLES = Path(__file__).resolve().parent / "samples"


def prepare(source, offline):
    revisions, notices, archive = initialize_source(source)
    west_5, west_7, east_open, east_closed = (
        register_file(revisions, SAMPLES / name)
        for name in ("west-5.json", "west-7.json", "east.json", "east.json")
    )
    record_file(revisions, notices, east_closed, SAMPLES / "east-f.json")
    intake, _ = initialize_offline(offline)
    return tuple(
        receive(intake, issue(revisions, notices, archive, revision).raw).package_id
        for revision in (west_5, west_7, east_open, east_closed)
    )


def check_routes(offline, packages):
    intake, reports = initialize_offline(offline)
    west_5, west_7, east_open, east_closed = packages
    start, end = Location("S", "west"), Location("T", "east")
    ordinary = route(intake, reports, (west_5, east_open), start, end).result
    closed_5 = route(intake, reports, (west_5, east_closed), start, end, "F").result
    closed_7 = route(intake, reports, (west_7, east_closed), start, end, "F").result
    restored = route(intake, reports, (west_5, east_open), start, end, "F").result
    print(json.dumps({
        "ordinary": asdict(ordinary), "closed_5": asdict(closed_5),
        "closed_7": asdict(closed_7), "restored": asdict(restored),
    }, sort_keys=True))
    if ordinary != RouteResult(3, ("P", "Q")) or restored != ordinary:
        raise RuntimeError("open-east control did not match the sample route")
    if (closed_5, closed_7) != (RouteResult(6, ("Q",)), RouteResult(8, ("Q",))):
        print("PATROL_F_CLOSURE_ROUTE_MISMATCH")
        return 1
    return 0


def main():
    with TemporaryDirectory(prefix="patrol-incident-") as directory:
        source_path = Path(directory) / "source.sqlite"
        offline_path = Path(directory) / "offline.sqlite"
        with closing(sqlite3.connect(source_path)) as source, closing(sqlite3.connect(offline_path)) as offline:
            packages = prepare(source, offline)
        source_path.unlink()
        with closing(sqlite3.connect(offline_path)) as offline:
            return check_routes(offline, packages)


if __name__ == "__main__":
    raise SystemExit(main())
