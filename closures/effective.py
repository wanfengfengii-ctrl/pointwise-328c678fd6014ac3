from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from closures.history import NoticeDeclaration
from closures.targets import validate_targets
from survey.revisions import Revision


@dataclass(frozen=True)
class LocalClosureEvidence:
    closed_segments: frozenset[str]
    closed_portals: tuple[str, ...]


def compile_local_closures(
    revision: Revision, declarations: Iterable[NoticeDeclaration]
) -> dict[str | None, LocalClosureEvidence]:
    if revision.revision_id is None:
        raise ValueError('transfer evidence requires a fixed revision')
    result = {None: LocalClosureEvidence(frozenset(), ())}
    identity = (revision.round_id, revision.tile_id, revision.revision_id)
    for declaration in declarations:
        origin = (declaration.round_id, declaration.tile_id, declaration.revision_id)
        if origin != identity or declaration.notice_id in result:
            raise ValueError('inconsistent notice provenance for issuance')
        targets = validate_targets(revision, declaration.targets)
        result[declaration.notice_id] = LocalClosureEvidence(
            frozenset(targets.segments), targets.portals
        )
    return result
