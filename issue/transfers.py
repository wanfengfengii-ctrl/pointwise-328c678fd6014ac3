from collections import defaultdict
from dataclasses import dataclass
from heapq import heappop, heappush

from closures.effective import LocalClosureEvidence
from survey.endpoints import Boundary, EndpointIndex
from survey.revisions import Revision


@dataclass(frozen=True)
class TransferEvidence:
    start: Boundary
    end: Boundary
    minutes: int
    portals: tuple[str, ...]


def _local_paths(
    neighbors: dict[str, list[tuple[str, int]]],
    portal_at: dict[str, str],
    origin: str,
) -> dict[str, tuple[int, tuple[str, ...]]]:
    trace = (portal_at[origin],) if origin in portal_at else ()
    best = {origin: (0, trace)}
    queue = [(0, origin, trace)]
    while queue:
        minutes, node, trace = heappop(queue)
        if best[node] != (minutes, trace):
            continue
        for end, duration in neighbors.get(node, ()):
            total = minutes + duration
            previous = best.get(end)
            if previous is not None and previous[0] <= total:
                continue
            next_trace = trace + (portal_at[end],) if end in portal_at else trace
            best[end] = (total, next_trace)
            heappush(queue, (total, end, next_trace))
    return best


def build_transfer_evidence(
    revision: Revision, endpoints: EndpointIndex, closure: LocalClosureEvidence
) -> tuple[TransferEvidence, ...]:
    neighbors = defaultdict(list)
    for segment in revision.segments:
        if segment.segment_id not in closure.closed_segments:
            neighbors[segment.start].append((segment.end, segment.minutes))
    at_boundary = endpoints.by_node
    portal_at = {node: key for node, (kind, key) in at_boundary.items() if kind == 'portal'}
    ordered = sorted(at_boundary.items(), key=lambda item: item[1])
    transfers = []
    for origin, start in ordered:
        paths = _local_paths(neighbors, portal_at, origin)
        for target, end in ordered:
            if origin == target:
                continue
            if target in paths:
                minutes, trace = paths[target]
                transfers.append(TransferEvidence(start, end, minutes, trace))
    return tuple(transfers)
