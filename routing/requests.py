from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from intake.selection import SelectedPackages, select_packages
from intake.store import IntakeStore
from intake.validation import Boundary
from issue.envelope import valid_identifier

NetworkNode = tuple[str, ...]


@dataclass(frozen=True)
class Location:
    key: str
    tile_id: str | None = None


@dataclass(frozen=True)
class RouteRequest:
    selection: SelectedPackages
    start: Location
    end: Location
    notice_id: str | None
    source: NetworkNode
    target: NetworkNode


def network_node(tile_id: str, boundary: Boundary) -> NetworkNode:
    kind, key = boundary
    if kind == 'portal':
        return (kind, key)
    return (kind, tile_id, key)


def _resolve(selection: SelectedPackages, location: Location) -> NetworkNode:
    if not isinstance(location, Location) or not valid_identifier(location.key):
        raise ValueError('invalid route location')
    if location.tile_id is None:
        if any(location.key in package.portals for package in selection.packages):
            return ('portal', location.key)
    else:
        if not valid_identifier(location.tile_id):
            raise ValueError('invalid location tile')
        for package in selection.packages:
            if package.tile_id == location.tile_id:
                boundary = dict(package.sites).get(location.key)
                if boundary is not None:
                    return network_node(package.tile_id, boundary)
                break
    raise ValueError(f'location absent from selected packages: {location}')


def bind_request(
    store: IntakeStore,
    package_ids: Iterable[str],
    start: Location,
    end: Location,
    notice_id: str | None = None,
) -> RouteRequest:
    if notice_id is not None and not valid_identifier(notice_id):
        raise ValueError('expected a single notice identifier')
    selection = select_packages(store, package_ids)
    return RouteRequest(
        selection, start, end, notice_id, _resolve(selection, start), _resolve(selection, end)
    )
