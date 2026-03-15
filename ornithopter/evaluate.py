"""
Ornithopter Design Evaluation
==============================

Computes fitness metrics from simulation results.

DO NOT MODIFY THIS FILE. This is the ground truth evaluation,
analogous to prepare.py's evaluate_bpb in autoresearch.

Fitness metric: propulsive efficiency
--------------------------------------
fitness = corrected_thrust / P_flap_estimate

Where:
  corrected_thrust = UVLM thrust - estimated parasitic drag (N)
  P_flap_estimate  = (rho/6) * v_tip^3 * S_wing (watts)

This measures how much useful thrust the design produces per watt of
estimated flapping power. Higher = more efficient = better design.

Why not raw CT (thrust coefficient)?
  CT is trivially maximizable — the agent just cranks frequency, amplitude,
  and AoA to produce huge coefficients that are physically meaningless.
  CT = 2.81 was reached in 34 experiments by pushing every parameter to its
  limit. The efficiency metric instead rewards designs that produce thrust
  CHEAPLY (low flapping power), which is what actually matters for a
  battery-powered MAV.

Physical bounds enforcement
----------------------------
All design parameters must fall within the buildable ranges for a 30-100g
MAV ornithopter. These are enforced as hard blocks in validate_design.
See build_details.md for the physical justification of each bound.

Lift floor
-----------
The design must produce at least 0.49N of mean lift (supporting 50g against
gravity). Designs below this threshold receive a steep penalty that dominates
the efficiency score, forcing the agent to meet the lift requirement before
optimizing efficiency.
"""

import math


# Air density at sea level, 20°C (locked physical constant)
RHO = 1.225

# Minimum lift to support target weight: 50g * 9.81 m/s²
TARGET_LIFT_N = 0.49

# Estimated parasitic drag coefficient (profile drag + body drag).
# UVLM is inviscid and does not compute viscous drag. This correction
# prevents the agent from being rewarded for "free thrust" that would
# be eaten by skin friction in reality.
CD_PARASITE = 0.03

# Physical bounds for a buildable 30-100g MAV ornithopter.
# Enforced as hard blocks — simulation won't run outside these ranges.
PHYSICAL_BOUNDS = {
    "semi_span":       (0.10, 0.25),   # total wingspan 200-500mm
    "root_chord":      (0.04, 0.10),   # wing chord at root (m)
    "taper_ratio":     (0.30, 1.00),   # tip chord / root chord
    "sweep_angle":     (0.0,  15.0),   # quarter-chord sweep (deg)
    "dihedral_angle":  (0.0,   8.0),   # wing dihedral (deg)
    "flap_frequency":  (8.0,  18.0),   # flapping frequency (Hz)
    "flap_amplitude":  (20.0, 55.0),   # half-stroke amplitude (deg)
    "pitch_amplitude": (10.0, 30.0),   # max pitch angle (deg)
    "phase_offset":    (75.0, 105.0),  # pitch-flap phase lag (deg)
    "mean_aoa":        (2.0,   8.0),   # body angle of attack (deg)
    "flight_speed":    (2.0,   8.0),   # forward airspeed (m/s)
}

