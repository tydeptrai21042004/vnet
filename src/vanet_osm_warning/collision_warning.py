from __future__ import annotations

from math import inf


def compute_ttc(distance_gap_m: float, rear_speed_mps: float, front_speed_mps: float) -> float:
    """Time-to-collision using lane-following approximation.

    TTC = gap / relative_speed, only meaningful when the rear vehicle is faster.
    """
    rel = rear_speed_mps - front_speed_mps
    if rel <= 1e-9:
        return inf
    return max(0.0, distance_gap_m) / rel


def is_ttc_dangerous(distance_gap_m: float, rear_speed_mps: float, front_speed_mps: float, threshold_s: float) -> bool:
    return compute_ttc(distance_gap_m, rear_speed_mps, front_speed_mps) <= threshold_s


def safe_distance(speed_mps: float, reaction_time_s: float, decel_mps2: float, margin_m: float = 2.0) -> float:
    """Simple stopping-distance rule.

    d_safe = v * t_reaction + v^2 / (2a) + margin
    """
    decel = max(decel_mps2, 1e-6)
    return speed_mps * reaction_time_s + (speed_mps * speed_mps) / (2.0 * decel) + margin_m
