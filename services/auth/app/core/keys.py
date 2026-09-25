"""RSA signing key handling: load from env/file, generate in dev, expose as JWK."""

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.core.config import Settings


@dataclass(frozen=True)
class KeyPair:
    private_key: RSAPrivateKey
    public_key: RSAPublicKey
    kid: str
    private_pem: bytes


def _b64url_uint(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _kid(public_key: RSAPublicKey) -> str:
    der = public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return hashlib.sha256(der).hexdigest()[:16]


def load_keypair(settings: Settings) -> KeyPair:
    pem: bytes | None = None
    if settings.jwt_private_key_pem:
        pem = settings.jwt_private_key_pem.encode()
    elif settings.jwt_private_key_file and Path(settings.jwt_private_key_file).exists():
        pem = Path(settings.jwt_private_key_file).read_bytes()

    if pem is None:
        if settings.env != "dev":
            raise RuntimeError("No JWT private key configured (AUTH_JWT_PRIVATE_KEY_PEM or _FILE)")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        if settings.jwt_private_key_file:
            path = Path(settings.jwt_private_key_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(pem)

    private_key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(private_key, RSAPrivateKey):
        raise RuntimeError("JWT private key must be RSA")
    public_key = private_key.public_key()
    return KeyPair(private_key, public_key, _kid(public_key), pem)


def jwk_from_public(public_key: RSAPublicKey, kid: str) -> dict[str, str]:
    nums = public_key.public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64url_uint(nums.n),
        "e": _b64url_uint(nums.e),
    }
