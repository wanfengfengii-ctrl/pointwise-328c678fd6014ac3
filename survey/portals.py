from dataclasses import dataclass
from typing import Iterable

from survey.segments import require_identifier


@dataclass(frozen=True)
class SharedPortal:
    portal_id: str
    node: str


def validate_shared_portals(
    nodes: set[str], portals: Iterable[SharedPortal]
) -> tuple[SharedPortal, ...]:
    by_id = {}
    assigned_nodes = set()
    for portal in portals:
        if not isinstance(portal, SharedPortal):
            raise ValueError('expected a shared portal')
        require_identifier(portal.portal_id, 'portal identifier')
        require_identifier(portal.node, 'portal node')
        if portal.node not in nodes:
            raise ValueError(f'unregistered portal node: {portal.node}')
        if portal.portal_id in by_id or portal.node in assigned_nodes:
            raise ValueError(f'duplicate portal placement: {portal.portal_id}')
        by_id[portal.portal_id] = portal
        assigned_nodes.add(portal.node)
    return tuple(by_id[key] for key in sorted(by_id))
