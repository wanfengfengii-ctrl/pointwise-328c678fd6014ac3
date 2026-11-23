import sqlite3
from dataclasses import dataclass
from typing import Iterable

from intake.validation import VerifiedPackage, verify_package
from issue.envelope import valid_identifier


@dataclass(frozen=True)
class Receipt:
    receipt_id: int
    package_id: str


class IntakeStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        with self.connection:
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS received_packages (
                    package_id TEXT PRIMARY KEY,
                    digest TEXT NOT NULL,
                    raw BLOB NOT NULL
                )
            ''')
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id INTEGER PRIMARY KEY,
                    package_id TEXT NOT NULL UNIQUE REFERENCES received_packages(package_id)
                )
            ''')

    def accept(self, package: VerifiedPackage) -> Receipt:
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            row = self.connection.execute('''
                SELECT p.digest, p.raw, r.receipt_id
                FROM received_packages AS p JOIN receipts AS r USING (package_id)
                WHERE p.package_id = ?
            ''', (package.package_id,)).fetchone()
            if row is not None:
                digest, raw, receipt_id = row
                if digest != package.digest:
                    raise ValueError(f'package identity conflict: {package.package_id}')
                if raw != package.raw and verify_package(raw).digest != package.digest:
                    raise ValueError(f'archived package failed verification: {package.package_id}')
            else:
                self.connection.execute('''
                    INSERT INTO received_packages (package_id, digest, raw) VALUES (?, ?, ?)
                ''', (package.package_id, package.digest, package.raw))
                cursor = self.connection.execute(
                    'INSERT INTO receipts (package_id) VALUES (?)', (package.package_id,)
                )
                receipt_id = cursor.lastrowid
        return Receipt(receipt_id, package.package_id)

    def get(self, package_id: str) -> VerifiedPackage:
        if not valid_identifier(package_id):
            raise ValueError('invalid selected package identifier')
        row = self.connection.execute('''
            SELECT p.raw, p.digest
            FROM received_packages AS p JOIN receipts AS r USING (package_id)
            WHERE p.package_id = ?
        ''', (package_id,)).fetchone()
        if row is None:
            raise KeyError(f'package not received: {package_id}')
        package = verify_package(row[0])
        if package.package_id != package_id or package.digest != row[1]:
            raise ValueError(f'inconsistent stored package: {package_id}')
        return package

    def get_selected(self, package_ids: Iterable[str]) -> tuple[VerifiedPackage, ...]:
        self.connection.execute('BEGIN')
        with self.connection:
            return tuple(self.get(package_id) for package_id in package_ids)
