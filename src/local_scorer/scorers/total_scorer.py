from __future__ import annotations
from ..models.scores import LocalScore, SocialScore, ActivityScore, TotalScore, _grade


class TotalScorer:
    """
    Combines sub-scores into a TotalScore.

    Weights (when all sub-scores present):
      local    0.50
      social   0.35
      activity 0.15

    When sub-scores are missing, weights are redistributed proportionally
    so the total stays in [0, 1].
    """

    _WEIGHTS = {"local": 0.50, "social": 0.35, "activity": 0.15}

    def score(
        self,
        place_id: str,
        business_name: str,
        local: LocalScore | None,
        social: SocialScore | None,
        activity: ActivityScore | None,
    ) -> TotalScore:
        present: dict[str, float] = {}
        if local is not None:
            present["local"] = local.total
        if social is not None:
            present["social"] = social.total
        if activity is not None:
            present["activity"] = activity.total

        if not present:
            total = 0.0
        else:
            weight_sum = sum(self._WEIGHTS[k] for k in present)
            total = sum(
                self._WEIGHTS[k] * v / weight_sum for k, v in present.items()
            )

        total = round(total, 4)

        return TotalScore(
            place_id=place_id,
            business_name=business_name,
            local_score=local,
            social_score=social,
            activity_score=activity,
            total=total,
            grade=_grade(total),
        )