# Human-readable names for error messages
_PARAM_NAMES = {
    "semi_span": "SEMI_SPAN",
    "root_chord": "ROOT_CHORD",
    "taper_ratio": "TAPER_RATIO",
    "sweep_angle": "SWEEP_ANGLE",
    "dihedral_angle": "DIHEDRAL_ANGLE",
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
    # With physical bounds (dihedral <= 8, amplitude <= 55), max total is
    # 63° — well below 90°. But keep this check as defense in depth.
    dihedral = params.get("dihedral_angle", 0)
    flap_amp = params.get("flap_amplitude", 0)
    if abs(dihedral) + flap_amp >= 90:
        errors.append(
            f"WING SELF-INTERSECTION: |dihedral| ({abs(dihedral):.1f}°) + "
            f"flap_amplitude ({flap_amp:.1f}°) >= 90°. "
            f"Wings would clip through each other."
        )

    # --- Extreme aspect ratio ---
    if params["semi_span"] > 0 and params["root_chord"] > 0:
        mean_chord = params["root_chord"] * (1 + params["taper_ratio"]) / 2
        wing_area = mean_chord * params["semi_span"] * 2
        ar = (2 * params["semi_span"]) ** 2 / wing_area
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
    """Compute fitness as propulsive efficiency: thrust per watt of flapping power.

    fitness = corrected_thrust / P_flap_estimate

    Where:
      corrected_thrust = UVLM mean thrust - parasitic drag estimate (N)
      P_flap_estimate  = (rho/6) * v_tip^3 * wing_area (watts)
        v_tip = 2*pi*f * semi_span * sin(flap_amplitude)

    The parasitic drag correction accounts for viscous drag that UVLM
    (inviscid solver) does not model. Without it, the agent gets "free"
    thrust at high speeds.

    P_flap_estimate captures the cubic scaling of flapping power with tip
    speed — the dominant cost of flapping flight. Higher frequency, larger
    amplitude, or longer span all increase tip speed and thus power cubically.

    Lift floor: mean_lift must reach 0.49N (50g weight support). Designs
    below this get a steep penalty that dominates the efficiency score.

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

    V = di["flight_speed"]
    S = di["wing_area"]
    f = di["flap_frequency"]
    b = di["semi_span"]
    amp_rad = math.radians(di["flap_amplitude"])

    penalties = {}

    # --- Parasitic drag correction ---
    # UVLM is inviscid: it computes pressure forces but not skin friction.
    # A real wing has profile drag + body drag ≈ Cd_parasite * q * S.
    # Subtract this from UVLM thrust to get realistic net thrust.
    q = 0.5 * RHO * V ** 2
    parasitic_drag = q * S * CD_PARASITE
    corrected_thrust = mean_thrust - parasitic_drag

    # --- Estimated flapping power (watts) ---
    # Tip speed of the wing during flapping:
    #   v_tip = 2*pi*f * semi_span * sin(flap_amplitude)
    # Power scales as v_tip^3 (aerodynamic drag on oscillating wing),
    # with span-averaging factor of 1/3 (velocity varies from 0 at root
    # to v_tip at tip, and power ~ v^3, so integral of (r/b)^3 = 1/4,
    # combined with 1/2 from dynamic pressure gives 1/6 overall).
    v_tip = 2 * math.pi * f * b * math.sin(amp_rad)
    P_flap = (RHO / 6) * v_tip ** 3 * S
    P_flap = max(P_flap, 0.01)  # floor to prevent division by zero

    # --- Base fitness: propulsive efficiency (N/W) ---
    fitness = corrected_thrust / P_flap

    # --- Lift floor ---
    # The ornithopter must produce enough lift to support its weight.
    # This is the PRIMARY constraint — without adequate lift, efficiency
    # is meaningless. The penalty is much larger than typical fitness values
    # (which are ~0.01-0.15 N/W), forcing the agent to solve lift first.
    if mean_lift < 0:
        penalties["negative_lift"] = -10.0
        fitness -= 10.0
    elif mean_lift < TARGET_LIFT_N:
        deficit_penalty = 5.0 * (1 - mean_lift / TARGET_LIFT_N)
        penalties["insufficient_lift"] = -deficit_penalty
        fitness -= deficit_penalty

    # --- Lift-to-drag ratio (informational) ---
    if mean_drag > 1e-10:
        l_over_d = mean_lift / mean_drag
    elif mean_drag < -1e-10:
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
        "corrected_thrust_N": corrected_thrust,
        "parasitic_drag_N": parasitic_drag,
        "P_flap_est_W": P_flap,
    }

    if penalties:
        metrics["penalties"] = penalties

    return fitness, metrics
