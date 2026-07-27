"""Public asset registry endpoint (sandbox / planned honesty)."""

from fastapi import APIRouter

from app.core.assets import ASSETS, SUPPORTED_ROUTES, asset_to_dict

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
async def list_assets() -> dict:
    return {
        "assets": [asset_to_dict(a) for a in ASSETS.values()],
        "routes": [
            {
                "direction": d.value,
                "from_asset": fa,
                "from_network": fn,
                "to_asset": ta,
                "to_network": tn,
            }
            for d, fa, fn, ta, tn in SUPPORTED_ROUTES
        ],
        "note": (
            "sandbox = mock partner demo only; planned = no adapter yet; "
            "real = none in this build; no REAL money rails"
        ),
    }
