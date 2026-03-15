"""
Ornithopter Simulation Script
==============================

Wraps PteraSoftware's Unsteady Ring Vortex Lattice Method (UVLM) solver
for flapping-wing aerodynamic analysis.

Usage: uv run simulate.py

DO NOT MODIFY THIS FILE. Edit design.py to change design parameters.
"""

import json
import math
import sys
import time

import pterasoftware as ps

from design import (
    AIR_DENSITY,
    ASPECT_RATIO,
    DIHEDRAL_ANGLE,
    FLAP_AMPLITUDE,
    FLAP_FREQUENCY,
    FLAP_PERIOD,
    FLIGHT_SPEED,
    KINEMATIC_VISCOSITY,
    MEAN_AOA,
    MEAN_CHORD,
    MID_CHORD,
    MID_CHORD_RATIO,
    MID_SPAN_FRACTION,
    MID_SWEEP_OFFSET,
    MID_Y,
    NUM_CHORDWISE_PANELS,
    NUM_CYCLES,
    NUM_SPANWISE_PANELS,
    PHASE_OFFSET,
    PITCH_AMPLITUDE,
    REDUCED_FREQUENCY,
    REYNOLDS_NUMBER,
    ROOT_AIRFOIL,
    ROOT_CHORD,
    SEMI_SPAN,
    STROUHAL_NUMBER,
    SWEEP_ANGLE,
    TAPER_RATIO,
    TIP_AIRFOIL,
    TIP_CHORD,
    WING_AREA,
)
from evaluate import compute_fitness, validate_design


def get_design_params():
    """Collect design parameters into a dict for validation."""
    return {
        "semi_span": SEMI_SPAN,
        "root_chord": ROOT_CHORD,
        "taper_ratio": TAPER_RATIO,
        "sweep_angle": SWEEP_ANGLE,
        "dihedral_angle": DIHEDRAL_ANGLE,
        "flap_frequency": FLAP_FREQUENCY,
        "flap_amplitude": FLAP_AMPLITUDE,
        "pitch_amplitude": PITCH_AMPLITUDE,
        "phase_offset": PHASE_OFFSET,
        "mean_aoa": MEAN_AOA,
        "flight_speed": FLIGHT_SPEED,
        "num_cycles": NUM_CYCLES,
        "air_density": AIR_DENSITY,
        "kinematic_viscosity": KINEMATIC_VISCOSITY,
        "mid_span_fraction": MID_SPAN_FRACTION,
        "mid_chord_ratio": MID_CHORD_RATIO,
        "mid_sweep_offset": MID_SWEEP_OFFSET,
        "num_spanwise_panels": NUM_SPANWISE_PANELS,
        "num_chordwise_panels": NUM_CHORDWISE_PANELS,
    }


def build_airplane():
    """Construct PteraSoftware Airplane geometry from design parameters.

    Uses a 3-section wing (root → mid → tip) to allow non-linear planform
    shapes (butterfly-like, elliptical, etc.). The mid-section position,
    chord, and sweep offset are controlled by MID_SPAN_FRACTION,
    MID_CHORD_RATIO, and MID_SWEEP_OFFSET.

    Uses symmetric=True with a tiny root offset from the symmetry plane to
    achieve "type 5" symmetry. This auto-creates a reflected wing AND remains
    compatible with flapping motion.
    """
    sweep_offset = SEMI_SPAN * math.tan(math.radians(SWEEP_ANGLE))
    dihedral_offset = SEMI_SPAN * math.sin(math.radians(DIHEDRAL_ANGLE))

    # Mid-section position (linear interpolation of sweep/dihedral + offset)
    mid_x = MID_SPAN_FRACTION * sweep_offset + MID_SWEEP_OFFSET
    mid_z = MID_SPAN_FRACTION * dihedral_offset

    # Split spanwise panels between inner (root→mid) and outer (mid→tip)
    panels_inner = max(2, round(NUM_SPANWISE_PANELS * MID_SPAN_FRACTION))
    panels_outer = max(2, NUM_SPANWISE_PANELS - panels_inner)

    airplane = ps.geometry.airplane.Airplane(
        wings=[
            ps.geometry.wing.Wing(
                wing_cross_sections=[
                    # ROOT
                    ps.geometry.wing_cross_section.WingCrossSection(
                        airfoil=ps.geometry.airfoil.Airfoil(name=ROOT_AIRFOIL),
                        num_spanwise_panels=panels_inner,
                        chord=ROOT_CHORD,
                        Lp_Wcsp_Lpp=(0.0, 0.0, 0.0),
                        control_surface_symmetry_type="symmetric",
                        spanwise_spacing="cosine",
                    ),
                    # MID
                    ps.geometry.wing_cross_section.WingCrossSection(
                        airfoil=ps.geometry.airfoil.Airfoil(name=ROOT_AIRFOIL),
                        num_spanwise_panels=panels_outer,
                        chord=MID_CHORD,
                        Lp_Wcsp_Lpp=(mid_x, MID_Y, mid_z),
                        control_surface_symmetry_type="symmetric",
                        spanwise_spacing="cosine",
                    ),
                    # TIP
                    ps.geometry.wing_cross_section.WingCrossSection(
                        airfoil=ps.geometry.airfoil.Airfoil(name=TIP_AIRFOIL),
                        num_spanwise_panels=None,
                        chord=TIP_CHORD,
                        Lp_Wcsp_Lpp=(sweep_offset, SEMI_SPAN, dihedral_offset),
                        control_surface_symmetry_type="symmetric",
                        spanwise_spacing=None,
                    ),
                ],
                name="Main Wing",
                Ler_Gs_Cgs=(0.0, 0.001, 0.0),
                symmetric=True,
                symmetryNormal_G=(0.0, 1.0, 0.0),
                symmetryPoint_G_Cg=(0.0, 0.0, 0.0),
                num_chordwise_panels=NUM_CHORDWISE_PANELS,
                chordwise_spacing="uniform",
            ),
        ],
        name="Ornithopter",
    )
    return airplane


