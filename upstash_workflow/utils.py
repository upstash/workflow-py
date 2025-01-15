import secrets
import base64
import logging

NANOID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
NANOID_LENGTH = 21

_logger = logging.getLogger(__name__)


def _nanoid() -> str:
    return "".join([secrets.choice(NANOID_CHARS) for _ in range(NANOID_LENGTH)])


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
