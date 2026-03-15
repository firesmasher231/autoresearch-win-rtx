"""
Ornithopter Design Evaluation
==============================

Computes fitness metrics from simulation results.

DO NOT MODIFY THIS FILE. This is the ground truth evaluation,
analogous to prepare.py's evaluate_bpb in autoresearch.

Primary metric: fitness (based on cycle-averaged thrust coefficient).
Higher fitness = better design. The goal is to maximize fitness.

Physics validity enforcement
-----------------------------
UVLM is an inviscid potential-flow solver. It has known blind spots that
an optimizer WILL exploit if left unchecked:

  1. No stall model — lift increases linearly with AoA forever (CL ≈ 2πα),
     when real wings stall at ~12-15° and lose lift.
  2. No collision detection — wings can pass through each other and the
     solver happily computes forces on intersecting geometry.
  3. Coefficient normalization — dividing by dynamic pressure (½ρv²) means
     near-zero flight speed inflates coefficients to infinity.

The penalties below prevent the agent from farming these artifacts.

Hard blocks (validate_design — prevent simulation from running):
  - Wing self-intersection: |dihedral| + flap_amplitude >= 90°
  - AoA beyond UVLM validity: |mean_aoa| > 25°
  - Extreme dihedral: |dihedral| > 45°
  - Flight speed too low: < 1.0 m/s
  - Extreme aspect ratio: AR > 15

Soft penalties (compute_fitness — simulation runs but fitness is crushed):
  - Coefficient cap: mean_CT capped at 2.0
  - Stall regime: quadratic penalty for |AoA| > 15°
  - Negative lift: -1.0 (can't fly without lift)
"""

import math


# Maximum physically plausible thrust coefficient.
# Real flapping wings produce CT in 0–1.0. Values above 2.0 indicate the
# simulation is in an unphysical regime. This cap prevents the agent from
# being rewarded for exploiting UVLM artifacts.
MAX_PLAUSIBLE_CT = 2.0


