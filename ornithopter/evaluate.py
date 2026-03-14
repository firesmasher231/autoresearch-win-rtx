"""
Ornithopter Design Evaluation
==============================

Computes fitness metrics from simulation results.

DO NOT MODIFY THIS FILE. This is the ground truth evaluation,
analogous to prepare.py's evaluate_bpb in autoresearch.

Primary metric: fitness (based on cycle-averaged thrust coefficient).
Higher fitness = better design. The goal is to maximize fitness.
"""

import math


def validate_design(params):
    """Check design parameters for physical plausibility.

    Returns a list of error strings. Empty list = valid design.
    """
    errors = []

    if params["semi_span"] <= 0:
        errors.append("SEMI_SPAN must be positive")
    if params["root_chord"] <= 0:
        errors.append("ROOT_CHORD must be positive")
    if not (0 < params["taper_ratio"] <= 1.0):
        errors.append("TAPER_RATIO must be in (0, 1.0]")
    if params["flap_frequency"] <= 0:
        errors.append("FLAP_FREQUENCY must be positive")
    if not (0 < params["flap_amplitude"] <= 89):
        errors.append("FLAP_AMPLITUDE must be in (0, 89] degrees")
    if params["pitch_amplitude"] < 0 or params["pitch_amplitude"] > 89:
        errors.append("PITCH_AMPLITUDE must be in [0, 89] degrees")
    if params["flight_speed"] <= 0:
        errors.append("FLIGHT_SPEED must be positive")
    if params["num_cycles"] < 1:
        errors.append("NUM_CYCLES must be >= 1")

    # Warn (not error) about extreme Strouhal numbers
    if params["flight_speed"] > 0 and params["semi_span"] > 0:
        tip_excursion = 2 * params["semi_span"] * math.sin(
            math.radians(params["flap_amplitude"])
        )
        st = params["flap_frequency"] * tip_excursion / params["flight_speed"]
        if st > 1.0:
            errors.append(
                f"Strouhal number {st:.2f} is very high (>1.0), design may be unphysical"
            )

    return errors


def compute_fitness(results):
    """Compute the primary fitness metric from simulation results.

    The fitness metric is the cycle-averaged thrust coefficient (mean_CT).
    Higher values are better. Positive mean_CT = net thrust production.

    A penalty is applied if the design produces negative mean lift (mean_CL < 0),
    since an ornithopter must support its weight.

    Returns:
        (fitness, metrics_dict)
    """
    ca = results["cycle_averaged"]

    mean_CT = ca["mean_CT"]
    mean_CL = ca["mean_CL"]
    mean_CD = ca["mean_CD"]
    mean_thrust = ca["mean_thrust"]
    mean_lift = ca["mean_lift"]
    mean_drag = ca["mean_drag"]

    # Primary fitness: thrust coefficient
    fitness = mean_CT

    # Penalty for negative lift (can't fly)
    if mean_CL < 0:
        fitness = fitness - 1.0

    # Lift-to-drag ratio (only meaningful when there is net drag)
    # When mean_drag < 0, the wing produces net thrust, so L/D is N/A.
    if mean_drag > 1e-10:
        l_over_d = mean_lift / mean_drag
    elif mean_drag < -1e-10:
        # Net thrust: report lift/|thrust| as a reference
        l_over_d = mean_lift / abs(mean_drag)
    else:
        l_over_d = float("inf") if mean_lift > 0 else 0.0

    metrics = {
        "fitness": fitness,
        "mean_CT": mean_CT,
        "mean_CL": mean_CL,
        "mean_CD": mean_CD,
        "L_over_D": l_over_d,
        "mean_thrust_N": mean_thrust,
        "mean_lift_N": mean_lift,
        "mean_drag_N": mean_drag,
    }

    return fitness, metrics
