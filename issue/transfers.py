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
) -> dict[str, tuple[tuple[int, tuple[str, ...]], ...]]:
    # Keep the cheapest path for every distinct set of shared portals traversed.
    # A path that visits fewer (or simply different) portals may be the only
    # usable route when another tile declares one of those portals closed.
    labels: dict[str, dict[frozenset[str], tuple[int, tuple[str, ...]]]] = {origin: {}}
    start_trace = (portal_at[origin],) if origin in portal_at else ()
    labels[origin][frozenset(start_trace)] = (0, start_trace)
    queue = [(0, origin, start_trace)]
    while queue:
        minutes, node, trace = heappop(queue)
        stamp = labels[node].get(frozenset(trace))
        if stamp != (minutes, trace):
            continue
        for end, duration in neighbors.get(node, ()):
            next_trace = trace + (portal_at[end],) if end in portal_at else trace
            next_portals = frozenset(next_trace)
            total = minutes + duration
            node_labels = labels.setdefault(end, {})
            previous = node_labels.get(next_portals)
            if previous is not None and previous[0] <= total:
                continue
            # A known path that traverses a subset of these portals and is no
            # more expensive dominates this label under every portal closure.
            if any(
                known_portals <= next_portals and known[0] <= total
                for known_portals, known in node_labels.items()
            ):
                continue
            node_labels[next_portals] = (total, next_trace)
            heappush(queue, (total, end, next_trace))
    return {
        node: tuple(sorted(node_labels.values()))
        for node, node_labels in labels.items()
    }


def build_transfer_evidence(
    revision: Revision, endpoints: EndpointIndex, closure: LocalClosureEvidence
) -> tuple[TransferEvidence, ...]:
    neighbors: dict[str, list[tuple[str, int]]] = {}
    for segment in revision.segments:
        if segment.segment_id not in closure.closed_segments:
            neighbors.setdefault(segment.start, []).append((segment.end, segment.minutes))
    at_boundary = endpoints.by_node
    portal_at = {node: key for node, (kind, key) in at_boundary.items() if kind == 'portal'}
    ordered = sorted(at_boundary.items(), key=lambda item: item[1])
    transfers = []
    for origin, start in ordered:
        paths = _local_paths(neighbors, portal_at, origin)
        for target, end in ordered:
            if origin == target or target not in paths:
                continue
            for minutes, trace in paths[target]:
                transfers.append(TransferEvidence(start, end, minutes, trace))
    return tuple(sorted(transfers, key=lambda transfer: (
        transfer.start, transfer.end, transfer.minutes, transfer.portals
    )))
