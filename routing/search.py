from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush

from routing.eligibility import Connection, EligibleNetwork
from routing.requests import NetworkNode


@dataclass(frozen=True)
class RouteResult:
    minutes: int | None
    portals: tuple[str, ...]

    @property
    def reachable(self) -> bool:
        return self.minutes is not None


def _trace(
    previous: dict[NetworkNode, tuple[NetworkNode, Connection]],
    source: NetworkNode,
    target: NetworkNode,
) -> tuple[str, ...]:
    legs = []
    while target != source:
        start, edge = previous[target]
        legs.append((start, edge.portals))
        target = start
    if not legs:
        return (source[1],) if source[0] == 'portal' else ()
    portals = []
    for start, trace in reversed(legs):
        if portals and start[0] == 'portal':
            portals.extend(trace[1:])
        else:
            portals.extend(trace)
    return tuple(portals)


def shortest_route(network: EligibleNetwork) -> RouteResult:
    source, target = network.source, network.target
    if any(node[0] == 'portal' and node[1] in network.closed_portals for node in (source, target)):
        return RouteResult(None, ())
    distance = {source: 0}
    previous = {}
    queue = [(0, source)]
    while queue:
        minutes, node = heappop(queue)
        if distance[node] != minutes:
            continue
        if node == target:
            return RouteResult(minutes, _trace(previous, source, target))
        for edge in network.edges.get(node, ()):
            total = minutes + edge.minutes
            old = distance.get(edge.target)
            if old is None or total < old:
                distance[edge.target] = total
                previous[edge.target] = (node, edge)
                heappush(queue, (total, edge.target))
    return RouteResult(None, ())
