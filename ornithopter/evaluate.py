"""
Ornithopter Design Evaluation
==============================

Computes fitness metrics from simulation results.

DO NOT MODIFY THIS FILE. This is the ground truth evaluation,
analogous to prepare.py's evaluate_bpb in autoresearch.

Fitness metric: multiplicative composite
------------------------------------------
fitness = thrust_score × strouhal_score × lift_score

Each factor is in [0, 1]. All three must be good for high fitness.
Maximum possible fitness = 1.0. Typical good design: 0.1-0.4.

Components:
  thrust_score:   Saturating function of corrected thrust (N).
                  Diminishing returns prevent "more force = always better".
  strouhal_score: Gaussian peaked at St=0.30 (biological optimum).
                  Forces the agent to balance f, amplitude, span, and speed
                  rather than pushing any single parameter to its limit.
  lift_score:     Ramp from 0 to 1 at target lift (0.49N for 50g).
                  The design must fly before efficiency matters.

Why this structure?
  Previous metrics were all trivially maximizable:
  - Raw CT: agent pushed AoA to -80° → CT=331
  - CT with cap: agent hit cap in 34 experiments and stopped
  - Thrust/power ratio: V² in numerator, not in denominator; S cancels;
    P_flap floor reachable within bounds → fitness=30+ trivially

  The multiplicative composite has NO ratio to game, NO denominator to
  minimize, and the Strouhal constraint creates a genuine multi-variable
  optimization problem with no trivial solution.

UVLM correction
-----------------
UVLM is an inviscid potential-flow solver that overestimates forces by
~2-3x at the low Reynolds numbers (10k-50k) of MAV ornithopters. A
correction factor of 0.5 is applied to all UVLM forces before fitness
computation. This doesn't change which design is best (it's a constant
multiplier on forces), but it prevents the agent from seeing unrealistic
force magnitudes that might lead it to declare success prematurely.
"""

import math


# --- Physical constants ---
RHO = 1.225  # air density at sea level (kg/m³), locked

# --- UVLM correction ---
# UVLM overestimates forces at low Re (no viscous losses, no stall).
# At Re=10k-50k typical of MAV ornithopters, real forces are ~40-60%
# of UVLM predictions. Apply 0.5 correction to all forces.
UVLM_CORRECTION = 0.50

# --- Parasitic drag ---
# UVLM doesn't model skin friction. Subtract estimated profile + body drag.
CD_PARASITE = 0.03

# --- Lift target ---
# 50g × 9.81 m/s² = 0.49N. Design must support its own weight.
TARGET_LIFT_N = 0.49

# --- Thrust scoring ---
# Saturating function: score = thrust / (thrust + halfpoint)
# At halfpoint thrust, score = 0.5. Diminishing returns above.
# 0.10N corrected thrust gives score=0.5. At 0.30N score=0.75, at 1.0N score=0.91.
# This spreads the gradient across the realistic thrust range for a 50g MAV.
THRUST_HALFPOINT_N = 0.10

# --- Strouhal scoring ---
# Biological flyers converge on St=0.2-0.4 because this range maximizes
# propulsive efficiency. The Gaussian peaks at 0.30 with σ=0.12, giving
# score > 0.5 within [0.18, 0.42] — matching the biological optimum.
# This is the KEY anti-exploit mechanism: it forces the agent to BALANCE
# frequency, amplitude, span, and speed rather than maximizing any one.
ST_OPTIMAL = 0.30
ST_SIGMA = 0.12

# --- Physical bounds ---
PHYSICAL_BOUNDS = {
    "semi_span":       (0.10, 0.25),
    "root_chord":      (0.04, 0.10),
    "taper_ratio":     (0.30, 1.00),
    "sweep_angle":     (0.0,  15.0),
    "dihedral_angle":  (0.0,   8.0),
    "mid_span_fraction": (0.20, 0.80),
    "mid_chord_ratio": (0.50, 2.00),
    "mid_sweep_offset": (-0.02, 0.02),
    "flap_frequency":  (8.0,  18.0),
    "flap_amplitude":  (20.0, 55.0),
    "pitch_amplitude": (10.0, 30.0),
    "phase_offset":    (75.0, 105.0),
    "mean_aoa":        (2.0,   8.0),
    "flight_speed":    (2.0,   8.0),
}

