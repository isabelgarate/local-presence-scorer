from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...models.business import SearchRequest
from ...models.scores import TotalScore
from ...services.search_service import SearchService, ScoredBusiness
from ..dependencies import get_search_service

router = APIRouter()


class SearchResultItem(BaseModel):
    place_id: str
    name: str
    address: str | None
    rating: float | None
    review_count: int | None
    website: str | None
    score: TotalScore


@router.post("/search", response_model=list[SearchResultItem])
async def search_businesses(
    request: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> list[SearchResultItem]:
    """
    Search for businesses by type/name and location.
    Returns local scores only (fast, no Instagram enrichment).
    """
    results = await service.search(
        query=request.query,
        location=request.location,
        max_results=request.max_results,
        include_social=False,
    )
    return [
        SearchResultItem(
            place_id=r.profile.place_id,
            name=r.profile.name,
            address=r.profile.address,
            rating=r.profile.rating,
            review_count=r.profile.review_count,
            website=r.profile.website,
            score=r.score,
        )
        for r in results
    ]
