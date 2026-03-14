"""
Ornithopter Visualization Script
=================================

Visualize the current ornithopter design from design.py.

Usage:
    uv run visualize.py                       # 3D animation (default)
    uv run visualize.py animate               # 3D animation, uniform color
    uv run visualize.py animate --lift        # color panels by lift
    uv run visualize.py animate --wake        # show trailing wake vortices
    uv run visualize.py animate --save        # save animation as WebP
    uv run visualize.py record                # record to GIF (no interaction needed)
    uv run visualize.py record --lift --wake  # record with lift coloring + wake
    uv run visualize.py plot                  # force/moment time-series plots
    uv run visualize.py plot --save           # save plots as PNGs
    uv run visualize.py plot --from-json      # plot from saved sim_output.json (no re-run)
"""

import argparse
import json
import math
import os
import sys
import time

import matplotlib.pyplot as plt
import numpy as np
import pterasoftware as ps
import pyvista as pv

from simulate import build_airplane, build_movement, extract_results, get_design_params
from evaluate import validate_design
from design import (
    SEMI_SPAN, ROOT_CHORD, TAPER_RATIO, ASPECT_RATIO,
    FLAP_FREQUENCY, FLAP_AMPLITUDE, PITCH_AMPLITUDE, PHASE_OFFSET,
    FLIGHT_SPEED, MEAN_AOA, REYNOLDS_NUMBER, STROUHAL_NUMBER,
    REDUCED_FREQUENCY, NUM_CYCLES,
)


