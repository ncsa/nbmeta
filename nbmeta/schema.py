"""Validation for the nbmeta metadata fields (--role/--env/--nagios/--ansible)."""

ALLOWED_KEYS = {"role", "env", "nagios", "ansible"}

DEFAULTS = {
    "env": "prod_a",
    "nagios": True,
    "ansible": True,
}


class ValidationError(ValueError):
    pass


def validate_data(data):
    """Validate the collected metadata fields against the nbmeta schema. Raises ValidationError;
    returns data unchanged. Whether 'role' must be present is checked separately by
    require_role(), since it may already be set in the existing description.
    """
    unknown = set(data) - ALLOWED_KEYS
    if unknown:
        raise ValidationError(
            f"unknown key(s) {sorted(unknown)}; allowed keys are {sorted(ALLOWED_KEYS)}"
        )

    if "role" in data and (not isinstance(data["role"], str) or not data["role"].strip()):
        raise ValidationError("'role' must be a non-empty string")

    if "env" in data and (not isinstance(data["env"], str) or not data["env"].strip()):
        raise ValidationError("'env' must be a non-empty string")

    for key in ("nagios", "ansible"):
        if key in data and not isinstance(data[key], bool):
            raise ValidationError(f"'{key}' must be a boolean")

    return data


def require_role(existing, new_data):
    """Ensure 'role' is set either already in the existing description or via --role."""
    if "role" not in existing and "role" not in new_data:
        raise ValidationError("'role' is required (pass --role, or it must already be set in the existing description)")
