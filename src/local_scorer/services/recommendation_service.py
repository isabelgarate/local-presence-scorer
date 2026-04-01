from __future__ import annotations
"""Genera recomendaciones de mejora a partir del score de un negocio."""

from ..models.scores import TotalScore
from ..models.recommendations import (
    Recommendation,
    RecommendationArea,
    Priority,
    RecommendationSet,
)

_THRESHOLDS = {
    "rating": 0.60,
    "reviews": 0.40,
    "completeness": 0.67,
    "engagement": 0.40,
    "activity": 0.30,
}


class RecommendationService:
    def generate(self, score: TotalScore) -> RecommendationSet:
        recs: list[Recommendation] = []

        if score.local_score:
            ls = score.local_score

            if ls.rating_component < _THRESHOLDS["rating"]:
                recs.append(Recommendation(
                    area=RecommendationArea.RATING,
                    priority=Priority.HIGH,
                    title="Mejora tu valoración en Google",
                    description=(
                        "Tu nota media está por debajo de 4.0. Pide reseñas a clientes satisfechos "
                        "tras cada visita y responde con profesionalidad a las críticas negativas."
                    ),
                    impact_estimate="+hasta 20 pts en score local",
                ))

            if ls.review_count_component < _THRESHOLDS["reviews"]:
                recs.append(Recommendation(
                    area=RecommendationArea.REVIEWS,
                    priority=Priority.HIGH,
                    title="Consigue más reseñas en Google",
                    description=(
                        "Los negocios con más reseñas aparecen primero y generan más confianza. "
                        "Comparte tu enlace de Google Maps con clientes por WhatsApp o email."
                    ),
                    impact_estimate="+hasta 15 pts en score local",
                ))

            if ls.profile_completeness_component < _THRESHOLDS["completeness"]:
                recs.append(Recommendation(
                    area=RecommendationArea.PROFILE_COMPLETENESS,
                    priority=Priority.MEDIUM,
                    title="Completa tu perfil de Google Business",
                    description=(
                        "Faltan datos como teléfono, horario, fotos o dirección. "
                        "Un perfil completo mejora el posicionamiento local y genera más confianza."
                    ),
                    impact_estimate="+hasta 8 pts en score local",
                ))

            if ls.website_component == 0.0:
                recs.append(Recommendation(
                    area=RecommendationArea.WEBSITE,
                    priority=Priority.MEDIUM,
                    title="Añade una web a tu perfil de Google",
                    description=(
                        "Los negocios con web propia generan mucha más credibilidad. "
                        "Incluso una página sencilla marca una gran diferencia."
                    ),
                    impact_estimate="+5 pts en score local",
                ))

        # Redes sociales
        if score.social_score is None:
            recs.append(Recommendation(
                area=RecommendationArea.INSTAGRAM,
                priority=Priority.MEDIUM,
                title="Crea perfiles en Instagram, Facebook y TikTok",
                description=(
                    "No se encontraron perfiles en redes sociales para este negocio. "
                    "La presencia social aumenta significativamente la visibilidad y la confianza."
                ),
                impact_estimate="+hasta 35 pts en score total",
            ))
        else:
            ss = score.social_score
            missing = [p for p in ("instagram", "facebook", "tiktok") if p not in ss.platforms_found]

            if missing:
                nombres = {"instagram": "Instagram", "facebook": "Facebook", "tiktok": "TikTok"}
                recs.append(Recommendation(
                    area=RecommendationArea.INSTAGRAM,
                    priority=Priority.MEDIUM,
                    title=f"Crea perfil en: {', '.join(nombres[p] for p in missing)}",
                    description=(
                        f"No se encontró perfil en {', '.join(nombres[p] for p in missing)}. "
                        "Cada plataforma adicional amplía tu alcance y mejora tu score."
                    ),
                    impact_estimate=f"+hasta {len(missing) * 8} pts en score social",
                ))

            if ss.instagram and ss.instagram.follower_component < 0.20:
                recs.append(Recommendation(
                    area=RecommendationArea.INSTAGRAM,
                    priority=Priority.MEDIUM,
                    title="Haz crecer tu audiencia en Instagram",
                    description=(
                        "Tu número de seguidores en Instagram es bajo. "
                        "Publica con regularidad, usa hashtags locales y etiqueta tu ubicación."
                    ),
                    impact_estimate="+hasta 10 pts en score social",
                ))

            if ss.instagram and ss.instagram.engagement_component < _THRESHOLDS["engagement"]:
                recs.append(Recommendation(
                    area=RecommendationArea.SOCIAL_ENGAGEMENT,
                    priority=Priority.LOW,
                    title="Mejora el engagement en Instagram",
                    description=(
                        "Tu tasa de interacción está por debajo de la media. "
                        "Usa encuestas en Stories, responde comentarios rápido y haz preguntas en los pies de foto."
                    ),
                    impact_estimate="+hasta 8 pts en score social",
                ))

            if ss.tiktok and ss.tiktok.follower_component < 0.10:
                recs.append(Recommendation(
                    area=RecommendationArea.CONTENT_ACTIVITY,
                    priority=Priority.LOW,
                    title="Potencia tu presencia en TikTok",
                    description=(
                        "Tu cuenta de TikTok tiene poco alcance. Los vídeos cortos de negocios locales "
                        "funcionan muy bien — intenta publicar 2-3 por semana."
                    ),
                    impact_estimate="+hasta 8 pts en score social",
                ))

        if score.activity_score and score.activity_score.total < _THRESHOLDS["activity"]:
            recs.append(Recommendation(
                area=RecommendationArea.CONTENT_ACTIVITY,
                priority=Priority.LOW,
                title="Publica contenido con más frecuencia",
                description=(
                    "La actividad reciente en redes es baja. "
                    "Apunta a 3-5 publicaciones por semana para mantenerte visible."
                ),
                impact_estimate="+hasta 6 pts en score de actividad",
            ))

        priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
        recs.sort(key=lambda r: priority_order[r.priority])

        return RecommendationSet(
            place_id=score.place_id,
            business_name=score.business_name,
            recommendations=recs,
        )
