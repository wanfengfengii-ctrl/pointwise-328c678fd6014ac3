import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class PackageEnvelope:
    package_id: str
    body: dict
    digest: str


def valid_identifier(value: object) -> bool:
    return isinstance(value, str) and value.isprintable() and value == value.strip()


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def package_digest(body: dict) -> str:
    return hashlib.sha256(_canonical(body)).hexdigest()


def encode_package(envelope: PackageEnvelope) -> bytes:
    return _canonical({
        'version': 1, 'package_id': envelope.package_id,
        'digest': envelope.digest, 'body': envelope.body,
    })


def _unique_object(items: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'duplicate package field: {key}')
        result[key] = value
    return result


def _invalid_number(value: str) -> None:
    raise ValueError(f'invalid package number: {value}')


def decode_package(raw: bytes) -> PackageEnvelope:
    if not isinstance(raw, bytes):
        raise ValueError('a package must be supplied as bytes')
    try:
        outer = json.loads(
            raw.decode('utf-8'), object_pairs_hook=_unique_object, parse_constant=_invalid_number
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid package encoding') from error
    if not isinstance(outer, dict) or set(outer) != {'version', 'package_id', 'body', 'digest'}:
        raise ValueError('invalid package envelope')
    if type(outer['version']) is not int or outer['version'] != 1:
        raise ValueError('unsupported package version')
    if not valid_identifier(outer['package_id']) or not isinstance(outer['body'], dict):
        raise ValueError('invalid package identity or body')
    if outer['digest'] != package_digest(outer['body']):
        raise ValueError('package digest mismatch')
    return PackageEnvelope(outer['package_id'], outer['body'], outer['digest'])