def build_movement(airplane):
    """Construct PteraSoftware Movement defining flapping kinematics.

    After type 5 processing, airplane.wings has 2 entries:
      [0] = original wing (type 1, no symmetry)
      [1] = reflected wing (type 3, mirror_only)

    Both get the same movement parameters. The mirroring in type 3 mesh
    generation ensures the reflected wing flaps symmetrically with the
    original (both tips go up/down together).
    """
    op = ps.operating_point.OperatingPoint(
        rho=AIR_DENSITY,
        vCg__E=FLIGHT_SPEED,
        alpha=MEAN_AOA,
        beta=0.0,
        nu=KINEMATIC_VISCOSITY,
    )

    wing_movements = []
    for wing in airplane.wings:
        wcs_movements = []
        for wcs in wing.wing_cross_sections:
            wcsm = ps.movements.wing_cross_section_movement.WingCrossSectionMovement(
                base_wing_cross_section=wcs,
            )
            wcs_movements.append(wcsm)

        wm = ps.movements.wing_movement.WingMovement(
            base_wing=wing,
            wing_cross_section_movements=wcs_movements,
            # Flap (x-axis rotation) + pitch (y-axis rotation) at wing level
            ampAngles_Gs_to_Wn_ixyz=(FLAP_AMPLITUDE, PITCH_AMPLITUDE, 0.0),
            periodAngles_Gs_to_Wn_ixyz=(FLAP_PERIOD, FLAP_PERIOD, 0.0),
            phaseAngles_Gs_to_Wn_ixyz=(0.0, PHASE_OFFSET, 0.0),
        )
        wing_movements.append(wm)

    airplane_movement = ps.movements.airplane_movement.AirplaneMovement(
        base_airplane=airplane,
        wing_movements=wing_movements,
    )

    op_movement = ps.movements.operating_point_movement.OperatingPointMovement(
        base_operating_point=op,
    )

    movement = ps.movements.movement.Movement(
        airplane_movements=[airplane_movement],
        operating_point_movement=op_movement,
        delta_time=None,  # auto-optimize timestep size
        num_cycles=NUM_CYCLES,
    )

    return movement


def extract_results(solver):
    """Extract force/moment time series and cycle-averaged data."""
    up = solver.unsteady_problem
    num_steps = up.num_steps
    first_step = up.first_results_step
    dt = up.delta_time

    # Per-timestep forces
    times, lifts, drags, thrusts, CLs, CDs = [], [], [], [], [], []
    for step in range(first_step, num_steps):
        ap = up.steady_problems[step].airplanes[0]
        t = step * dt
        times.append(t)
        thrusts.append(float(ap.forces_W[0]))        # +FX = thrust
        drags.append(float(-ap.forces_W[0]))          # drag = -FX
        lifts.append(float(-ap.forces_W[2]))          # lift = -FZ
        CLs.append(float(-ap.forceCoefficients_W[2]))
        CDs.append(float(-ap.forceCoefficients_W[0]))

    # Cycle-averaged results
    mean_forces = up.finalMeanForces_W[0]
    mean_coeffs = up.finalMeanForceCoefficients_W[0]
    rms_forces = up.finalRmsForces_W[0]

    return {
        "time_series": {
            "times": times,
            "lifts": lifts,
            "drags": drags,
            "thrusts": thrusts,
            "CLs": CLs,
            "CDs": CDs,
        },
        "cycle_averaged": {
            "mean_thrust": float(mean_forces[0]),
            "mean_lift": float(-mean_forces[2]),
            "mean_drag": float(-mean_forces[0]),
            "mean_CT": float(mean_coeffs[0]),
            "mean_CL": float(-mean_coeffs[2]),
            "mean_CD": float(-mean_coeffs[0]),
            "rms_thrust": float(rms_forces[0]),
            "rms_lift": float(rms_forces[2]),
        },
        "design_info": {
            "semi_span": SEMI_SPAN,
            "root_chord": ROOT_CHORD,
            "taper_ratio": TAPER_RATIO,
            "mid_span_fraction": MID_SPAN_FRACTION,
            "mid_chord_ratio": MID_CHORD_RATIO,
            "mid_sweep_offset": MID_SWEEP_OFFSET,
            "aspect_ratio": ASPECT_RATIO,
            "wing_area": WING_AREA,
            "mean_chord": MEAN_CHORD,
            "flap_frequency": FLAP_FREQUENCY,
            "flap_amplitude": FLAP_AMPLITUDE,
            "pitch_amplitude": PITCH_AMPLITUDE,
            "phase_offset": PHASE_OFFSET,
            "flight_speed": FLIGHT_SPEED,
            "mean_aoa": MEAN_AOA,
            "reynolds_number": REYNOLDS_NUMBER,
            "strouhal_number": STROUHAL_NUMBER,
            "reduced_frequency": REDUCED_FREQUENCY,
        },
        "solver_info": {
            "num_steps": num_steps,
            "first_results_step": first_step,
            "delta_time": dt,
            "num_cycles": NUM_CYCLES,
        },
    }


