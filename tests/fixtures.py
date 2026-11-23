import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intake.receipts import receive
from issue.build import issue
from issue.cli import initialize_source, record_file, register_file
from routing.cli import initialize_offline
from routing.reports import route
from routing.requests import Location
from survey.endpoints import EndpointRef
from survey.imports import register
from survey.portals import SharedPortal
from survey.segments import DirectedSegment

SAMPLES = Path(__file__).resolve().parents[1] / 'samples'
START = Location('S', 'west')
END = Location('T', 'east')


class HandoffFixture(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix='patrol-tests-')
        self.addCleanup(directory.cleanup)
        self.source_path = Path(directory.name) / 'source.sqlite'
        self.offline_path = Path(directory.name) / 'offline.sqlite'
        self.source = sqlite3.connect(self.source_path)
        self.addCleanup(self.source.close)
        self.revisions, self.notices, self.archive = initialize_source(self.source)
        self.reopen_offline()

    def reopen_offline(self):
        if hasattr(self, 'offline'):
            self.offline.close()
        self.offline = sqlite3.connect(self.offline_path)
        self.addCleanup(self.offline.close)
        self.intake, self.reports = initialize_offline(self.offline)

    def disconnect_source(self):
        self.source.close()
        self.source_path.unlink()
        self.assertFalse(self.source_path.exists())
        self.reopen_offline()

    def sample(self, name):
        return json.loads((SAMPLES / name).read_text(encoding='utf-8'))

    def register_sample(self, name):
        return register_file(self.revisions, SAMPLES / name)

    def register_survey(self, survey):
        return register(
            self.revisions, survey['round'], survey['tile'], survey['nodes'],
            [DirectedSegment(item['id'], item['start'], item['end'], item['minutes'])
             for item in survey['segments']],
            [SharedPortal(key, node) for key, node in survey['portals'].items()],
            [EndpointRef(key, node) for key, node in survey['endpoints'].items()],
        )

    def east(self, closed=False):
        revision_id = self.register_sample('east.json')
        if closed:
            record_file(self.revisions, self.notices, revision_id, SAMPLES / 'east-f.json')
        return revision_id

    def issue_piece(self, revision_id):
        return issue(self.revisions, self.notices, self.archive, revision_id)

    def publish(self, revision_id):
        return receive(self.intake, self.issue_piece(revision_id).raw).package_id

    def dispatch(self, packages, notice=None, start=START, end=END):
        return route(self.intake, self.reports, packages, start, end, notice)

    def report_counts(self):
        return (
            self.offline.execute('SELECT count(*) FROM reports').fetchone()[0],
            self.offline.execute('SELECT count(*) FROM report_receipts').fetchone()[0],
        )

    def receipt_counts(self):
        return (
            self.offline.execute('SELECT count(*) FROM received_packages').fetchone()[0],
            self.offline.execute('SELECT count(*) FROM receipts').fetchone()[0],
        )

    def notice_count(self):
        return self.source.execute('SELECT count(*) FROM notices').fetchone()[0]
