from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DirectedSegment:
    segment_id: str
    start: str
    end: str
    minutes: int


def require_identifier(value: object, description: str) -> None:
    if not isinstance(value, str) or not value.isprintable() or value != value.strip():
        raise ValueError(f'invalid {description}')


def validate_directed_segments(
    nodes: set[str], segments: Iterable[DirectedSegment]
) -> tuple[DirectedSegment, ...]:
    validated = []
    seen = set()
    for segment in segments:
        if not isinstance(segment, DirectedSegment):
            raise ValueError('expected a directed segment')
        require_identifier(segment.segment_id, 'segment identifier')
        require_identifier(segment.start, 'segment start')
        require_identifier(segment.end, 'segment end')
        if segment.segment_id in seen:
            raise ValueError(f'duplicate segment: {segment.segment_id}')
        if segment.start not in nodes or segment.end not in nodes:
            raise ValueError(f'unregistered endpoint on segment: {segment.segment_id}')
        if type(segment.minutes) is not int or segment.minutes <= 0:
            raise ValueError(f'invalid minutes on segment: {segment.segment_id}')
        seen.add(segment.segment_id)
        validated.append(segment)
    return tuple(validated)
