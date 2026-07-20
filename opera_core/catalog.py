"""Subject-area catalog over the bundled OPERA Cloud RnA GraphQL schemas.

Parses the Oracle-published SDL files shipped under ``opera_core.schemas``
with a small hand-rolled parser (stdlib only) so other tooling can discover
subject areas, their object types, filter inputs, and a starter query.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"

_HEADER_LINE = re.compile(r"^#\s*(\w+)\s*:\s*(.*)$")
_TYPE_START = re.compile(r"^type\s+(\w+)\s*\{")
_INPUT_START = re.compile(r"^input\s+(\w+)\s*\{")
_FIELD_LINE = re.compile(
    r"^\s*(?P<name>[A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*:\s*"
    r"(?P<type>\[?[A-Za-z_]\w*!?\]?!?)\s*(?:@.*)?$"
)
_DOCSTRING = re.compile(r'^\s*"""(?P<text>.*?)"""\s*$')
_COMMENT = re.compile(r"^\s*#\s?(?P<text>.*)$")

_SCALAR_TYPES = {"Int", "Float", "String", "Boolean", "ID", "Date", "DateTime"}


def _base_type(type_name: str) -> str:
    """Strip list/nullability wrappers from a GraphQL type reference."""
    return type_name.replace("[", "").replace("]", "").replace("!", "")


def _parse_header(text: str) -> dict[str, str]:
    """Parse the leading ``# key : value`` metadata block of a schema file."""
    meta: dict[str, str] = {}
    current_key: str | None = None
    for line in text.splitlines():
        if not line.strip():
            if current_key is not None:
                break
            continue
        if not line.startswith("#"):
            break
        match = _HEADER_LINE.match(line)
        if match:
            current_key = match.group(1).lower()
            meta[current_key] = match.group(2).strip().rstrip(",").strip()
        elif current_key:
            continuation = line.lstrip("# ").strip()
            if "This document and all content" in continuation:
                current_key = None
            elif continuation:
                meta[current_key] = f"{meta[current_key]} {continuation}"
    return meta


def _parse_schema(text: str) -> tuple[list[dict], list[str], list[dict]]:
    """Parse SDL into (object_types, filter_input_names, query_root_fields).

    Only plain ``type X { ... }`` blocks become object types; directives,
    scalars, and ``input`` blocks are skipped (input names are collected
    separately as filter inputs). Triple-quoted docstrings and ``#``
    comments directly above a field become that field's description.
    """
    object_types: list[dict] = []
    input_names: list[str] = []
    query_fields: list[dict] = []
    current_type: dict | None = None
    in_query = False
    in_skipped_block = False
    pending: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        type_match = _TYPE_START.match(line)
        if type_match:
            type_name = type_match.group(1)
            in_query = type_name == "Query"
            in_skipped_block = False
            current_type = {
                "name": type_name,
                "description": " ".join(pending).strip(),
                "fields": [],
            }
            pending = []
            if not in_query:
                object_types.append(current_type)
            continue

        input_match = _INPUT_START.match(line)
        if input_match:
            input_names.append(input_match.group(1))
            in_skipped_block = True
            current_type = None
            pending = []
            continue

        if line == "}":
            if in_query and current_type is not None:
                query_fields = current_type["fields"]
            current_type = None
            in_query = False
            in_skipped_block = False
            pending = []
            continue

        if in_skipped_block:
            continue

        if current_type is None:
            doc = _DOCSTRING.match(line) or _COMMENT.match(line)
            if doc and line.strip():
                bit = doc.group("text").strip()
                if bit:
                    pending.append(bit)
            elif line.strip():
                pending = []
            continue

        doc = _DOCSTRING.match(line) or _COMMENT.match(line)
        if doc and line.strip():
            bit = doc.group("text").strip()
            if bit:
                pending.append(bit)
            continue

        field_match = _FIELD_LINE.match(line)
        if field_match:
            type_text = field_match.group("type")
            current_type["fields"].append(
                {
                    "name": field_match.group("name"),
                    "type": type_text,
                    "required": type_text.endswith("!"),
                    "description": " ".join(pending).strip(),
                }
            )
        pending = []

    return object_types, input_names, query_fields


def _build_example_query(
    area_name: str, query_fields: list[dict], object_types: list[dict]
) -> str:
    """Build a plausible minimal query selecting a few fields of the main type."""
    if not query_fields:
        return ""
    root = query_fields[0]
    type_names = {t["name"] for t in object_types}
    main = next(
        (t for t in object_types if t["name"] == _base_type(root["type"])), None
    )
    lines = [
        f"query {area_name}Sample {{",
        f"  {root['name']}(limit: 10, input: {{}}) {{",
    ]
    if main is not None:
        subfield = next(
            (
                f
                for f in main["fields"]
                if _base_type(f["type"]) in type_names
                and _base_type(f["type"]) != main["name"]
            ),
            None,
        )
        if subfield is not None:
            subtype = next(
                t for t in object_types if t["name"] == _base_type(subfield["type"])
            )
            scalars = [
                f["name"]
                for f in subtype["fields"]
                if _base_type(f["type"]) in _SCALAR_TYPES
            ][:3]
            lines.append(f"    {subfield['name']} {{")
            lines.extend(f"      {name}" for name in scalars)
            lines.append("    }")
            main_scalars = [
                f["name"]
                for f in main["fields"]
                if _base_type(f["type"]) in _SCALAR_TYPES
            ][:1]
            lines.extend(f"    {name}" for name in main_scalars)
        else:
            scalars = [
                f["name"]
                for f in main["fields"]
                if _base_type(f["type"]) in _SCALAR_TYPES
            ][:4]
            lines.extend(f"    {name}" for name in scalars)
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    """Parse every bundled schema once and cache the results by area name."""
    areas: dict[str, dict] = {}
    for path in sorted(SCHEMAS_DIR.glob("*.graphql")):
        text = path.read_text(encoding="utf-8")
        meta = _parse_header(text)
        if "title" not in meta:
            # base.graphql is bundled for completeness, not a subject area.
            continue
        object_types, input_names, query_fields = _parse_schema(text)
        areas[path.stem] = {
            "meta": meta,
            "object_types": object_types,
            "filter_inputs": input_names,
            "query_fields": query_fields,
        }
    return areas


def list_subject_areas() -> list[dict]:
    """List all bundled subject areas with name, title, description, version."""
    return [
        {
            "name": name,
            "title": entry["meta"].get("title", ""),
            "description": entry["meta"].get("description", ""),
            "version": entry["meta"].get("version", ""),
        }
        for name, entry in sorted(_index().items())
    ]


def describe_subject_area(name: str) -> dict:
    """Describe one subject area: metadata, object types, filter inputs, sample query.

    Raises KeyError listing the valid names when ``name`` is unknown.
    """
    index = _index()
    if name not in index:
        lowered = {key.lower(): key for key in index}
        if name.lower() in lowered:
            name = lowered[name.lower()]
        else:
            valid = ", ".join(sorted(index))
            raise KeyError(
                f"Unknown subject area {name!r}. Valid subject areas: {valid}"
            )
    entry = index[name]
    meta = entry["meta"]
    return {
        "name": name,
        "title": meta.get("title", ""),
        "description": meta.get("description", ""),
        "version": meta.get("version", ""),
        "object_types": entry["object_types"],
        "filter_inputs": entry["filter_inputs"],
        "example_query": _build_example_query(
            name, entry["query_fields"], entry["object_types"]
        ),
    }
