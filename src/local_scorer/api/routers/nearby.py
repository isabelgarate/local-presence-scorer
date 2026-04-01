from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...models.business import BusinessProfile
from ...models.scores import TotalScore
from ...models.recommendations import RecommendationSet
from ...services.nearby_service import NearbyService
from ...services.recommendation_service import RecommendationService
from ..dependencies import get_places_client, get_instagram_client

router = APIRouter()


class NearbyCompareRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Target business name")
    location: str = Field(..., min_length=2, description="City or address")
    radius_meters: float = Field(default=1000.0, ge=100, le=50000, description="Search radius in metres")
    max_competitors: int = Field(default=5, ge=1, le=10)
    include_social: bool = False


class RankedBusiness(BaseModel):
    rank: int
    is_target: bool
    profile: BusinessProfile
    score: TotalScore
    recommendations: RecommendationSet


@router.post("/nearby-compare", response_model=list[RankedBusiness])
async def nearby_compare(
    request: NearbyCompareRequest,
    places=Depends(get_places_client),
    instagram=Depends(get_instagram_client),
    rec_service: RecommendationService = Depends(RecommendationService),
) -> list[RankedBusiness]:
    """
    Find the target business, discover nearby competitors in the same category,
    and return everyone ranked by digital presence score.
    """
    from ..dependencies import get_facebook_client, get_tiktok_client
    facebook = get_facebook_client()
    tiktok = get_tiktok_client()
    service = NearbyService(places, instagram, facebook, tiktok)
    target, competitors = await service.nearby_compare(
        name=request.name,
        location=request.location,
        radius_meters=request.radius_meters,
        max_competitors=request.max_competitors,
        include_social=request.include_social,
    )

    if target is None:
        raise HTTPException(status_code=404, detail=f"Business '{request.name}' not found in '{request.location}'")

    # Merge target + competitors and rank together
    all_businesses = [target] + competitors
    all_businesses.sort(key=lambda b: b.score.total, reverse=True)

    return [
        RankedBusiness(
            rank=i + 1,
            is_target=(b.profile.place_id == target.profile.place_id),
            profile=b.profile,
            score=b.score,
            recommendations=rec_service.generate(b.score),
        )
        for i, b in enumerate(all_businesses)
    ]
