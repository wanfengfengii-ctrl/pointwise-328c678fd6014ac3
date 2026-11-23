from typing import Iterable

from survey.endpoints import EndpointRef, index_endpoints
from survey.portals import SharedPortal, validate_shared_portals
from survey.revisions import Revision, RevisionStore
from survey.segments import DirectedSegment, require_identifier, validate_directed_segments


def register(
    store: RevisionStore,
    round_id: str,
    tile_id: str,
    nodes: Iterable[str],
    segments: Iterable[DirectedSegment],
    portals: Iterable[SharedPortal],
    endpoints: Iterable[EndpointRef],
) -> int:
    require_identifier(round_id, 'round identifier')
    require_identifier(tile_id, 'tile identifier')
    if isinstance(nodes, (str, bytes)):
        raise ValueError('nodes must be a collection of identifiers')
    ordered_nodes = tuple(nodes)
    for node in ordered_nodes:
        require_identifier(node, 'node identifier')
    known_nodes = set(ordered_nodes)
    if len(known_nodes) != len(ordered_nodes):
        raise ValueError('duplicate node identifier')
    frozen_segments = validate_directed_segments(known_nodes, segments)
    frozen_portals = validate_shared_portals(known_nodes, portals)
    frozen_endpoints = tuple(endpoints)
    index_endpoints(known_nodes, frozen_endpoints, frozen_portals)
    revision = Revision(
        round_id, tile_id, ordered_nodes, frozen_segments, frozen_portals, frozen_endpoints
    )
    return store.save(revision)
