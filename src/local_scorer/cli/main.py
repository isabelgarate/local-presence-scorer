from __future__ import annotations
"""CLI interface — mirrors the API endpoints but runs in-process."""

import asyncio
import json
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from ..clients.google_places import GooglePlacesClient
from ..clients.instagram import InstagramClient
from ..config import settings
from ..services.search_service import SearchService, ScoredBusiness
from ..services.compare_service import CompareService
from ..services.recommendation_service import RecommendationService

app = typer.Typer(
    name="local-scorer",
    help="Score and compare local businesses' digital presence.",
    no_args_is_help=True,
)
console = Console()


def _grade_style(grade: str) -> str:
    return {
        "A": "bold green",
        "B": "green",
        "C": "yellow",
        "D": "red",
        "F": "bold red",
    }.get(grade, "white")


def _build_clients() -> tuple[GooglePlacesClient, InstagramClient | None]:
    places = GooglePlacesClient()
    instagram: InstagramClient | None = None
    if settings.rapidapi_key:
        try:
            instagram = InstagramClient()
        except ValueError:
            pass
    return places, instagram


def _render_results(results: list[ScoredBusiness], show_rank: bool = False) -> None:
    table = Table(box=box.ROUNDED, show_lines=True)

    if show_rank:
        table.add_column("#", style="dim", width=3)
    table.add_column("Business", min_width=20)
    table.add_column("Rating", justify="center")
    table.add_column("Reviews", justify="right")
    table.add_column("Instagram", justify="center")
    table.add_column("Local", justify="right")
    table.add_column("Social", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Grade", justify="center")

    for i, r in enumerate(results):
        p = r.profile
        s = r.score
        grade_style = _grade_style(s.grade)

        row = []
        if show_rank:
            row.append(str(i + 1))
        row.extend([
            p.name,
            f"{p.rating:.1f} ★" if p.rating else "—",
            str(p.review_count or "—"),
            f"@{p.instagram_handle}" if p.instagram_handle else "—",
            f"{s.local_score.total:.2f}" if s.local_score else "—",
            f"{s.social_score.total:.2f}" if s.social_score else "—",
            f"[bold]{s.total:.2f}[/bold]",
            f"[{grade_style}]{s.grade}[/{grade_style}]",
        ])
        table.add_row(*row)

    console.print(table)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Business type, e.g. 'italian restaurant'")],
    location: Annotated[str, typer.Option("--location", "-l", help="City or address")] = "",
    max_results: Annotated[int, typer.Option("--max", "-n")] = 5,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Search for businesses and show their local scores."""

    async def _run() -> None:
        places, instagram = _build_clients()
        service = SearchService(places, instagram)
        results = await service.search(query, location, max_results, include_instagram=False)
        if as_json:
            console.print_json(json.dumps([r.score.model_dump(mode="json") for r in results], default=str))
        else:
            _render_results(results)

    asyncio.run(_run())


@app.command()
def score(
    name: Annotated[str, typer.Argument(help="Business name")],
    location: Annotated[str, typer.Option("--location", "-l", help="City or address")] = "",
    instagram: Annotated[bool, typer.Option("--instagram/--no-instagram")] = True,
    recommendations: Annotated[bool, typer.Option("--recommendations/--no-recommendations")] = True,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Full digital presence score for a single business."""

    async def _run() -> None:
        places, ig_client = _build_clients()
        service = SearchService(places, ig_client)
        result = await service.score_business(name, location, include_instagram=instagram)

        if result is None:
            console.print(f"[red]Business '{name}' not found in '{location}'[/red]")
            raise typer.Exit(1)

        if as_json:
            out = {"score": result.score.model_dump(mode="json"), "profile": result.profile.model_dump()}
            if recommendations:
                rec_service = RecommendationService()
                recs = rec_service.generate(result.score)
                out["recommendations"] = recs.model_dump()
            console.print_json(json.dumps(out, default=str))
        else:
            _render_results([result])
            if recommendations:
                rec_service = RecommendationService()
                recs = rec_service.generate(result.score)
                if recs.recommendations:
                    console.print("\n[bold]Recommendations:[/bold]")
                    for r in recs.recommendations:
                        priority_style = {"high": "red", "medium": "yellow", "low": "blue"}[r.priority.value]
                        console.print(
                            f"  [{priority_style}]●[/{priority_style}] [bold]{r.title}[/bold] "
                            f"({r.impact_estimate})\n    {r.description}"
                        )

    asyncio.run(_run())


@app.command()
def compare(
    businesses: Annotated[list[str], typer.Argument(help="Business names to compare")],
    location: Annotated[str, typer.Option("--location", "-l", help="Shared city/address")] = "",
    instagram: Annotated[bool, typer.Option("--instagram/--no-instagram")] = True,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Score and rank multiple businesses side by side."""

    async def _run() -> None:
        places, ig_client = _build_clients()
        service = CompareService(places, ig_client)
        pairs = [(b, location) for b in businesses]
        results = await service.compare(pairs, include_instagram=instagram)

        if as_json:
            console.print_json(json.dumps([r.score.model_dump(mode="json") for r in results], default=str))
        else:
            _render_results(results, show_rank=True)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
