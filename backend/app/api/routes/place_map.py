"""Signed image proxy for Geoapify place previews."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Response

from app.core.config import settings
from app.modules.leisure.geoapify import valid_place_map_signature

router = APIRouter(tags=["leisure"])


@router.get("/place-map/{latitude}/{longitude}/{signature}")
async def place_map(latitude: float, longitude: float, signature: str) -> Response:
    if not valid_place_map_signature(latitude, longitude, signature):
        raise HTTPException(status_code=404, detail="Image not found")
    coordinates = f"{longitude:.6f},{latitude:.6f}"
    try:
        async with httpx.AsyncClient(timeout=settings.geoapify_timeout_seconds) as client:
            result = await client.get(
                "https://maps.geoapify.com/v1/staticmap",
                params={
                    "style": "osm-bright",
                    "width": 640,
                    "height": 360,
                    "format": "jpeg",
                    "center": f"lonlat:{coordinates}",
                    "zoom": 15,
                    "marker": f"lonlat:{coordinates};type:material;color:#5b35d5;size:48",
                    "lang": "ru",
                    "apiKey": settings.geoapify_api_key,
                },
            )
            result.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="Image unavailable") from error
    if result.headers.get("content-type", "").split(";", 1)[0] != "image/jpeg":
        raise HTTPException(status_code=503, detail="Image unavailable")
    return Response(
        content=result.content,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
