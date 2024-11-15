import secrets
import base64

NANOID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
NANOID_LENGTH = 21


def nanoid() -> str:
    random_indices = [
        secrets.randbelow(len(NANOID_CHARS)) for _ in range(NANOID_LENGTH)
    ]
    return "".join(NANOID_CHARS[i] for i in random_indices)


def decode_base64(base64_str: str) -> str:
    try:
        decoded_bytes = base64.b64decode(base64_str)
        return decoded_bytes.decode("utf-8")
    except Exception as error:
        print(
            f"Upstash Qstash: Failed while decoding base64 '{base64_str}'."
            f" Falling back to standard base64 decoding. {error}"
        )
        return base64.b64decode(base64_str).decode("ascii")