def run_simulation():
    """Build geometry, run solver, return solver object and results."""
    params = get_design_params()
    errors = validate_design(params)
    if errors:
        print("DESIGN VALIDATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("Building geometry...")
    t0 = time.time()
    airplane = build_airplane()
    movement = build_movement(airplane)
    print(f"  Built in {time.time() - t0:.1f}s")

    print("Running UVLM simulation...")
    t0 = time.time()
    problem = ps.problems.UnsteadyProblem(movement=movement)
    solver = (
        ps.unsteady_ring_vortex_lattice_method.UnsteadyRingVortexLatticeMethodSolver(
            unsteady_problem=problem,
        )
    )
    solver.run(prescribed_wake=True, logging_level="Warning")
    print(f"  Completed in {time.time() - t0:.1f}s")

    results = extract_results(solver)
    return solver, results


def _get_panel_mesh(airplanes):
    """Build a PyVista mesh from airplane panels.

    Uses PteraSoftware's panel vertex attributes:
    Flpp (front-left), Frpp (front-right), Brpp (back-right), Blpp (back-left).
    """
    panel_vertices = np.empty((0, 3), dtype=float)
    panel_faces = np.empty(0, dtype=int)
    panel_num = 0

    for airplane in airplanes:
        for wing in airplane.wings:
            for panel in np.ravel(wing.panels):
                verts = np.vstack((
                    panel.Flpp_GP1_CgP1,
                    panel.Frpp_GP1_CgP1,
                    panel.Brpp_GP1_CgP1,
                    panel.Blpp_GP1_CgP1,
                ))
                face = np.array([4, panel_num * 4, panel_num * 4 + 1,
                                 panel_num * 4 + 2, panel_num * 4 + 3], dtype=int)
                panel_vertices = np.vstack((panel_vertices, verts))
                panel_faces = np.hstack((panel_faces, face))
                panel_num += 1

    return pv.PolyData(panel_vertices, panel_faces)


def _get_panel_scalars(airplanes, scalar_type, q_inf):
    """Get per-panel scalar values for coloring (matches PteraSoftware's convention)."""
    scalars = []
    for airplane in airplanes:
        for wing in airplane.wings:
            for panel in np.ravel(wing.panels):
                if scalar_type == "lift":
                    scalars.append(-panel.forces_W[2] / q_inf / panel.area)
                elif scalar_type == "induced drag":
                    scalars.append(-panel.forces_W[0] / q_inf / panel.area)
                elif scalar_type == "side force":
                    scalars.append(panel.forces_W[1] / q_inf / panel.area)
    return np.array(scalars)


def _get_wake_mesh(solver, step):
    """Build a PyVista mesh from wake ring vortices at a given step.

    Uses PteraSoftware's stacked vertex arrays for efficiency.
    """
    num_wake = solver.list_num_wake_vortices[step]
    if num_wake == 0:
        return None

    fr = solver.listStackFrwrvp_GP1_CgP1[step]
    fl = solver.listStackFlwrvp_GP1_CgP1[step]
    bl = solver.listStackBlwrvp_GP1_CgP1[step]
    br = solver.listStackBrwrvp_GP1_CgP1[step]

    vertices = np.empty((0, 3), dtype=float)
    faces = np.empty(0, dtype=int)

    for i in range(num_wake):
        verts = np.vstack((fl[i], fr[i], br[i], bl[i]))
        face = np.array([4, i * 4, i * 4 + 1, i * 4 + 2, i * 4 + 3], dtype=int)
        vertices = np.vstack((vertices, verts))
        faces = np.hstack((faces, face))

    return pv.PolyData(vertices, faces)


def cmd_animate(args):
    """Run simulation and show interactive 3D animation."""
    solver, _ = run_simulation()

    scalar_type = None
    if args.lift:
        scalar_type = "lift"
    elif args.drag:
        scalar_type = "induced drag"
    elif args.side:
        scalar_type = "side force"

    label = scalar_type or "uniform"
    print(f"\nLaunching 3D animation (color={label}, wake={args.wake})...")
    print("  1. Orient the view in the window (rotate/zoom)")
    print('  2. Press "Q" to close and start the animation')
    print("  3. The animation will render (window may freeze briefly)")
    print("  4. Window closes automatically when done")
    if args.save:
        print("  -> Will save to Animate.webp when finished")
    print()

    ps.output.animate(
        unsteady_solver=solver,
        scalar_type=scalar_type,
        show_wake_vortices=args.wake,
        save=args.save,
    )

    if args.save and os.path.exists("Animate.webp"):
        print(f"Saved animation to Animate.webp")


def cmd_record(args):
    """Run simulation and record animation to GIF — no interaction needed."""
    solver, _ = run_simulation()
    up = solver.unsteady_problem

    scalar_type = None
    if args.lift:
        scalar_type = "lift"
    elif args.drag:
        scalar_type = "induced drag"
    elif args.side:
        scalar_type = "side force"

    output_file = args.output
    num_steps = up.num_steps
    first_step = up.first_results_step

    # Compute FPS: real-time would be 1/delta_time, cap at 30
    real_fps = 1.0 / up.delta_time
    speed = min(1.0, 30.0 / real_fps)
    fps = max(5, int(real_fps * speed))

    label = scalar_type or "uniform"
    print(f"\nRecording animation to {output_file}")
    print(f"  {num_steps} frames, {fps} fps, color={label}, wake={args.wake}")

    # Compute global scalar range for consistent coloring
    c_min, c_max = 0.0, 0.0
    if scalar_type is not None:
        all_scalars = []
        for step in range(num_steps):
            airplanes = up.steady_problems[step].airplanes
            q_inf = up.steady_problems[step].operating_point.qInf__E
            if step >= first_step:
                s = _get_panel_scalars(airplanes, scalar_type, q_inf)
                all_scalars.append(s)
        if all_scalars:
            combined = np.concatenate(all_scalars)
            mean_s, std_s = np.mean(combined), np.std(combined)
            if np.sign(np.min(combined)) == np.sign(np.max(combined)):
                c_min = max(mean_s - 3 * std_s, np.min(combined))
                c_max = min(mean_s + 3 * std_s, np.max(combined))
            else:
                c_min = -3 * std_s
                c_max = 3 * std_s

    # Set up offscreen plotter
    bg_color = "black" if args.dark else "white"
    text_color = "white" if args.dark else "black"
    panel_color = "cyan" if args.dark else "lightblue"
    wake_color = "gray" if args.dark else "lightgray"

    pv.OFF_SCREEN = True
    plotter = pv.Plotter(window_size=[1280, 720], off_screen=True)
    plotter.set_background(bg_color)
    plotter.enable_parallel_projection()

    # Set camera to isometric view looking at the wing
    plotter.camera_position = [(-0.8, -0.8, 0.5), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)]

    # Open writer based on file extension
    ext = os.path.splitext(output_file)[1].lower()
    if ext == ".gif":
        plotter.open_gif(output_file, fps=fps)
    elif ext in (".mp4", ".avi", ".mov", ".mkv"):
        plotter.open_movie(output_file, framerate=fps, quality=7)
    else:
        print(f"Unsupported format '{ext}'. Use .gif, .mp4, .avi, .mov, or .mkv")
        sys.exit(1)

    for step in range(num_steps):
        plotter.clear()
        plotter.set_background(bg_color)

        airplanes = up.steady_problems[step].airplanes
        mesh = _get_panel_mesh(airplanes)

        if scalar_type is not None and step >= first_step:
            q_inf = up.steady_problems[step].operating_point.qInf__E
            scalars = _get_panel_scalars(airplanes, scalar_type, q_inf)
            # Repeat each scalar 4x (one per vertex in quad)
            vertex_scalars = np.repeat(scalars, 4)
            mesh.point_data["scalars"] = vertex_scalars
            plotter.add_mesh(
                mesh, scalars="scalars", show_edges=True,
                clim=[c_min, c_max], cmap="coolwarm",
                scalar_bar_args={"title": scalar_type.title()},
            )
        else:
            plotter.add_mesh(mesh, show_edges=True, color=panel_color)

        if args.wake and step >= first_step:
            wake_mesh = _get_wake_mesh(solver, step)
            if wake_mesh is not None and wake_mesh.n_points > 0:
                plotter.add_mesh(wake_mesh, show_edges=True,
                                 color=wake_color, opacity=0.3)

        # Add timestep label
        t = step * up.delta_time
        plotter.add_text(
            f"t = {t:.3f}s  (step {step}/{num_steps})",
            position="upper_left", font_size=10, color=text_color,
        )

        plotter.write_frame()

        if (step + 1) % 50 == 0 or step == num_steps - 1:
            print(f"  Frame {step + 1}/{num_steps}")

    plotter.close()
    pv.OFF_SCREEN = False

    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"\nSaved {output_file} ({size_mb:.1f} MB, {num_steps} frames at {fps} fps)")


