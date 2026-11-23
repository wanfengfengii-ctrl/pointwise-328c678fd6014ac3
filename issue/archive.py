import sqlite3

from issue.envelope import PackageEnvelope, encode_package, valid_identifier


class PackageArchive:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        with self.connection:
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS issued_packages (
                    package_id TEXT PRIMARY KEY,
                    revision_id INTEGER NOT NULL REFERENCES revisions(revision_id),
                    raw BLOB NOT NULL
                )
            ''')

    def save(self, envelope: PackageEnvelope, revision_id: int) -> bytes:
        raw = encode_package(envelope)
        with self.connection:
            self.connection.execute('''
                INSERT INTO issued_packages (package_id, revision_id, raw) VALUES (?, ?, ?)
                ON CONFLICT (package_id) DO NOTHING
            ''', (envelope.package_id, revision_id, raw))
            stored = self.connection.execute(
                'SELECT revision_id, raw FROM issued_packages WHERE package_id = ?',
                (envelope.package_id,),
            ).fetchone()
            if stored != (revision_id, raw):
                raise ValueError(f'conflicting issue identity: {envelope.package_id}')
        return raw

    def get(self, package_id: str) -> bytes:
        if not valid_identifier(package_id):
            raise ValueError('invalid package identifier')
        row = self.connection.execute(
            'SELECT raw FROM issued_packages WHERE package_id = ?', (package_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f'unknown issued package: {package_id}')
        return row[0]
