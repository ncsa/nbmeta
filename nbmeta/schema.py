"""Validation for the nbmeta metadata fields (--role/--env/--nagios/--ansible)."""

ALLOWED_KEYS = {"role", "env", "nagios", "ansible"}

DEFAULTS = {
    "role": "default",
    "env": "prod_a",
    "nagios": True,
    "ansible": True,
}


class ValidationError(ValueError):
    pass


def sanitize_env(value):
    """Replace '/' and '-' with '_' so env values are safe to use as e.g. branch/path names."""
    return value.replace("/", "_").replace("-", "_")


def validate_data(data):
    """Validate the collected metadata fields against the nbmeta schema. Raises ValidationError;
    returns data unchanged.
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
