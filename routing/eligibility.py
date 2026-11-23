from collections import defaultdict
from dataclasses import dataclass

from routing.requests import NetworkNode, RouteRequest, network_node


@dataclass(frozen=True)
class Connection:
    target: NetworkNode
    minutes: int
    portals: tuple[str, ...]


@dataclass(frozen=True)
class EligibleNetwork:
    source: NetworkNode
    target: NetworkNode
    edges: dict[NetworkNode, tuple[Connection, ...]]
    closed_portals: frozenset[str]


def build_eligible_network(request: RouteRequest) -> EligibleNetwork:
    selected_views = []
    for package in request.selection.packages:
        views = {view.notice_id: view for view in package.views}
        selected_views.append((package.tile_id, views.get(request.notice_id, views[None])))
    # A portal closed by any selected piece is closed for the whole journey,
    # including start, end and same-tile passage in every other tile.
    closed_portals = frozenset(portal for _, view in selected_views for portal in view.closed_portals)
    edges = defaultdict(list)
    for tile_id, view in selected_views:
        for transfer in view.transfers:
            if closed_portals.isdisjoint(transfer.portals):
                origin = network_node(tile_id, transfer.start)
                target = network_node(tile_id, transfer.end)
                edges[origin].append(Connection(target, transfer.minutes, transfer.portals))
    return EligibleNetwork(
        request.source, request.target,
        {origin: tuple(connections) for origin, connections in edges.items()},
        closed_portals,
    )
