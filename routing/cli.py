from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from intake.receipts import receive
from intake.store import IntakeStore
from routing.history import ReportStore, SignedReport, read
from routing.reports import route
from routing.requests import Location
from routing.search import RouteResult


def initialize_offline(connection: sqlite3.Connection) -> tuple[IntakeStore, ReportStore]:
    connection.execute('PRAGMA foreign_keys = ON')
    intake, reports = IntakeStore(connection), ReportStore(connection)
    intake.initialize()
    reports.initialize()
    return intake, reports


def _report_document(report: SignedReport) -> dict:
    document = asdict(report)
    document['result']['reachable'] = report.result.reachable
    return document


def _emit(value: dict, prefix: str = '') -> None:
    print(prefix + json.dumps(value, ensure_ascii=False, sort_keys=True))


def _demo() -> None:
    from issue.build import issue
    from issue.cli import initialize_source, record_file, register_file

    samples = Path(__file__).resolve().parents[1] / 'samples'
    with TemporaryDirectory(prefix='patrol-handoff-') as directory:
        source_path = Path(directory) / 'survey.sqlite'
        offline_path = Path(directory) / 'offline.sqlite'
        with closing(sqlite3.connect(source_path)) as source:
            revisions, notices, archive = initialize_source(source)
            west_5 = register_file(revisions, samples / 'west-5.json')
            west_7 = register_file(revisions, samples / 'west-7.json')
            east_open = register_file(revisions, samples / 'east.json')
            east_closed = register_file(revisions, samples / 'east.json')
            record_file(revisions, notices, east_closed, samples / 'east-f.json')
            pieces = [issue(revisions, notices, archive, revision_id) for revision_id in (
                west_5, west_7, east_open, east_closed
            )]
        with closing(sqlite3.connect(offline_path)) as offline:
            intake, _ = initialize_offline(offline)
            w5, w7, opened, closed = [receive(intake, piece.raw).package_id for piece in pieces]
        source_path.rename(source_path.with_suffix('.offsite'))
        start, end = Location('S', 'west'), Location('T', 'east')
        with closing(sqlite3.connect(offline_path)) as offline:
            intake, reports = initialize_offline(offline)
            ordinary = route(intake, reports, (w5, opened), start, end)
            bypass_5 = route(intake, reports, (w5, closed), start, end, 'F')
            bypass_7 = route(intake, reports, (w7, closed), start, end, 'F')
            restored = route(intake, reports, (w5, opened), start, end, 'F')
        with closing(sqlite3.connect(offline_path)) as offline:
            _, reports = initialize_offline(offline)
            recovered = read(reports, bypass_5.report_id)
            recovered_pair = [recovered, read(reports, bypass_7.report_id)]
        expected = [RouteResult(6, ('Q',)), RouteResult(8, ('Q',))]
        actual = [bypass_5.result, bypass_7.result]
        if (ordinary.result != RouteResult(3, ('P', 'Q'))
                or restored.result != ordinary.result or actual != expected
                or recovered_pair != [bypass_5, bypass_7]):
            raise ValueError('demo route or history differs from the hand-calculated results')
        for name, report in (
            ('ordinary', ordinary), ('closed_5', bypass_5), ('closed_7', bypass_7),
            ('restored', restored), ('historical', recovered),
        ):
            _emit({'operation': name, 'report': _report_document(report)})
        _emit({
            'case_id': 'v6.bypass_pair',
            'input': {'notice': 'F', 'closed_portal': 'P', 'start': asdict(start), 'end': asdict(end),
                      'package_pairs': [bypass_5.package_ids, bypass_7.package_ids]},
            'expected': [asdict(item) for item in expected],
            'actual': [asdict(item) for item in actual],
            'downstream_expected': [asdict(item) for item in expected],
            'downstream_actual': [asdict(item.result) for item in recovered_pair],
            'code_paths': ['issue/transfers.py', 'routing/eligibility.py', 'routing/search.py',
                           'routing/history.py'],
            'oracle': '封 P 后只剩 2+3 或 2+5 分钟的西幅绕行，再加东幅 Q→T 的 1 分钟',
        }, 'POINTWISE_SCENARIO ')


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='巡检交班值班库')
    modes = parser.add_subparsers(dest='mode', required=True)
    modes.add_parser('demo')
    offline = modes.add_parser('offline')
    offline.add_argument('database', type=Path)
    commands = offline.add_subparsers(dest='command', required=True)
    commands.add_parser('init')
    commands.add_parser('receive').add_argument('package', type=Path)
    request = commands.add_parser('route')
    request.add_argument('package_ids', nargs='+')
    request.add_argument('--notice')
    for end in ('start', 'end'):
        location = request.add_mutually_exclusive_group(required=True)
        location.add_argument(f'--{end}', nargs=2, metavar=('TILE', 'KEY'))
        location.add_argument(f'--{end}-portal', metavar='PORTAL')
    commands.add_parser('read').add_argument('report_id', type=int)
    return parser


def _location(site: list[str] | None, portal: str | None) -> Location:
    if site is None:
        return Location(portal)
    tile, key = site
    return Location(key, tile)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == 'demo':
            _demo()
            return 0
        with closing(sqlite3.connect(args.database)) as connection:
            intake, reports = initialize_offline(connection)
            if args.command == 'receive':
                result = asdict(receive(intake, args.package.read_bytes()))
            elif args.command == 'route':
                start = _location(args.start, args.start_portal)
                end = _location(args.end, args.end_portal)
                result = _report_document(route(intake, reports, args.package_ids, start, end, args.notice))
            elif args.command == 'read':
                result = _report_document(read(reports, args.report_id))
            else:
                result = {'database': str(args.database)}
    except (ValueError, KeyError, OSError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 1
    _emit(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
