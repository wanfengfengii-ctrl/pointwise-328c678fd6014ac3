import json
import sqlite3
from dataclasses import dataclass

from closures.targets import ClosureTargets


@dataclass(frozen=True)
class NoticeDeclaration:
    round_id: str
    tile_id: str
    revision_id: int
    notice_id: str
    targets: ClosureTargets


class NoticeStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        with self.connection:
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS notices (
                    revision_id INTEGER NOT NULL REFERENCES revisions(revision_id),
                    notice_id TEXT NOT NULL,
                    round_id TEXT NOT NULL,
                    tile_id TEXT NOT NULL,
                    segments TEXT NOT NULL,
                    portals TEXT NOT NULL,
                    PRIMARY KEY (revision_id, notice_id)
                )
            ''')

    def save(self, declaration: NoticeDeclaration) -> NoticeDeclaration:
        with self.connection:
            self.connection.execute('''
                INSERT INTO notices (revision_id, notice_id, round_id, tile_id, segments, portals)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (revision_id, notice_id) DO NOTHING
            ''', (
                declaration.revision_id, declaration.notice_id,
                declaration.round_id, declaration.tile_id,
                json.dumps(declaration.targets.segments), json.dumps(declaration.targets.portals),
            ))
            stored = self.get(declaration.revision_id, declaration.notice_id)
            if stored != declaration:
                raise ValueError('this notice already has a different frozen declaration')
        return stored

    @staticmethod
    def _declaration(row: tuple) -> NoticeDeclaration:
        revision_id, notice_id, round_id, tile_id, segments, portals = row
        return NoticeDeclaration(
            round_id, tile_id, revision_id, notice_id,
            ClosureTargets(tuple(json.loads(segments)), tuple(json.loads(portals))),
        )

    def get(self, revision_id: int, notice_id: str) -> NoticeDeclaration:
        row = self.connection.execute('''
            SELECT revision_id, notice_id, round_id, tile_id, segments, portals
            FROM notices WHERE revision_id = ? AND notice_id = ?
        ''', (revision_id, notice_id)).fetchone()
        if row is None:
            raise KeyError(f'unknown notice {notice_id!r} for revision {revision_id}')
        return self._declaration(row)

    def for_revision(self, revision_id: int) -> tuple[NoticeDeclaration, ...]:
        rows = self.connection.execute('''
            SELECT revision_id, notice_id, round_id, tile_id, segments, portals
            FROM notices WHERE revision_id = ? ORDER BY notice_id
        ''', (revision_id,))
        return tuple(self._declaration(row) for row in rows)
