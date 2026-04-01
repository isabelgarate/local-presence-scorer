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
from ..clients.facebook import FacebookClient
from ..clients.tiktok import TikTokClient
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
    return {"A": "bold green", "B": "green", "C": "yellow", "D": "red", "F": "bold red"}.get(grade, "white")


def _build_clients() -> tuple[GooglePlacesClient, InstagramClient | None, FacebookClient | None, TikTokClient | None]:
    places = GooglePlacesClient()
    ig = fb = tt = None
    if settings.rapidapi_key:
        try:
            ig = InstagramClient()
            fb = FacebookClient()
            tt = TikTokClient()
        except ValueError:
            pass
    return places, ig, fb, tt


def _render_results(results: list[ScoredBusiness], show_rank: bool = False) -> None:
    table = Table(box=box.ROUNDED, show_lines=True)

    if show_rank:
        table.add_column("#", style="dim", width=3)
    table.add_column("Negocio", min_width=22)
    table.add_column("Rating", justify="center")
    table.add_column("Reseñas", justify="right")
    table.add_column("Instagram", justify="center")
    table.add_column("Facebook", justify="center")
    table.add_column("TikTok", justify="center")
    table.add_column("Local", justify="right")
    table.add_column("Social", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Nota", justify="center")

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
            f"✓ {p.facebook_handle[:12]}" if p.facebook_handle else "—",
            f"@{p.tiktok_handle}" if p.tiktok_handle else "—",
            f"{s.local_score.total:.2f}" if s.local_score else "—",
            f"{s.social_score.total:.2f}" if s.social_score else "—",
            f"[bold]{s.total:.2f}[/bold]",
            f"[{grade_style}]{s.grade}[/{grade_style}]",
        ])
        table.add_row(*row)

    console.print(table)


def _explain_score(result: ScoredBusiness) -> None:
    """Print a human-readable breakdown of the score."""
    s = result.score
    p = result.profile

    console.print(f"\n[bold]📊 Análisis de presencia digital — {p.name}[/bold]\n")

    # Local score breakdown
    if s.local_score:
        ls = s.local_score
        console.print(f"[bold cyan]📍 Presencia local (Google Business)[/bold cyan]  →  {ls.total:.0%}")
        console.print(f"   • Rating {p.rating or '—'} ★         {ls.rating_component:.0%}  (peso 35%)")
        console.print(f"   • Reseñas ({p.review_count or 0})     {ls.review_count_component:.0%}  (peso 30%)")
        console.print(f"   • Categoría coincide    {ls.category_match_component:.0%}  (peso 15%)")
        console.print(f"   • Tiene web             {ls.website_component:.0%}  (peso 10%)")
        console.print(f"   • Perfil completo       {ls.profile_completeness_component:.0%}  (peso 10%)\n")

    # Social score breakdown
    if s.social_score:
        ss = s.social_score
        console.print(f"[bold magenta]📱 Presencia en redes sociales[/bold magenta]          →  {ss.total:.0%}")
        if ss.instagram:
            console.print(f"   • Instagram @{p.instagram_handle}   {ss.instagram.total:.0%}  (peso 40%)")
        else:
            console.print("   • Instagram   no encontrado")
        if ss.facebook:
            console.print(f"   • Facebook                {ss.facebook.total:.0%}  (peso 35%)")
        else:
            console.print("   • Facebook    no encontrado")
        if ss.tiktok:
            console.print(f"   • TikTok @{p.tiktok_handle}      {ss.tiktok.total:.0%}  (peso 25%)")
        else:
            console.print("   • TikTok      no encontrado")
        console.print()

    if s.activity_score:
        act = s.activity_score
        console.print(f"[bold yellow]🏃 Actividad de contenido[/bold yellow]               →  {act.total:.0%}\n")

    grade_style = _grade_style(s.grade)
    console.print(f"[bold]SCORE TOTAL: {s.total:.0%}  [{grade_style}]Nota: {s.grade}[/{grade_style}][/bold]")
    console.print(f"[dim]  = 50% local + 35% social + 15% actividad[/dim]\n")


@app.command()
def score(
    name: Annotated[str, typer.Argument(help="Nombre del negocio")],
    location: Annotated[str, typer.Option("--location", "-l", help="Ciudad o dirección")] = "",
    social: Annotated[bool, typer.Option("--social/--no-social")] = True,
    recommendations: Annotated[bool, typer.Option("--recommendations/--no-recommendations")] = True,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Score completo de presencia digital para un negocio."""

    async def _run() -> None:
        places, ig, fb, tt = _build_clients()
        service = SearchService(places, ig, fb, tt)
        result = await service.score_business(name, location, include_social=social)

        if result is None:
            console.print(f"[red]Negocio '{name}' no encontrado en '{location}'[/red]")
            raise typer.Exit(1)

        if as_json:
            out = {
                "score": result.score.model_dump(mode="json"),
                "profile": result.profile.model_dump(),
                "social": result.social.model_dump(),
            }
            if recommendations:
                recs = RecommendationService().generate(result.score)
                out["recommendations"] = recs.model_dump()
            console.print_json(json.dumps(out, default=str))
        else:
            _render_results([result])
            _explain_score(result)
            if recommendations:
                recs = RecommendationService().generate(result.score)
                if recs.recommendations:
                    console.print("[bold]💡 Recomendaciones de mejora:[/bold]")
                    for r in recs.recommendations:
                        priority_style = {"high": "red", "medium": "yellow", "low": "blue"}[r.priority.value]
                        console.print(
                            f"  [{priority_style}]●[/{priority_style}] [bold]{r.title}[/bold] "
                            f"({r.impact_estimate})\n    {r.description}\n"
                        )

    asyncio.run(_run())


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Tipo de negocio, p.ej. 'restaurante italiano'")],
    location: Annotated[str, typer.Option("--location", "-l")] = "",
    max_results: Annotated[int, typer.Option("--max", "-n")] = 5,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Busca negocios y muestra su score local (rápido, sin redes sociales)."""

    async def _run() -> None:
        places, ig, fb, tt = _build_clients()
        service = SearchService(places, ig, fb, tt)
        results = await service.search(query, location, max_results, include_social=False)
        if as_json:
            console.print_json(json.dumps([r.score.model_dump(mode="json") for r in results], default=str))
        else:
            _render_results(results)

    asyncio.run(_run())


@app.command()
def compare(
    businesses: Annotated[list[str], typer.Argument(help="Nombres de negocios a comparar")],
    location: Annotated[str, typer.Option("--location", "-l")] = "",
    social: Annotated[bool, typer.Option("--social/--no-social")] = True,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Compara y rankea varios negocios por presencia digital."""

    async def _run() -> None:
        places, ig, fb, tt = _build_clients()
        service = CompareService(places, ig, fb, tt)
        pairs = [(b, location) for b in businesses]
        results = await service.compare(pairs, include_social=social)

        if as_json:
            console.print_json(json.dumps([r.score.model_dump(mode="json") for r in results], default=str))
        else:
            _render_results(results, show_rank=True)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
