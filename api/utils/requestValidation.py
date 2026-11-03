"""Small transport input validators shared by HTTP adapters.

These validate input shape only; they never establish actor identity or access.
"""


def integer_field(data: dict, field: str) -> int:
    """Read a required integer or integer string, rejecting bools and coercions.

    Missing/null values, containers and floats raise ValueError for the adapter
    to translate to 400. Range and resource/authorization rules belong to callers.
    """
    return _integer_value(data.get(field), field)


def integer_list_field(data: dict, field: str) -> list[int]:
    """Read an integer array without coercing other containers or scalar values.

    Empty arrays, duplicates and ID ranges remain domain-policy decisions.
    """
    values = data.get(field)
    if not isinstance(values, list):
        raise ValueError(f"{field} must be an array of integers")
    return [_integer_value(value, field) for value in values]


def _integer_value(value, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{field} must be an integer")
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{field} must be an integer") from None
