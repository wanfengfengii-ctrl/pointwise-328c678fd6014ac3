from dataclasses import dataclass
from typing import Iterable

from survey.portals import SharedPortal
from survey.segments import require_identifier

Boundary = tuple[str, str]


@dataclass(frozen=True)
class EndpointRef:
    key: str
    node: str


@dataclass(frozen=True)
class EndpointIndex:
    by_node: dict[str, Boundary]
    sites: dict[str, Boundary]


def index_endpoints(
    nodes: set[str], endpoints: Iterable[EndpointRef], portals: Iterable[SharedPortal]
) -> EndpointIndex:
    by_key = {}
    for endpoint in endpoints:
        if not isinstance(endpoint, EndpointRef):
            raise ValueError('expected a business endpoint')
        require_identifier(endpoint.key, 'endpoint key')
        require_identifier(endpoint.node, 'endpoint node')
        if endpoint.node not in nodes:
            raise ValueError(f'unregistered business endpoint: {endpoint.key}')
        if endpoint.key in by_key:
            raise ValueError(f'duplicate endpoint key: {endpoint.key}')
        by_key[endpoint.key] = endpoint.node

    by_node = {portal.node: ('portal', portal.portal_id) for portal in portals}
    sites = {}
    for key in sorted(by_key):
        node = by_key[key]
        # Aliases of one node share a boundary. Only the public keys leave the station.
        sites[key] = by_node.setdefault(node, ('site', key))
    return EndpointIndex(by_node, sites)