def cmd_plot(args):
    """Plot force/moment time series with matplotlib."""
    if args.from_json:
        if not os.path.exists("sim_output.json"):
            print("ERROR: sim_output.json not found. Run simulate.py first.")
            sys.exit(1)
        print("Loading results from sim_output.json...")
        with open("sim_output.json") as f:
            results = json.load(f)
        solver = None
    else:
        solver, results = run_simulation()

    ts = results["time_series"]
    ca = results["cycle_averaged"]
    di = results["design_info"]

    times = ts["times"]

    title_suffix = (
        f"  |  span={2*di['semi_span']:.2f}m  AR={di['aspect_ratio']:.1f}"
        f"  f={di['flap_frequency']:.0f}Hz  V={di['flight_speed']:.0f}m/s"
        f"  St={di['strouhal_number']:.2f}"
    )

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("Ornithopter Simulation Results" + title_suffix, fontsize=11)

    # Thrust vs time
    ax = axes[0, 0]
    ax.plot(times, ts["thrusts"], "b-", linewidth=0.8)
    ax.axhline(ca["mean_thrust"], color="b", linestyle="--", alpha=0.5,
               label=f"mean = {ca['mean_thrust']:.4f} N")
    ax.axhline(0, color="k", linewidth=0.3)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Thrust (N)")
    ax.set_title("Thrust vs Time")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Lift vs time
    ax = axes[0, 1]
    ax.plot(times, ts["lifts"], "r-", linewidth=0.8)
    ax.axhline(ca["mean_lift"], color="r", linestyle="--", alpha=0.5,
               label=f"mean = {ca['mean_lift']:.4f} N")
    ax.axhline(0, color="k", linewidth=0.3)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Lift (N)")
    ax.set_title("Lift vs Time")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # CL vs time
    ax = axes[1, 0]
    ax.plot(times, ts["CLs"], "g-", linewidth=0.8)
    ax.axhline(ca["mean_CL"], color="g", linestyle="--", alpha=0.5,
               label=f"mean CL = {ca['mean_CL']:.4f}")
    ax.axhline(0, color="k", linewidth=0.3)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("CL")
    ax.set_title("Lift Coefficient vs Time")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # CT vs time (thrust coefficient)
    ax = axes[1, 1]
    CTs = [-cd for cd in ts["CDs"]]
    ax.plot(times, CTs, "m-", linewidth=0.8)
    ax.axhline(ca["mean_CT"], color="m", linestyle="--", alpha=0.5,
               label=f"mean CT = {ca['mean_CT']:.4f}")
    ax.axhline(0, color="k", linewidth=0.3)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("CT")
    ax.set_title("Thrust Coefficient vs Time")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if args.save:
        filename = "ornithopter_plots.png"
        fig.savefig(filename, dpi=150)
        print(f"Saved plots to {filename}")

    # Also try PteraSoftware's built-in plots if we have the solver
    if solver is not None and not args.from_json:
        try:
            ps.output.plot_results_versus_time(
                unsteady_solver=solver, show=not args.save, save=args.save
            )
        except Exception:
            pass  # built-in plots are a bonus, not critical

    if not args.save:
        plt.show()
    else:
        print("Plots saved. Use --no-save or omit --save to show interactively.")


