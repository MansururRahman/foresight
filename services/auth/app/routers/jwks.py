from fastapi import APIRouter, Response

from app.core.keys import jwk_from_public
from app.deps import KeyPairDep

router = APIRouter(tags=["jwks"])


@router.get("/.well-known/jwks.json")
async def jwks(kp: KeyPairDep, response: Response) -> dict[str, list[dict[str, str]]]:
    response.headers["Cache-Control"] = "public, max-age=300"
    return {"keys": [jwk_from_public(kp.public_key, kp.kid)]}
