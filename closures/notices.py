from closures.history import NoticeDeclaration, NoticeStore
from closures.targets import ClosureTargets, validate_targets
from survey.revisions import RevisionStore
from survey.segments import require_identifier


def record(
    revisions: RevisionStore,
    notices: NoticeStore,
    revision_id: int,
    notice_id: str,
    targets: ClosureTargets,
) -> NoticeDeclaration:
    if revisions.connection is not notices.connection:
        raise ValueError('revision and notice stores must share the source connection')
    require_identifier(notice_id, 'notice identifier')
    revision = revisions.get(revision_id)
    validated = validate_targets(revision, targets)
    return notices.save(NoticeDeclaration(
        revision.round_id, revision.tile_id, revision_id, notice_id, validated
    ))