def cmd_print(args):
    """Print detailed force/moment results."""
    solver, _ = run_simulation()
    ps.output.print_results(solver=solver)


def main():
    parser = argparse.ArgumentParser(
        description="Visualize ornithopter simulation results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run visualize.py                         3D animation (default)
  uv run visualize.py animate --lift           3D with lift coloring
  uv run visualize.py animate --lift --save    3D + save as Animate.webp
  uv run visualize.py record                   Record to GIF (no interaction)
  uv run visualize.py record --lift --wake     Record with coloring + wake
  uv run visualize.py record -o my_wing.gif    Custom output filename
  uv run visualize.py plot                     Force time-series plots
  uv run visualize.py plot --save              Save plots as PNG
  uv run visualize.py plot --from-json         Plot from saved results (no re-run)
  uv run visualize.py print                    Print detailed force tables
""",
    )

    subparsers = parser.add_subparsers(dest="command")

    # animate (interactive)
    p_anim = subparsers.add_parser("animate",
        help="Interactive 3D animation (orient view, press Q to play)")
    p_anim.add_argument("--lift", action="store_true", help="Color panels by lift")
    p_anim.add_argument("--drag", action="store_true", help="Color panels by induced drag")
    p_anim.add_argument("--side", action="store_true", help="Color panels by side force")
    p_anim.add_argument("--wake", action="store_true", help="Show wake vortices")
    p_anim.add_argument("--save", action="store_true", help="Also save as Animate.webp")

    # record (non-interactive, saves GIF)
    p_rec = subparsers.add_parser("record",
        help="Record animation to GIF file (non-interactive)")
    p_rec.add_argument("--lift", action="store_true", help="Color panels by lift")
    p_rec.add_argument("--drag", action="store_true", help="Color panels by induced drag")
    p_rec.add_argument("--side", action="store_true", help="Color panels by side force")
    p_rec.add_argument("--wake", action="store_true", help="Show wake vortices")
    p_rec.add_argument("--dark", action="store_true", help="Black background")
    p_rec.add_argument("-o", "--output", default="ornithopter.gif",
                        help="Output filename (default: ornithopter.gif)")

    # plot
    p_plot = subparsers.add_parser("plot", help="Force/moment time-series plots")
    p_plot.add_argument("--save", action="store_true", help="Save plots as PNG")
    p_plot.add_argument("--from-json", action="store_true",
                        help="Plot from sim_output.json without re-running simulation")

    # print
    subparsers.add_parser("print", help="Print detailed force/moment tables")

    args = parser.parse_args()

    if args.command is None:
        # Default: animate with lift coloring
        args.command = "animate"
        args.lift = True
        args.drag = False
        args.side = False
        args.wake = False
        args.save = False

    if args.command == "animate":
        cmd_animate(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "plot":
        cmd_plot(args)
    elif args.command == "print":
        cmd_print(args)


if __name__ == "__main__":
    main()
