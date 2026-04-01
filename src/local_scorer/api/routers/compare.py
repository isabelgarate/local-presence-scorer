from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...models.business import CompareRequest, BusinessProfile
from ...models.scores import TotalScore
from ...models.recommendations import RecommendationSet
from ...services.compare_service import CompareService
from ...services.recommendation_service import RecommendationService
from ..dependencies import get_compare_service, get_recommendation_service

router = APIRouter()


class CompareResultItem(BaseModel):
    rank: int
    profile: BusinessProfile
    score: TotalScore
    recommendations: RecommendationSet


@router.post("/compare", response_model=list[CompareResultItem])
async def compare_businesses(
    request: CompareRequest,
    service: Annotated[CompareService, Depends(get_compare_service)],
    rec_service: Annotated[RecommendationService, Depends(get_recommendation_service)],
) -> list[CompareResultItem]:
    """
    Score and rank multiple businesses. Returns sorted by total score (highest first).
    """
    pairs = [(b.name, b.location) for b in request.businesses]
    results = await service.compare(pairs, include_instagram=request.include_instagram)

    return [
        CompareResultItem(
            rank=i + 1,
            profile=r.profile,
            score=r.score,
            recommendations=rec_service.generate(r.score),
        )
        for i, r in enumerate(results)
    ]
