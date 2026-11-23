from dataclasses import dataclass
from typing import Iterable

from intake.store import IntakeStore
from intake.validation import VerifiedPackage
from issue.envelope import valid_identifier


@dataclass(frozen=True)
class SelectedPackages:
    round_id: str
    package_ids: tuple[str, ...]
    packages: tuple[VerifiedPackage, ...]


def select_packages(store: IntakeStore, package_ids: Iterable[str]) -> SelectedPackages:
    if isinstance(package_ids, (str, bytes)):
        raise ValueError('selection must be a collection of package identifiers')
    ids = tuple(package_ids)
    if not ids or not all(valid_identifier(package_id) for package_id in ids):
        raise ValueError('invalid or empty package selection')
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate package in selection')
    packages = store.get_selected(ids)
    round_id = packages[0].round_id
    if any(package.round_id != round_id for package in packages):
        raise ValueError('selected packages mix rounds')
    if len({package.tile_id for package in packages}) != len(packages):
        raise ValueError('select exactly one revision for each included tile')
    return SelectedPackages(round_id, ids, packages)
