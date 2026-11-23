from intake.store import IntakeStore, Receipt
from intake.validation import verify_package


def receive(store: IntakeStore, raw: bytes) -> Receipt:
    return store.accept(verify_package(raw))