_PARAM_NAMES = {
    "semi_span": "SEMI_SPAN",
    "root_chord": "ROOT_CHORD",
    "taper_ratio": "TAPER_RATIO",
    "sweep_angle": "SWEEP_ANGLE",
    "dihedral_angle": "DIHEDRAL_ANGLE",
    "mid_span_fraction": "MID_SPAN_FRACTION",
    "mid_chord_ratio": "MID_CHORD_RATIO",
    "mid_sweep_offset": "MID_SWEEP_OFFSET",
    "flap_frequency": "FLAP_FREQUENCY",
    "flap_amplitude": "FLAP_AMPLITUDE",
    "pitch_amplitude": "PITCH_AMPLITUDE",
    "phase_offset": "PHASE_OFFSET",
    "mean_aoa": "MEAN_AOA",
    "flight_speed": "FLIGHT_SPEED",
}


def validate_design(params):
    """Check design parameters for physical plausibility.

    Returns a list of error strings. Empty list = valid design.
    Hard errors prevent the simulation from running.
    """
    errors = []

    # --- Physical bounds (buildable MAV range) ---
    for param, (lo, hi) in PHYSICAL_BOUNDS.items():
        if param in params:
            val = params[param]
            if val < lo or val > hi:
                name = _PARAM_NAMES.get(param, param.upper())
                errors.append(
                    f"{name} = {val} is outside buildable range [{lo}, {hi}]. "
                    f"See build_details.md."
                )

    # --- Basic parameter validity ---
    if params["semi_span"] <= 0:
        errors.append("SEMI_SPAN must be positive")
    if params["root_chord"] <= 0:
        errors.append("ROOT_CHORD must be positive")
    if not (0 < params["taper_ratio"] <= 1.0):
        errors.append("TAPER_RATIO must be in (0, 1.0]")
    if params["flap_frequency"] <= 0:
        errors.append("FLAP_FREQUENCY must be positive")
    if params["flight_speed"] <= 0:
        errors.append("FLIGHT_SPEED must be positive")
    if params["num_cycles"] < 1:
        errors.append("NUM_CYCLES must be >= 1")

    # --- Wing self-intersection (safety net) ---
    dihedral = params.get("dihedral_angle", 0)
    flap_amp = params.get("flap_amplitude", 0)
    if abs(dihedral) + flap_amp >= 90:
        errors.append(
            f"WING SELF-INTERSECTION: |dihedral| ({abs(dihedral):.1f}°) + "
            f"flap_amplitude ({flap_amp:.1f}°) >= 90°. "
            f"Wings would clip through each other."
        )

    # --- Extreme aspect ratio (using 3-section wing area) ---
    if params["semi_span"] > 0 and params["root_chord"] > 0:
        mid_frac = params.get("mid_span_fraction", 0.5)
        mid_ratio = params.get("mid_chord_ratio", 0.75)
        rc = params["root_chord"]
        tr = params["taper_ratio"]
        b = params["semi_span"]
        mid_chord = rc * mid_ratio
        tip_chord = rc * tr
        mid_y = mid_frac * b
        wing_area = ((rc + mid_chord) / 2 * mid_y +
                     (mid_chord + tip_chord) / 2 * (b - mid_y)) * 2
        ar = (2 * b) ** 2 / wing_area if wing_area > 0 else 999
        if ar > 15:
            errors.append(
                f"Aspect ratio {ar:.1f} exceeds 15. Structurally infeasible "
                f"for a flapping wing."
            )

    # --- Locked physical constants ---
    if "air_density" in params and params["air_density"] != 1.225:
        errors.append(
            f"AIR_DENSITY = {params['air_density']} but must be 1.225 kg/m³. "
            f"This is a physical constant, not a design parameter."
        )
    if "kinematic_viscosity" in params and params["kinematic_viscosity"] != 15.06e-6:
        errors.append(
            f"KINEMATIC_VISCOSITY = {params['kinematic_viscosity']} but must be "
            f"15.06e-6 m²/s. This is a physical constant, not a design parameter."
        )

    # --- Locked simulation parameters ---
    if "num_cycles" in params and params["num_cycles"] != 3:
        errors.append(
            f"NUM_CYCLES = {params['num_cycles']} but must be 3. "
            f"Cycle count affects result quality and must stay fixed."
        )
    if "num_spanwise_panels" in params and params["num_spanwise_panels"] < 4:
        errors.append(
            f"NUM_SPANWISE_PANELS = {params['num_spanwise_panels']} is below minimum (4)."
        )
    if "num_chordwise_panels" in params and params["num_chordwise_panels"] < 3:
        errors.append(
            f"NUM_CHORDWISE_PANELS = {params['num_chordwise_panels']} is below minimum (3)."
        )

    # --- Strouhal number sanity ---
    if params["flight_speed"] > 0 and params["semi_span"] > 0:
        tip_excursion = 2 * params["semi_span"] * math.sin(
            math.radians(params["flap_amplitude"])
        )
        st = params["flap_frequency"] * tip_excursion / params["flight_speed"]
        if st > 1.0:
            errors.append(
                f"Strouhal number {st:.2f} exceeds 1.0 — design is unphysical."
            )

    return errors


