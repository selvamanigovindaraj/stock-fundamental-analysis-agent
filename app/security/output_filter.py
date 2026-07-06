from __future__ import annotations


def filter_output(response: str) -> str:
    """Redact or block disallowed content before returning a response."""
    raise NotImplementedError
