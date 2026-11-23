from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass

from routing.requests import Location, RouteRequest
from routing.search import RouteResult


@dataclass(frozen=True)
class SignedReport:
    report_id: int
    receipt_id: int
    round_id: str
    package_ids: tuple[str, ...]
    start: Location
    end: Location
    notice_id: str | None
    result: RouteResult


class ReportStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        with self.connection:
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    report_id INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL
                )
            ''')
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS report_receipts (
                    receipt_id INTEGER PRIMARY KEY,
                    report_id INTEGER NOT NULL UNIQUE REFERENCES reports(report_id)
                )
            ''')

    def sign(self, request: RouteRequest, result: RouteResult) -> SignedReport:
        selection = request.selection
        payload = json.dumps({
            'round_id': selection.round_id, 'package_ids': selection.package_ids,
            'start': asdict(request.start), 'end': asdict(request.end),
            'notice_id': request.notice_id, 'result': asdict(result),
        }, sort_keys=True)
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            report = self.connection.execute('INSERT INTO reports (payload) VALUES (?)', (payload,))
            report_id = report.lastrowid
            receipt = self.connection.execute(
                'INSERT INTO report_receipts (report_id) VALUES (?)', (report_id,)
            )
            receipt_id = receipt.lastrowid
        return SignedReport(
            report_id, receipt_id, selection.round_id, selection.package_ids,
            request.start, request.end, request.notice_id, result,
        )

    def get(self, report_id: int) -> SignedReport:
        if type(report_id) is not int or report_id <= 0:
            raise ValueError('expected a positive report identifier')
        if report_id > 2**63 - 1:
            raise KeyError(f'unknown report: {report_id}')
        row = self.connection.execute('''
            SELECT r.payload, s.receipt_id
            FROM reports AS r JOIN report_receipts AS s USING (report_id)
            WHERE r.report_id = ?
        ''', (report_id,)).fetchone()
        if row is None:
            raise KeyError(f'unknown report: {report_id}')
        payload, receipt_id = row
        record = json.loads(payload)
        result = record['result']
        return SignedReport(
            report_id, receipt_id, record['round_id'], tuple(record['package_ids']),
            Location(**record['start']), Location(**record['end']), record['notice_id'],
            RouteResult(result['minutes'], tuple(result['portals'])),
        )


def read(store: ReportStore, report_id: int) -> SignedReport:
    return store.get(report_id)