def main():
    # Validate design parameters
    params = get_design_params()
    errors = validate_design(params)
    if errors:
        print("DESIGN VALIDATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("=" * 60)
    print("ORNITHOPTER SIMULATION")
    print("=" * 60)
    print()
    print("Design:")
    print(
        f"  Wing: span={2*SEMI_SPAN:.3f}m, root_chord={ROOT_CHORD:.3f}m, "
        f"taper={TAPER_RATIO:.2f}, AR={ASPECT_RATIO:.1f}"
    )
    print(
        f"  Kinematics: f={FLAP_FREQUENCY:.1f}Hz, flap={FLAP_AMPLITUDE:.1f}deg, "
        f"pitch={PITCH_AMPLITUDE:.1f}deg, phase={PHASE_OFFSET:.1f}deg"
    )
    print(f"  Flight: V={FLIGHT_SPEED:.1f}m/s, AoA={MEAN_AOA:.1f}deg")
    print(
        f"  Dimensionless: Re={REYNOLDS_NUMBER:.0f}, St={STROUHAL_NUMBER:.3f}, "
        f"k={REDUCED_FREQUENCY:.3f}"
    )
    print()

    # Build geometry
    print("Building geometry...")
    t0 = time.time()
    airplane = build_airplane()
    movement = build_movement(airplane)
    t_build = time.time() - t0
    print(f"  Built in {t_build:.1f}s")

    # Run solver
    print("Running UVLM simulation...")
    t0 = time.time()
    problem = ps.problems.UnsteadyProblem(movement=movement)
    solver = (
        ps.unsteady_ring_vortex_lattice_method.UnsteadyRingVortexLatticeMethodSolver(
            unsteady_problem=problem,
        )
    )
    solver.run(prescribed_wake=True, logging_level="Info")
    sim_time = time.time() - t0
    print(f"  Completed in {sim_time:.1f}s")

    # Extract and evaluate
    results = extract_results(solver)
    fitness, metrics = compute_fitness(results)

    # Save detailed results to JSON
    with open("sim_output.json", "w") as f:
        json.dump(results, f, indent=2)

    # Print summary (grep-able format, matches autoresearch pattern)
    print()
    print("---")
    print(f"fitness:          {fitness:.6f}")
    if "penalties" in metrics:
        for name, value in metrics["penalties"].items():
            print(f"penalty_{name}:    {value:.6f}")
    print(f"mean_thrust_N:    {metrics['mean_thrust_N']:.6f}")
    print(f"mean_lift_N:      {metrics['mean_lift_N']:.6f}")
    print(f"corrected_thrust: {metrics['corrected_thrust_N']:.6f}")
    print(f"parasitic_drag_N: {metrics['parasitic_drag_N']:.6f}")
    print(f"P_flap_est_W:     {metrics['P_flap_est_W']:.3f}")
    print(f"mean_CT:          {metrics['mean_CT']:.6f}")
    print(f"mean_CL:          {metrics['mean_CL']:.6f}")
    print(f"L_over_D:         {metrics['L_over_D']:.6f}{'  (net thrust)' if metrics['mean_drag_N'] < 0 else ''}")
    print(f"sim_seconds:      {sim_time:.1f}")
    print(f"num_steps:        {results['solver_info']['num_steps']}")
    print(f"reynolds:         {REYNOLDS_NUMBER:.0f}")
    print(f"strouhal:         {STROUHAL_NUMBER:.3f}")
    print(f"reduced_freq:     {REDUCED_FREQUENCY:.3f}")

    return fitness


if __name__ == "__main__":
    try:
        fitness = main()
    except Exception as e:
        print(f"\nSIMULATION FAILED: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
