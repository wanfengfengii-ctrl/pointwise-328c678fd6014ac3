from dataclasses import asdict, dataclass

from closures.effective import compile_local_closures
from closures.history import NoticeStore
from issue.archive import PackageArchive
from issue.envelope import PackageEnvelope, package_digest
from issue.transfers import build_transfer_evidence
from survey.endpoints import index_endpoints
from survey.revisions import RevisionStore


@dataclass(frozen=True)
class IssuedPackage:
    package_id: str
    raw: bytes


def issue(
    revisions: RevisionStore,
    notices: NoticeStore,
    archive: PackageArchive,
    revision_id: int,
) -> IssuedPackage:
    if revisions.connection is not notices.connection or revisions.connection is not archive.connection:
        raise ValueError('source stores must share one connection')
    revision = revisions.get(revision_id)
    closures = compile_local_closures(revision, notices.for_revision(revision_id))
    index = index_endpoints(set(revision.nodes), revision.endpoints, revision.portals)
    views = []
    for notice_id, closure in closures.items():
        evidence = build_transfer_evidence(revision, index, closure)
        views.append({
            'notice': notice_id,
            'closed_portals': closure.closed_portals,
            'transfers': [asdict(transfer) for transfer in evidence],
        })
    body = {
        'round': revision.round_id, 'tile': revision.tile_id, 'revision': revision_id,
        'portals': [portal.portal_id for portal in revision.portals],
        'sites': index.sites, 'views': views,
    }
    digest = package_digest(body)
    envelope = PackageEnvelope(f'piece-{digest}', body, digest)
    return IssuedPackage(envelope.package_id, archive.save(envelope, revision_id))


def reissue(archive: PackageArchive, package_id: str) -> bytes:
    return archive.get(package_id)
