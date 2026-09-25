"""Test-only JWT signing with a throwaway RSA key. The API's JWKS cache is pointed at it."""

import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

TEST_KID = "test-kid-0001"
TEST_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_PUBLIC_KEY = TEST_KEY.public_key()

ISSUER = "foresight-auth"
AUDIENCE = "foresight-api"


def sign(sub: str, email: str, name: str, **overrides: Any) -> str:
    kid = overrides.pop("kid", TEST_KID)
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "name": name,
        "iat": now,
        "exp": now + 900,
        "jti": uuid.uuid4().hex,
        "iss": ISSUER,
        "aud": AUDIENCE,
    }
    claims.update(overrides)
    return jwt.encode(claims, TEST_KEY, algorithm="RS256", headers={"kid": kid})


def public_jwk() -> dict[str, str]:
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(TEST_PUBLIC_KEY, as_dict=True)
    jwk.update({"kid": TEST_KID, "use": "sig", "alg": "RS256"})
    return jwk
