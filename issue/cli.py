from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from closures.history import NoticeDeclaration, NoticeStore
from closures.notices import record
from closures.targets import ClosureTargets
from issue.archive import PackageArchive
from issue.build import issue, reissue
from survey.endpoints import EndpointRef
from survey.imports import register
from survey.portals import SharedPortal
from survey.revisions import RevisionStore
from survey.segments import DirectedSegment


def initialize_source(
    connection: sqlite3.Connection,
) -> tuple[RevisionStore, NoticeStore, PackageArchive]:
    connection.execute('PRAGMA foreign_keys = ON')
    revisions = RevisionStore(connection)
    notices = NoticeStore(connection)
    archive = PackageArchive(connection)
    for store in (revisions, notices, archive):
        store.initialize()
    return revisions, notices, archive


def _document(path: Path, fields: set[str]) -> dict:
    def unique_object(items: list[tuple[str, object]]) -> dict:
        result = dict(items)
        if len(result) != len(items):
            raise ValueError(f'duplicate field in {path.name}')
        return result

    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f'invalid input fields in {path.name}')
    return value


def register_file(store: RevisionStore, path: Path) -> int:
    document = _document(path, {'round', 'tile', 'nodes', 'segments', 'portals', 'endpoints'})
    if not all(isinstance(document[key], list) for key in ('nodes', 'segments')):
        raise ValueError('survey nodes and segments must be arrays')
    if not all(isinstance(document[key], dict) for key in ('portals', 'endpoints')):
        raise ValueError('survey portals and endpoints must be objects')
    segments = []
    for entry in document['segments']:
        if not isinstance(entry, dict) or set(entry) != {'id', 'start', 'end', 'minutes'}:
            raise ValueError('invalid directed segment fields')
        segments.append(DirectedSegment(entry['id'], entry['start'], entry['end'], entry['minutes']))
    return register(
        store, document['round'], document['tile'], document['nodes'], segments,
        (SharedPortal(key, node) for key, node in document['portals'].items()),
        (EndpointRef(key, node) for key, node in document['endpoints'].items()),
    )


def record_file(
    revisions: RevisionStore, notices: NoticeStore, revision_id: int, path: Path
) -> NoticeDeclaration:
    document = _document(path, {'notice', 'segments', 'portals'})
    if not all(isinstance(document[key], list) for key in ('segments', 'portals')):
        raise ValueError('notice targets must be arrays')
    targets = ClosureTargets(tuple(document['segments']), tuple(document['portals']))
    return record(revisions, notices, revision_id, document['notice'], targets)


def _export(raw: bytes, path: Path) -> None:
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix='.piece-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='巡检交班源站')
    parser.add_argument('database', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init')
    commands.add_parser('register').add_argument('survey', type=Path)
    declaration = commands.add_parser('record')
    declaration.add_argument('revision', type=int)
    declaration.add_argument('notice', type=Path)
    issuance = commands.add_parser('issue')
    issuance.add_argument('revision', type=int)
    issuance.add_argument('output', type=Path)
    resend = commands.add_parser('reissue')
    resend.add_argument('package_id')
    resend.add_argument('output', type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        with closing(sqlite3.connect(args.database)) as connection:
            revisions, notices, archive = initialize_source(connection)
            if args.command == 'register':
                result = {'revision_id': register_file(revisions, args.survey)}
            elif args.command == 'record':
                result = asdict(record_file(revisions, notices, args.revision, args.notice))
            elif args.command == 'issue':
                issued = issue(revisions, notices, archive, args.revision)
                try:
                    _export(issued.raw, args.output)
                except OSError as error:
                    raise OSError(f'archived {issued.package_id}; export failed: {error}') from error
                result = {'package_id': issued.package_id}
            elif args.command == 'reissue':
                _export(reissue(archive, args.package_id), args.output)
                result = {'package_id': args.package_id}
            else:
                result = {'database': str(args.database)}
    except (ValueError, KeyError, OSError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
