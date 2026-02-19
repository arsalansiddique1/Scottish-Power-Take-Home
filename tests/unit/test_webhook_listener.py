import hashlib
import hmac

import pytest
from fastapi import HTTPException

from review_agent.webhook_listener import _verify_signature


def test_verify_signature_accepts_valid_signature() -> None:
    secret = "top-secret"
    payload = b'{"a":1}'
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    _verify_signature(secret=secret, payload=payload, signature_header=f"sha256={digest}")


def test_verify_signature_rejects_invalid_signature() -> None:
    with pytest.raises(HTTPException):
        _verify_signature(secret="x", payload=b"{}", signature_header="sha256=deadbeef")
