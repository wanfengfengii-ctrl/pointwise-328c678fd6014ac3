from __future__ import annotations

from dataclasses import dataclass

from issue.envelope import decode_package, valid_identifier

Boundary = tuple[str, str]


@dataclass(frozen=True)
class VerifiedTransfer:
    start: Boundary
    end: Boundary
    minutes: int
    portals: tuple[str, ...]


@dataclass(frozen=True)
class VerifiedView:
    notice_id: str | None
    closed_portals: tuple[str, ...]
    transfers: tuple[VerifiedTransfer, ...]


@dataclass(frozen=True)
class VerifiedPackage:
    package_id: str
    digest: str
    round_id: str
    tile_id: str
    revision_id: int
    portals: tuple[str, ...]
    sites: tuple[tuple[str, Boundary], ...]
    views: tuple[VerifiedView, ...]
    raw: bytes


def _fields(value: object, expected: set[str], description: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f'invalid {description} fields')
    return value


def _identifiers(value: object, description: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(valid_identifier(item) for item in value):
        raise ValueError(f'invalid {description} identifiers')
    return tuple(value)


def _boundary(value: object) -> Boundary:
    if (not isinstance(value, list) or len(value) != 2
            or value[0] not in ('site', 'portal') or not valid_identifier(value[1])):
        raise ValueError('invalid transfer boundary')
    return (value[0], value[1])


def _sites(value: object, portals: set[str]) -> dict[str, Boundary]:
    if not isinstance(value, dict) or not all(valid_identifier(key) for key in value):
        raise ValueError('invalid site table')
    sites = {key: _boundary(target) for key, target in value.items()}
    for kind, key in sites.values():
        valid = key in portals if kind == 'portal' else sites.get(key) == (kind, key)
        if not valid:
            raise ValueError(f'unknown public boundary: {key}')
    return sites


def _transfer(value: object, boundaries: set[Boundary], portals: set[str]) -> VerifiedTransfer:
    item = _fields(value, {'start', 'end', 'minutes', 'portals'}, 'transfer')
    start, end = _boundary(item['start']), _boundary(item['end'])
    if start == end or start not in boundaries or end not in boundaries:
        raise ValueError('invalid transfer endpoint reference')
    minutes = item['minutes']
    if type(minutes) is not int or minutes <= 0:
        raise ValueError('invalid transfer minutes')
    trace = _identifiers(item['portals'], 'transfer portal')
    if not set(trace) <= portals:
        raise ValueError('transfer references a portal outside this tile')
    if start[0] == 'portal' and trace[:1] != (start[1],):
        raise ValueError('transfer trace omits its starting portal')
    if end[0] == 'portal' and trace[-1:] != (end[1],):
        raise ValueError('transfer trace omits its ending portal')
    return VerifiedTransfer(start, end, minutes, trace)


def _views(value: object, boundaries: set[Boundary], portals: set[str]) -> tuple[VerifiedView, ...]:
    if not isinstance(value, list):
        raise ValueError('invalid package views')
    views = []
    seen = set()
    for entry in value:
        view = _fields(entry, {'notice', 'closed_portals', 'transfers'}, 'view')
        notice_id = view['notice']
        if notice_id is not None and not valid_identifier(notice_id):
            raise ValueError('invalid notice identifier')
        if notice_id in seen:
            raise ValueError('duplicate notice view')
        seen.add(notice_id)
        closed = _identifiers(view['closed_portals'], 'closed portal')
        if len(set(closed)) != len(closed) or not set(closed) <= portals:
            raise ValueError('invalid closed portal reference')
        if notice_id is None and closed:
            raise ValueError('the ordinary view cannot declare a closure')
        if not isinstance(view['transfers'], list):
            raise ValueError('invalid view transfers')
        transfers = tuple(_transfer(item, boundaries, portals) for item in view['transfers'])
        views.append(VerifiedView(notice_id, closed, transfers))
    if None not in seen:
        raise ValueError('package has no ordinary view')
    return tuple(views)


def verify_package(raw: bytes) -> VerifiedPackage:
    envelope = decode_package(raw)
    body = _fields(envelope.body, {'round', 'tile', 'revision', 'portals', 'sites', 'views'}, 'body')
    round_id, tile_id, revision_id = body['round'], body['tile'], body['revision']
    if not valid_identifier(round_id) or not valid_identifier(tile_id):
        raise ValueError('invalid package provenance')
    if type(revision_id) is not int or revision_id <= 0:
        raise ValueError('invalid package revision')
    portals = _identifiers(body['portals'], 'portal')
    portal_set = set(portals)
    if len(portal_set) != len(portals):
        raise ValueError('duplicate portal identifier')
    sites = _sites(body['sites'], portal_set)
    boundaries = set(sites.values()) | {('portal', key) for key in portals}
    views = _views(body['views'], boundaries, portal_set)
    return VerifiedPackage(
        envelope.package_id, envelope.digest, round_id, tile_id, revision_id,
        portals, tuple(sorted(sites.items())), views, raw,
    )
