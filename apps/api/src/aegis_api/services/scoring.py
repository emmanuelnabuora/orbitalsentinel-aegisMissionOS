"""Pure mission-assurance scoring core.

The scoring math lives here as a dependency-free function over plain values so
that MissionIQ (live DB state) and the Digital Twin (hypothetical projected
state) produce *identical* scores from the same inputs. Neither path duplicates
the model; both call score_mission(). Keeping this pure also makes the model
trivially unit-testable and keeps the Explainable-AI factor list in one place.
"""

from dataclasses import dataclass, field

from aegis_api.models.enums import AssetStatus, Criticality

CRIT_WEIGHT = {
    Criticality.CRITICAL: 1.0,
    Criticality.HIGH: 0.75,
    Criticality.MEDIUM: 0.5,
    Criticality.LOW: 0.25,
}
STATUS_PENALTY = {
    AssetStatus.OFFLINE: 45,
    AssetStatus.DEGRADED: 22,
    AssetStatus.UNKNOWN: 10,
    AssetStatus.OPERATIONAL: 0,
}
ALERT_PENALTY = 6  # per open alert on a mission asset, criticality-weighted


@dataclass
class ScoredAsset:
    """One asset's contribution to a mission, as plain values."""

    name: str
    status: AssetStatus
    dependency_criticality: Criticality
    open_alerts: int = 0


@dataclass
class MissionScore:
    score: int  # 0-100
    health: str  # assured | degraded | at_risk
    degraded_assets: int
    offline_assets: int
    open_alerts: int
    factors: list[str] = field(default_factory=list)


def health_band(score: int) -> str:
    return "assured" if score >= 80 else "degraded" if score >= 50 else "at_risk"


def score_mission(assets: list[ScoredAsset]) -> MissionScore:
    """Deterministic, explainable assurance score for one mission.

    Score starts at 100 and is reduced by criticality-weighted penalties for
    non-operational status and for open alerts. Every deduction appends a
    human-readable factor.
    """
    score = 100.0
    factors: list[str] = []
    degraded = offline = 0
    total_alerts = 0

    for a in assets:
        weight = CRIT_WEIGHT[a.dependency_criticality]
        penalty = STATUS_PENALTY[a.status] * weight
        if a.status == AssetStatus.DEGRADED:
            degraded += 1
        if a.status == AssetStatus.OFFLINE:
            offline += 1
        if penalty:
            score -= penalty
            factors.append(
                f"{a.name} is {a.status.value} "
                f"({a.dependency_criticality.value} dependency): -{penalty:.0f}"
            )
        if a.open_alerts:
            total_alerts += a.open_alerts
            alert_penalty = ALERT_PENALTY * a.open_alerts * weight
            score -= alert_penalty
            factors.append(f"{a.open_alerts} open alert(s) on {a.name}: -{alert_penalty:.0f}")

    if not assets:
        factors.append("No assets attached; assurance not yet meaningful.")
    if not factors:
        factors.append("All mission dependencies operational with no open alerts.")

    final = max(0, min(100, round(score)))
    return MissionScore(
        score=final,
        health=health_band(final),
        degraded_assets=degraded,
        offline_assets=offline,
        open_alerts=total_alerts,
        factors=factors,
    )
