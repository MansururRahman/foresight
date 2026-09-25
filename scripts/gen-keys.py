"""Generate the development RSA signing key for the auth service.

Usage: uv run --with cryptography python scripts/gen-keys.py [path]
Writes a 2048-bit PKCS8 PEM to infra/keys/dev_private.pem unless it exists.
"""

from __future__ import annotations

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main(path: Path) -> None:
    if path.exists():
        print(f"key already exists: {path}")
        return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pem)
    print(f"wrote {path}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("infra/keys/dev_private.pem")
    main(target)
