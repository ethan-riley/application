from __future__ import annotations

import re

_TAG_RE = re.compile(
    r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?:[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$'
)
_MAX_TAGS = 10
_MAX_PART_LEN = 64


def validate_tag(tag: str) -> bool:
    if not _TAG_RE.match(tag):
        return False
    key, _, val = tag.partition(":")
    return len(key) <= _MAX_PART_LEN and len(val) <= _MAX_PART_LEN


def parse_header_tags(header_value: str | None) -> list[str]:
    if not isinstance(header_value, str) or not header_value:
        return []
    return [t.strip() for t in header_value.split(",") if t.strip() and validate_tag(t.strip())]


def merge_tags(header_tags: list[str], body_tags: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for tag in header_tags + body_tags:
        if not validate_tag(tag):
            continue
        key, _, _ = tag.partition(":")
        if key not in seen:
            seen[key] = tag
    return list(seen.values())[:_MAX_TAGS]
