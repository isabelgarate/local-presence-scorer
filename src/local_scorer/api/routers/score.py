from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...models.business import ScoreRequest, BusinessProfile
from ...models.scores import TotalScore
from ...models.recommendations import RecommendationSet
from ...services.search_service import SearchService
from ...services.recommendation_service import RecommendationService
from ..dependencies import get_search_service, get_recommendation_service

router = APIRouter()


class ScoreResponse(BaseModel):
    profile: BusinessProfile
    score: TotalScore
    recommendations: RecommendationSet


@router.post("/score", response_model=ScoreResponse)
async def score_business(
    request: ScoreRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
    rec_service: Annotated[RecommendationService, Depends(get_recommendation_service)],
) -> ScoreResponse:
    """
    Full digital presence score for a single business.
    Includes Instagram enrichment if configured.
    """
    result = await service.score_business(
        name=request.name,
        location=request.location,
        include_instagram=request.include_instagram,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Business '{request.name}' not found in '{request.location}'")

    recommendations = rec_service.generate(result.score)
    return ScoreResponse(profile=result.profile, score=result.score, recommendations=recommendations)