def validate_design(params):
    """Check design parameters for physical plausibility.

    Returns a list of error strings. Empty list = valid design.
    Hard errors prevent the simulation from running — these catch
    configurations where UVLM would produce meaningless results.
    """
    errors = []

    # --- Basic parameter validity ---

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

    # --- Wing self-intersection (HARD BLOCK) ---
    # Symmetric wings flap about the body axis. When |dihedral| + flap_amplitude
    # >= 90°, the wingtip crosses the symmetry plane during the stroke, meaning
    # left and right wings pass through each other. UVLM has NO collision
    # detection — it computes forces on intersecting geometry, producing
    # completely meaningless results.
    # The agent previously exploited this (dihedral=40° + amplitude=70° = 110°)
    # to reach fitness ~331 with wings clipping through themselves.
    dihedral = params.get("dihedral_angle", 0)
    flap_amp = params.get("flap_amplitude", 0)
    total_excursion = abs(dihedral) + flap_amp
    if total_excursion >= 90:
        errors.append(
            f"WING SELF-INTERSECTION: |dihedral| ({abs(dihedral):.1f}°) + "
            f"flap_amplitude ({flap_amp:.1f}°) = {total_excursion:.1f}° >= 90°. "
            f"Wings would clip through each other. Reduce dihedral or amplitude."
        )

    # --- AoA beyond UVLM validity (HARD BLOCK) ---
    # UVLM is inviscid potential flow. It CANNOT model stall (flow separation).
    # Real wings stall at 12-15° AoA. UVLM predicts lift increasing linearly
    # forever, producing arbitrarily large fantasy coefficients.
    # The agent previously exploited this (AoA = -80°) to get CT = 331.
    # Hard block at 25° (generous margin); soft penalty starts at 15°.
    mean_aoa = params.get("mean_aoa", 0)
    if abs(mean_aoa) > 25:
        errors.append(
            f"|MEAN_AOA| = {abs(mean_aoa):.1f}° exceeds 25°. UVLM cannot model "
            f"stall — results above ~15° are increasingly unreliable, and "
            f"above 25° are pure fiction. Use |MEAN_AOA| <= 25°."
        )

    # --- Extreme dihedral (HARD BLOCK) ---
    # Dihedral > 45° is structurally impossible for a real wing and produces
    # bizarre force decompositions in the simulation.
    if abs(dihedral) > 45:
        errors.append(
            f"|DIHEDRAL_ANGLE| = {abs(dihedral):.1f}° exceeds 45°. "
            f"Real ornithopters use 0-10° dihedral. Max allowed: 45°."
        )

    # --- Flight speed floor (HARD BLOCK) ---
    # Force coefficients are normalized by dynamic pressure q = ½ρv².
    # Near-zero v makes q ≈ 0, inflating coefficients to infinity even
    # with negligible actual forces. Below 1 m/s the coefficients are
    # numerically meaningless.
    if 0 < params["flight_speed"] < 1.0:
        errors.append(
            f"FLIGHT_SPEED = {params['flight_speed']:.2f} m/s is too low. "
            f"Below 1 m/s, force coefficients are normalized by near-zero "
            f"dynamic pressure, producing inflated values. Minimum: 1.0 m/s."
        )

    # --- Extreme aspect ratio (HARD BLOCK) ---
    # Very high AR with thin chord is structurally impossible for a flapping
    # wing and gives unreliable UVLM results at low Reynolds numbers where
    # viscous effects dominate.
    if params["semi_span"] > 0 and params["root_chord"] > 0:
        mean_chord = params["root_chord"] * (1 + params["taper_ratio"]) / 2
        wing_area = mean_chord * params["semi_span"] * 2
        ar = (2 * params["semi_span"]) ** 2 / wing_area
        if ar > 15:
            errors.append(
                f"Aspect ratio {ar:.1f} exceeds 15. Structurally infeasible "
                f"for a flapping wing — the spar would snap. Real flapping-wing "
                f"MAVs use AR 3-10."
            )

    # --- Locked physical constants ---
    # These are properties of the environment, not the design. Changing them
    # is not "optimizing the ornithopter" — it's changing the laws of physics.
    if "air_density" in params and params["air_density"] != 1.225:
        errors.append(
            f"AIR_DENSITY = {params['air_density']} but must be 1.225 kg/m³ "
            f"(sea level standard). This is a physical constant, not a design parameter."
        )
    if "kinematic_viscosity" in params and params["kinematic_viscosity"] != 15.06e-6:
        errors.append(
            f"KINEMATIC_VISCOSITY = {params['kinematic_viscosity']} but must be "
            f"15.06e-6 m²/s (air at ~20°C). This is a physical constant, not a design parameter."
        )

    # --- Locked simulation parameters ---
    # NUM_CYCLES: fewer cycles = unreliable cycle-averaging (the last cycle
    # is used for mean forces — it needs preceding cycles to reach periodicity).
    # More than 3 wastes time. Lock at 3.
    if "num_cycles" in params and params["num_cycles"] != 3:
        errors.append(
            f"NUM_CYCLES = {params['num_cycles']} but must be 3. "
            f"Cycle count affects result quality and must stay fixed."
        )

    # Panel count floors: fewer panels = faster but noisier results.
    # The agent could reduce panels to game speed at the cost of accuracy.
    # Minimum 4 spanwise, 3 chordwise for any meaningful UVLM result.
    if "num_spanwise_panels" in params and params["num_spanwise_panels"] < 4:
        errors.append(
            f"NUM_SPANWISE_PANELS = {params['num_spanwise_panels']} is below minimum (4). "
            f"Too few panels for reliable UVLM results."
        )
    if "num_chordwise_panels" in params and params["num_chordwise_panels"] < 3:
        errors.append(
            f"NUM_CHORDWISE_PANELS = {params['num_chordwise_panels']} is below minimum (3). "
            f"Too few panels for reliable UVLM results."
        )

    # --- Strouhal number sanity ---
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

    Base metric: cycle-averaged thrust coefficient (mean_CT).

    Physics penalties (applied in order):
      1. Coefficient cap: CT capped at MAX_PLAUSIBLE_CT (2.0)
      2. Stall regime: quadratic penalty for |AoA| > 15°
      3. Negative lift: -1.0 (ornithopter must support its weight)

    These penalties exist because UVLM is inviscid and produces
    arbitrarily large coefficients in unphysical regimes. Without them,
    the optimizer will find and exploit these simulation artifacts
    instead of finding genuinely good designs.

    Returns:
        (fitness, metrics_dict)
    """
    ca = results["cycle_averaged"]
    di = results["design_info"]

    mean_CT = ca["mean_CT"]
    mean_CL = ca["mean_CL"]
    mean_CD = ca["mean_CD"]
    mean_thrust = ca["mean_thrust"]
    mean_lift = ca["mean_lift"]
    mean_drag = ca["mean_drag"]

    penalties = {}

    # --- Coefficient cap ---
    # Real flapping wings produce CT in 0-1.0 range. Values above
    # MAX_PLAUSIBLE_CT indicate an unphysical simulation regime.
    if mean_CT > MAX_PLAUSIBLE_CT:
        penalties["coefficient_cap"] = MAX_PLAUSIBLE_CT - mean_CT
        fitness = MAX_PLAUSIBLE_CT
    else:
        fitness = mean_CT

    # --- Stall regime penalty ---
    # UVLM results degrade past ~12° AoA and are meaningless by ~25°.
    # Quadratic penalty starting at 15° makes stall-exploiting designs
    # uncompetitive without punishing legitimate high-AoA exploration.
    #   16° → -0.1,  18° → -0.9,  20° → -2.5,  25° → -10.0
    aoa = abs(di["mean_aoa"])
    if aoa > 15:
        stall_penalty = -((aoa - 15) ** 2) * 0.1
        fitness += stall_penalty
        penalties["stall_regime"] = stall_penalty

    # --- Negative lift penalty ---
    # An ornithopter must produce positive mean lift to support its weight.
    if mean_CL < 0:
        fitness -= 1.0
        penalties["negative_lift"] = -1.0

    # --- Lift-to-drag ratio ---
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

    if penalties:
        metrics["penalties"] = penalties

    return fitness, metrics
