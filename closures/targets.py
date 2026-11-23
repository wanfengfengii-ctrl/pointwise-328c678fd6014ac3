from dataclasses import dataclass

from survey.revisions import Revision
from survey.segments import require_identifier


@dataclass(frozen=True)
class ClosureTargets:
    segments: tuple[str, ...] = ()
    portals: tuple[str, ...] = ()


def _validate_ids(values: tuple[str, ...], valid: set[str], kind: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f'{kind} targets must be a collection')
    identifiers = set()
    for value in values:
        require_identifier(value, f'{kind} target')
        if value not in valid:
            raise ValueError(f'unknown {kind} in the specified revision: {value}')
        identifiers.add(value)
    return tuple(sorted(identifiers))


def validate_targets(revision: Revision, targets: ClosureTargets) -> ClosureTargets:
    if not isinstance(targets, ClosureTargets):
        raise ValueError('expected closure targets')
    return ClosureTargets(
        _validate_ids(targets.segments, {s.segment_id for s in revision.segments}, 'segment'),
        _validate_ids(targets.portals, {p.portal_id for p in revision.portals}, 'portal'),
    )
