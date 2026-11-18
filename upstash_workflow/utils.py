import re
import secrets
import base64
import logging

from upstash_workflow.error import WorkflowError

NANOID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
NANOID_LENGTH = 21

_logger = logging.getLogger(__name__)


def _nanoid() -> str:
    return "".join([secrets.choice(NANOID_CHARS) for _ in range(NANOID_LENGTH)])


_FORBIDDEN_IN_SEGMENT = re.compile(r"[/?#\x00-\x1f\x7f]")
_IGNORED_IN_DOT_SEGMENT = re.compile(r"[\s\x00-\x1f\x7f]")
_ENCODED_DOT = re.compile(r"%2e", re.IGNORECASE)


def _is_dot_segment(segment: str) -> bool:
    normalized = _ENCODED_DOT.sub(".", _IGNORED_IN_DOT_SEGMENT.sub("", segment))
    return normalized in (".", "..")


def _path_segment(value: str, name: str = "Id") -> str:
    """Checks that an id can be used as a single segment of a request path."""
    if not isinstance(value, str):
        raise WorkflowError(f"{name} must be a string.")
    if not value:
        raise WorkflowError(f"{name} cannot be empty.")
    # A backslash is allowed in an id, but "." and ".." are not allowed on
    # either side of one.
    if any(_is_dot_segment(part) for part in value.split("\\")):
        raise WorkflowError(f'{name} cannot be "." or "..".')
    if _FORBIDDEN_IN_SEGMENT.search(value) or value != value.strip():
        raise WorkflowError(
            f"{name} cannot contain '/', '?', '#' or control characters, "
            "or start or end with whitespace."
        )
    return value


def _destination_path(url: str) -> str:
    """Checks that a workflow url can be used as the destination of a publish request."""
    match = (
        re.match(r"^https?://([^/]*)([^?#]*)", url) if isinstance(url, str) else None
    )
    if (
        not match
        or not match.group(1)
        or re.search(r"[?#]", match.group(1))
        or re.search(r"[\x00-\x1f\x7f]", url)
        # a backslash is only allowed in the query or fragment
        or "\\" in match.group(0)
        or any(_is_dot_segment(segment) for segment in match.group(2).split("/"))
    ):
        raise WorkflowError("Workflow url is not usable as a destination.")
    return url


def _decode_base64(base64_str: str) -> str:
    try:
        decoded_bytes = base64.b64decode(base64_str)
        return decoded_bytes.decode("utf-8")
    except Exception as error:
        _logger.error(
            f"Upstash Qstash: Failed while decoding base64 '{base64_str}'."
            f" Falling back to standard base64 decoding. {error}"
        )
        return base64.b64decode(base64_str).decode("ascii")
