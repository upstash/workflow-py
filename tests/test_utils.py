import base64

from upstash_workflow.utils import _decode_base64


def test_decode_base64_handles_base64url_and_unpadded_input() -> None:
    # Include bytes producing `+` and `/` so standard and base64url encodings differ.
    raw = '{"note":"?>? ✓"}'
    unpadded_urlsafe = (
        base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    )
    assert "-" in unpadded_urlsafe or "_" in unpadded_urlsafe
    assert not unpadded_urlsafe.endswith("=")
    assert _decode_base64(unpadded_urlsafe) == raw


def test_decode_base64_handles_standard_padded_and_empty() -> None:
    assert _decode_base64("eyJoZWxsbyI6IndvcmxkIn0=") == '{"hello":"world"}'
    assert _decode_base64("") == ""
