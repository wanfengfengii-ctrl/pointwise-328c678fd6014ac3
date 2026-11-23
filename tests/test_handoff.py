import json

from closures.notices import record
from closures.targets import ClosureTargets
from intake.receipts import receive
from intake.selection import select_packages
from intake.validation import verify_package
from issue.build import reissue
from issue.cli import initialize_source
from issue.envelope import PackageEnvelope, decode_package, encode_package, package_digest
from routing.cli import initialize_offline
from routing.history import read
from routing.search import RouteResult
from tests.fixtures import HandoffFixture


class IntakeTests(HandoffFixture):
    def test_receipt_identity(self):
        piece = self.issue_piece(self.register_sample('west-5.json'))
        first = receive(self.intake, piece.raw)
        self.assertEqual(receive(self.intake, piece.raw), first)
        before = self.receipt_counts()
        self.assertEqual(before, (1, 1))
        envelope = decode_package(piece.raw)
        different = dict(envelope.body, revision=envelope.body['revision'] + 1)
        conflict = encode_package(PackageEnvelope(piece.package_id, different, package_digest(different)))
        self.assertNotEqual(verify_package(conflict).digest, envelope.digest)
        with self.assertRaisesRegex(ValueError, 'identity conflict'):
            receive(self.intake, conflict)
        self.reopen_offline()
        self.assertEqual(self.receipt_counts(), before)
        self.assertEqual(self.intake.get(piece.package_id).raw, piece.raw)
        self.assertEqual(receive(self.intake, piece.raw), first)

    def test_bad_digest(self):
        piece = self.issue_piece(self.register_sample('west-5.json'))
        wire = json.loads(piece.raw)
        wire['body']['round'] = 'other-day'
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            receive(self.intake, json.dumps(wire).encode('utf-8'))
        self.assertEqual(self.receipt_counts(), (0, 0))

    def test_invalid_transfer_reference_with_valid_digest(self):
        piece = self.issue_piece(self.register_sample('west-5.json'))
        envelope = decode_package(piece.raw)
        body = envelope.body
        body['views'][0]['transfers'][0]['end'] = ['portal', 'outside-this-tile']
        raw = encode_package(PackageEnvelope(piece.package_id, body, package_digest(body)))
        with self.assertRaisesRegex(ValueError, 'endpoint reference'):
            receive(self.intake, raw)
        self.assertEqual(self.receipt_counts(), (0, 0))

    def test_frozen_issue_reopen(self):
        old_revision = self.register_sample('west-5.json')
        old = self.issue_piece(old_revision)
        receive(self.intake, old.raw)
        corrected = self.issue_piece(self.register_sample('west-7.json'))
        receive(self.intake, corrected.raw)
        self.assertNotEqual(old.package_id, corrected.package_id)
        self.assertEqual(reissue(self.archive, old.package_id), old.raw)
        with self.assertRaises(KeyError):
            reissue(self.archive, 'never-issued')
        self.disconnect_source()
        selection = select_packages(self.intake, (old.package_id,))
        self.assertEqual(selection.package_ids, (old.package_id,))
        self.assertEqual(selection.packages[0].revision_id, old_revision)
        self.assertEqual(selection.packages[0].raw, old.raw)

    def test_piece_keeps_every_portal_set_alternative(self):
        # The offline piece cannot contain private nodes, so the source must
        # emit both shortest paths between the same public boundary when they
        # traverse different shared portals. Keeping only the shortest one
        # would erase the bypass needed after another tile closes a portal.
        piece = self.issue_piece(self.register_sample('west-5.json'))
        body = decode_package(piece.raw).body
        ordinary = next(view for view in body['views'] if view['notice'] is None)
        s_to_q = {
            tuple(transfer['portals']): transfer['minutes']
            for transfer in ordinary['transfers']
            if transfer['start'] == ['site', 'S'] and transfer['end'] == ['portal', 'Q']
        }
        self.assertEqual(s_to_q, {('P', 'Q'): 2, ('Q',): 5})
        piece_7 = self.issue_piece(self.register_sample('west-7.json'))
        body_7 = decode_package(piece_7.raw).body
        ordinary_7 = next(view for view in body_7['views'] if view['notice'] is None)
        s_to_q_7 = {
            tuple(transfer['portals']): transfer['minutes']
            for transfer in ordinary_7['transfers']
            if transfer['start'] == ['site', 'S'] and transfer['end'] == ['portal', 'Q']
        }
        self.assertEqual(s_to_q_7, {('P', 'Q'): 2, ('Q',): 7})

    def test_private_graph_stays(self):
        revision_id = self.register_sample('west-5.json')
        revision = self.revisions.get(revision_id)
        archived = self.issue_piece(revision_id)
        for identifier in revision.nodes + tuple(item.segment_id for item in revision.segments):
            self.assertNotIn(identifier.encode('utf-8'), archived.raw)
        received = verify_package(archived.raw)
        self.assertEqual(dict(received.sites), {'S': ('site', 'S')})
        self.assertEqual(set(received.portals), {'P', 'Q'})
        self.assertTrue(received.views[0].transfers)

    def test_repeat_init(self):
        west_revision = self.register_sample('west-5.json')
        west = self.issue_piece(west_revision)
        receipt = receive(self.intake, west.raw)
        east = self.publish(self.east())
        user_notice = record(
            self.revisions, self.notices, west_revision, 'USER', ClosureTargets(('west-in-p',))
        )
        later_piece = self.issue_piece(west_revision)
        self.assertNotEqual(west.package_id, later_piece.package_id)
        report = self.dispatch((west.package_id, east), 'USER')
        self.assertEqual(report.result, RouteResult(3, ('P', 'Q')))
        revisions, notices, archive = initialize_source(self.source)
        self.assertEqual(revisions.get(west_revision), self.revisions.get(west_revision))
        self.assertEqual(notices.get(west_revision, 'USER'), user_notice)
        self.assertEqual(reissue(archive, west.package_id), west.raw)
        self.assertEqual(reissue(archive, later_piece.package_id), later_piece.raw)
        self.reopen_offline()
        intake, reports = initialize_offline(self.offline)
        self.assertEqual(receive(intake, west.raw), receipt)
        self.assertEqual(read(reports, report.report_id), report)
        self.assertEqual(self.receipt_counts(), (2, 2))
        self.assertEqual(self.report_counts(), (1, 1))
