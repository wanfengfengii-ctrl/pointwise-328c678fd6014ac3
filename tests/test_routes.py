import sqlite3

from closures.notices import record
from closures.targets import ClosureTargets
from issue.cli import record_file
from routing.history import read
from routing.requests import Location
from routing.search import RouteResult
from tests.fixtures import HandoffFixture, SAMPLES


class RouteTests(HandoffFixture):
    def test_normal_crossing(self):
        west = self.publish(self.register_sample('west-5.json'))
        east = self.publish(self.east())
        self.disconnect_source()
        report = self.dispatch((west, east))
        self.assertEqual(report.result, RouteResult(3, ('P', 'Q')))
        self.assertTrue(report.result.reachable)
        self.assertEqual(report.package_ids, (west, east))
        self.assertEqual(read(self.reports, report.report_id), report)

    def test_remote_portal_closure(self):
        west_5 = self.publish(self.register_sample('west-5.json'))
        west_7 = self.publish(self.register_sample('west-7.json'))
        east_open = self.publish(self.east())
        east_closed = self.publish(self.east(closed=True))
        self.disconnect_source()
        ordinary = self.dispatch((west_5, east_open), 'F')
        self.assertEqual(ordinary.result, RouteResult(3, ('P', 'Q')))
        self.assertEqual(self.dispatch((west_7, east_closed)).result, RouteResult(3, ('P', 'Q')))
        for west, minutes in ((west_5, 6), (west_7, 8)):
            with self.subTest(minutes=minutes):
                result = self.dispatch((west, east_closed), 'F')
                self.assertEqual(result.result, RouteResult(minutes, ('Q',)))
                self.assertEqual(result.package_ids, (west, east_closed))
        restored = self.dispatch((west_5, east_open), 'F')
        self.assertEqual(restored.result, RouteResult(3, ('P', 'Q')))
        self.assertNotEqual(restored.report_id, ordinary.report_id)

    def test_unreachable_and_history(self):
        west = self.publish(self.register_sample('west-5.json'))
        survey = self.sample('west-5.json')
        survey['segments'] = survey['segments'][:2]
        no_bypass = self.publish(self.register_survey(survey))
        east = self.publish(self.east(closed=True))
        self.disconnect_source()
        old = self.dispatch((west, east), 'F')
        self.assertEqual(old.result, RouteResult(6, ('Q',)))
        lost = self.dispatch((no_bypass, east), 'F')
        self.assertNotEqual(old.report_id, lost.report_id)
        self.assertEqual(lost.result, RouteResult(None, ()))
        self.assertFalse(lost.result.reachable)
        self.reopen_offline()
        self.assertEqual(read(self.reports, old.report_id), old)
        self.assertEqual(read(self.reports, lost.report_id), lost)
        with self.assertRaises(KeyError):
            read(self.reports, 9999)

    def test_failed_signoff(self):
        west = self.publish(self.register_sample('west-5.json'))
        east = self.publish(self.east())
        survey = self.sample('east.json')
        survey['round'] = 'day-2'
        other_round = self.publish(self.register_survey(survey))
        self.disconnect_source()
        original = self.dispatch((west, east))
        before = self.report_counts()
        self.assertEqual(before, (1, 1))
        with self.assertRaisesRegex(ValueError, 'mix rounds'):
            self.dispatch((west, other_round))
        self.assertEqual(self.report_counts(), before)
        with self.assertRaisesRegex(KeyError, 'not received'):
            self.dispatch((west, 'missing-piece'))
        self.assertEqual(self.report_counts(), before)
        with self.offline:
            self.offline.execute('''
                CREATE TRIGGER reject_report_receipt BEFORE INSERT ON report_receipts
                BEGIN SELECT RAISE(ABORT, 'receipt ledger rejected signoff'); END
            ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'rejected signoff'):
            self.dispatch((west, east))
        self.reopen_offline()
        self.assertEqual(self.report_counts(), before)
        self.assertEqual(read(self.reports, original.report_id), original)
        with self.assertRaises(KeyError):
            read(self.reports, original.report_id + 1)
        with self.offline:
            self.offline.execute('DROP TRIGGER reject_report_receipt')
        after = self.dispatch((west, east))
        self.assertEqual(after.result, original.result)
        self.assertEqual(self.report_counts(), (2, 2))

    def test_internal_closure_is_specific_to_one_notice(self):
        west_revision = self.register_sample('west-5.json')
        record(self.revisions, self.notices, west_revision, 'F', ClosureTargets(('west-in-p',)))
        record(self.revisions, self.notices, west_revision, 'EMPTY', ClosureTargets())
        west = self.publish(west_revision)
        east = self.publish(self.east())
        self.disconnect_source()
        for notice in (None, 'EMPTY', 'UNDECLARED'):
            with self.subTest(notice=notice):
                self.assertEqual(self.dispatch((west, east), notice).result, RouteResult(3, ('P', 'Q')))
        self.assertEqual(self.dispatch((west, east), 'F').result, RouteResult(6, ('Q',)))

    def test_portal_closure_includes_start_end_and_same_point(self):
        survey = self.sample('west-5.json')
        survey['endpoints']['at-p'] = survey['portals']['P']
        west = self.publish(self.register_survey(survey))
        east = self.publish(self.east(closed=True))
        self.disconnect_source()
        ids = (west, east)
        p = Location('P')
        at_p = Location('at-p', 'west')
        self.assertEqual(self.dispatch(ids, start=at_p, end=p).result, RouteResult(0, ('P',)))
        self.assertEqual(self.dispatch(ids, start=p).result, RouteResult(2, ('P', 'Q')))
        self.assertEqual(self.dispatch(ids, end=p).result, RouteResult(1, ('P',)))
        for args in ({'start': p}, {'end': p}, {'start': p, 'end': p}):
            with self.subTest(args=args):
                self.assertEqual(self.dispatch(ids, 'F', **args).result, RouteResult(None, ()))

    def test_remote_closure_blocks_same_tile_passage_elsewhere(self):
        # A portal closed by one selected piece must block passage through that
        # portal inside every other tile too, not only inside the declaring tile.
        west = self.publish(self.register_sample('west-5.json'))
        survey = self.sample('east.json')
        survey['segments'].append(
            {'id': 'east-p-q', 'start': 'east-private-p', 'end': 'east-private-q', 'minutes': 4}
        )
        east_revision = self.register_survey(survey)
        record_file(self.revisions, self.notices, east_revision, SAMPLES / 'east-f.json')
        east = self.publish(east_revision)
        self.disconnect_source()
        # Without F, east may travel P->Q->T: west 2 plus east 4+1.
        self.assertEqual(
            self.dispatch((west, east)).result, RouteResult(3, ('P', 'Q'))
        )
        # With F, P is closed journey-wide; east cannot enter P and west must
        # use its bypass: west 5 plus the open east Q->T leg of 1.
        self.assertEqual(
            self.dispatch((west, east), 'F').result, RouteResult(6, ('Q',))
        )

    def test_duplicate_tile_or_unknown_location_never_signs(self):
        west_5 = self.publish(self.register_sample('west-5.json'))
        west_7 = self.publish(self.register_sample('west-7.json'))
        east = self.publish(self.east())
        self.disconnect_source()
        with self.assertRaisesRegex(ValueError, 'one revision'):
            self.dispatch((west_5, west_7, east))
        with self.assertRaisesRegex(ValueError, 'absent'):
            self.dispatch((west_5, east), end=Location('unknown', 'east'))
        self.assertEqual(self.report_counts(), (0, 0))
