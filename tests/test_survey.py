from routing.requests import Location
from routing.search import RouteResult
from survey.endpoints import EndpointRef
from survey.imports import register
from survey.portals import SharedPortal
from survey.segments import DirectedSegment
from tests.fixtures import HandoffFixture


class SurveyTests(HandoffFixture):
    def test_invalid_directed_segment(self):
        bad = (
            DirectedSegment('L', 'a', 'missing', 2),
            DirectedSegment('L', 'a', 'b', 0),
            DirectedSegment('L', 'a', 'b', -1),
            DirectedSegment('L', 'a', 'b', True),
            DirectedSegment('L', 'a', 'b', 2.0),
        )
        for segment in bad:
            with self.subTest(segment=segment), self.assertRaises(ValueError):
                register(self.revisions, 'shift', 'west', ('a', 'b'), (segment,), (), ())
        count = self.source.execute('SELECT count(*) FROM revisions').fetchone()[0]
        self.assertEqual(count, 0)

    def test_directed_only(self):
        forward = DirectedSegment('L', 'a', 'b', 2)
        rev = register(
            self.revisions, 'shift', 'west', ('a', 'b'), (forward,), (),
            (EndpointRef('A', 'a'), EndpointRef('B', 'b')),
        )
        self.assertEqual(self.revisions.get(rev).segments, (forward,))
        piece = self.publish(rev)
        self.disconnect_source()
        start, end = Location('A', 'west'), Location('B', 'west')
        self.assertEqual(self.dispatch((piece,), start=start, end=end).result, RouteResult(2, ()))
        self.assertEqual(self.dispatch((piece,), start=end, end=start).result, RouteResult(None, ()))

    def test_invalid_public_location_does_not_register(self):
        with self.assertRaises(ValueError):
            register(self.revisions, 'shift', 'west', ('a',), (), (SharedPortal('P', 'missing'),), ())
        with self.assertRaises(ValueError):
            register(self.revisions, 'shift', 'west', ('a',), (), (), (EndpointRef('A', 'missing'),))
        self.assertEqual(self.source.execute('SELECT count(*) FROM revisions').fetchone()[0], 0)
