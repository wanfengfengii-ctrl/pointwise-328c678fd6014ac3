from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass

from survey.endpoints import EndpointRef
from survey.portals import SharedPortal
from survey.segments import DirectedSegment


@dataclass(frozen=True)
class Revision:
    round_id: str
    tile_id: str
    nodes: tuple[str, ...]
    segments: tuple[DirectedSegment, ...]
    portals: tuple[SharedPortal, ...]
    endpoints: tuple[EndpointRef, ...]
    revision_id: int | None = None


class RevisionStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        with self.connection:
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id INTEGER PRIMARY KEY,
                    round_id TEXT NOT NULL,
                    tile_id TEXT NOT NULL,
                    survey TEXT NOT NULL
                )
            ''')

    def save(self, revision: Revision) -> int:
        if revision.revision_id is not None:
            raise ValueError('a frozen revision already has an identifier')
        survey = {
            'nodes': revision.nodes,
            'segments': [asdict(segment) for segment in revision.segments],
            'portals': [asdict(portal) for portal in revision.portals],
            'endpoints': [asdict(endpoint) for endpoint in revision.endpoints],
        }
        with self.connection:
            cursor = self.connection.execute(
                'INSERT INTO revisions (round_id, tile_id, survey) VALUES (?, ?, ?)',
                (revision.round_id, revision.tile_id, json.dumps(survey)),
            )
        return cursor.lastrowid

    def get(self, revision_id: int) -> Revision:
        if type(revision_id) is not int or revision_id <= 0:
            raise ValueError('expected a positive revision identifier')
        if revision_id > 2**63 - 1:
            raise KeyError(f'unknown revision: {revision_id}')
        row = self.connection.execute(
            'SELECT round_id, tile_id, survey FROM revisions WHERE revision_id = ?',
            (revision_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f'unknown revision: {revision_id}')
        round_id, tile_id, raw = row
        survey = json.loads(raw)
        return Revision(
            round_id, tile_id, tuple(survey['nodes']),
            tuple(DirectedSegment(**item) for item in survey['segments']),
            tuple(SharedPortal(**item) for item in survey['portals']),
            tuple(EndpointRef(**item) for item in survey['endpoints']),
            revision_id,
        )
