from closures.notices import record
from closures.targets import ClosureTargets
from tests.fixtures import HandoffFixture


class ClosureTests(HandoffFixture):
    def test_unknown_private_target(self):
        revision = self.register_sample('west-5.json')
        with self.assertRaises(ValueError):
            record(self.revisions, self.notices, revision, 'F', ClosureTargets(('missing',)))
        self.assertEqual(self.notice_count(), 0)
        declaration = record(
            self.revisions, self.notices, revision, 'F', ClosureTargets(('west-in-p',))
        )
        self.assertEqual(declaration.targets.segments, ('west-in-p',))
        self.assertEqual(self.notices.get(revision, 'F'), declaration)

    def test_revision_scope(self):
        old = self.register_sample('west-5.json')
        survey = self.sample('west-5.json')
        survey['segments'] = [item for item in survey['segments'] if item['id'] != 'west-by-a']
        new = self.register_survey(survey)
        self.assertIn('west-by-a', [item.segment_id for item in self.revisions.get(old).segments])
        with self.assertRaises(ValueError):
            record(self.revisions, self.notices, new, 'F', ClosureTargets(('west-by-a',)))
        self.assertEqual(self.notice_count(), 0)
        declaration = record(
            self.revisions, self.notices, new, 'F', ClosureTargets(('west-in-p',))
        )
        self.assertEqual(declaration.revision_id, new)
        self.assertEqual(self.notices.for_revision(old), ())
        self.assertEqual(self.notices.for_revision(new), (declaration,))

    def test_portal_scope(self):
        revision = self.east()
        with self.assertRaises(ValueError):
            record(self.revisions, self.notices, revision, 'F', ClosureTargets(portals=('X',)))
        self.assertEqual(self.notice_count(), 0)
        p_closed = ClosureTargets(portals=('P',))
        declaration = record(self.revisions, self.notices, revision, 'F', p_closed)
        self.assertEqual(declaration.targets, p_closed)
        self.assertEqual(record(self.revisions, self.notices, revision, 'F', p_closed), declaration)
        with self.assertRaises(ValueError):
            record(self.revisions, self.notices, revision, 'F', ClosureTargets(portals=('Q',)))
        self.assertEqual(self.notice_count(), 1)
        self.assertEqual(self.notices.get(revision, 'F'), declaration)