def compute_fitness(results):
    """Compute fitness as a multiplicative composite of three scores.

    fitness = thrust_score × strouhal_score × lift_score

    Each score is in [0, 1]. The product is maximized only when ALL three
    are simultaneously good. This prevents gaming any single axis.

    thrust_score:   saturating(corrected_thrust)  — diminishing returns
    strouhal_score: gaussian(St, peak=0.30)       — must hit bio-optimal range
    lift_score:     ramp(corrected_lift, 0→0.49N) — must support weight

    Returns:
        (fitness, metrics_dict)
    """
    ca = results["cycle_averaged"]
    di = results["design_info"]

    mean_thrust = ca["mean_thrust"]
    mean_lift = ca["mean_lift"]
    mean_CT = ca["mean_CT"]
    mean_CL = ca["mean_CL"]
    mean_CD = ca["mean_CD"]
    mean_drag = ca["mean_drag"]

    V = di["flight_speed"]
    S = di["wing_area"]

    # --- Apply UVLM correction ---
    # UVLM overpredicts forces at low Re. Scale all forces by correction factor.
    corrected_thrust = mean_thrust * UVLM_CORRECTION
    corrected_lift = mean_lift * UVLM_CORRECTION

    # --- Subtract parasitic drag from thrust ---
    # UVLM doesn't model skin friction. Real net thrust is lower.
    q = 0.5 * RHO * V ** 2
    parasitic_drag = q * S * CD_PARASITE
    corrected_thrust -= parasitic_drag

    # --- THRUST SCORE (saturating, diminishing returns) ---
    # score = thrust / (thrust + halfpoint)
    # At halfpoint: score = 0.5. Asymptotes to 1.0.
    # Negative thrust → score = 0.
    if corrected_thrust > 0:
        thrust_score = corrected_thrust / (corrected_thrust + THRUST_HALFPOINT_N)
    else:
        thrust_score = 0.0

    # --- STROUHAL SCORE (Gaussian around biological optimum) ---
    # St = f * tip_excursion / V. Biological flyers: St=0.2-0.4.
    # Gaussian peaks at 0.30 with σ=0.12.
    # This is the KEY constraint: it forces the agent to BALANCE
    # frequency, amplitude, span, and speed. Pushing any single
    # parameter to its limit moves St away from the optimum.
    st = di["strouhal_number"]
    strouhal_score = math.exp(-((st - ST_OPTIMAL) / ST_SIGMA) ** 2)

    # --- LIFT SCORE (ramp to target, then saturates) ---
    # Must produce enough lift to support 50g.
    if corrected_lift <= 0:
        lift_score = 0.0
    elif corrected_lift < TARGET_LIFT_N:
        lift_score = corrected_lift / TARGET_LIFT_N
    else:
        lift_score = 1.0

    # --- COMPOSITE FITNESS ---
    fitness = thrust_score * strouhal_score * lift_score

    # --- Informational metrics ---
    if mean_drag > 1e-10:
        l_over_d = mean_lift / mean_drag
    elif mean_drag < -1e-10:
        l_over_d = mean_lift / abs(mean_drag)
    else:
        l_over_d = float("inf") if mean_lift > 0 else 0.0

    metrics = {
        "fitness": fitness,
        "thrust_score": thrust_score,
        "strouhal_score": strouhal_score,
        "lift_score": lift_score,
        "strouhal": st,
        "corrected_thrust_N": corrected_thrust,
        "corrected_lift_N": corrected_lift,
        "parasitic_drag_N": parasitic_drag,
        "mean_CT": mean_CT,
        "mean_CL": mean_CL,
        "mean_CD": mean_CD,
        "L_over_D": l_over_d,
        "mean_thrust_N": mean_thrust,
        "mean_lift_N": mean_lift,
        "mean_drag_N": mean_drag,
    }

    return fitness, metrics
