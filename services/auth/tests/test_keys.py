from app.core.config import Settings
from app.core.keys import jwk_from_public, load_keypair


def test_generates_key_when_missing(tmp_path):
    s = Settings(
        database_url="postgresql+asyncpg://x", jwt_private_key_file=str(tmp_path / "k.pem"), env="dev"
    )
    kp = load_keypair(s)
    assert (tmp_path / "k.pem").exists()
    assert len(kp.kid) == 16
    again = load_keypair(s)
    assert again.kid == kp.kid  # stable across loads


def test_jwk_shape():
    s = Settings(database_url="postgresql+asyncpg://x", jwt_private_key_file="", env="dev")
    kp = load_keypair(s)
    jwk = jwk_from_public(kp.public_key, kp.kid)
    assert jwk["kty"] == "RSA" and jwk["alg"] == "RS256" and jwk["kid"] == kp.kid
    assert "=" not in jwk["n"]
