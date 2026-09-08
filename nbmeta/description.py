"""Merge logic for a JSON payload embedded at the start of a NetBox description field."""
import json


def split_leading_json(description):
    """Split a description into (leading JSON object, remainder). ({}, description) if none."""
    if not description:
        return {}, ""
    try:
        obj, end = json.JSONDecoder().raw_decode(description)
    except json.JSONDecodeError:
        return {}, description
    if not isinstance(obj, dict):
        return {}, description
    return obj, description[end:]


def merge_description(description, new_data, defaults=None):
    """Shallow-merge new_data into any JSON object leading the description; new keys win.

    `defaults` fills in keys still missing after the merge (e.g. on first-time creation)
    without overriding any value already present, explicit or previously set. A default
    may be a plain value, or a callable taking the in-progress merged dict and returning
    the value to use, for a default derived from another key. Defaults are applied in
    dict order, so such a callable can rely on an earlier key already being resolved.
    """
    existing, remainder = split_leading_json(description or "")
    merged = {**existing, **new_data}
    if defaults:
        for key, value in defaults.items():
            if key not in merged:
                merged[key] = value(merged) if callable(value) else value
    json_str = json.dumps(merged, sort_keys=True)
    if not remainder:
        return json_str
    if remainder[0].isspace():
        return json_str + remainder
    return f"{json_str} {remainder}"
