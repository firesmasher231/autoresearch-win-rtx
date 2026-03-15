# AutoOrnithopter

> **Note**: This is a modified fork of [jsegov/autoresearch-win-rtx](https://github.com/jsegov/autoresearch-win-rtx) (itself a Windows fork of [Karpathy's autoresearch](https://github.com/karpathy/autoresearch)). The `ornithopter/` subdirectory contains an autonomous ornithopter design research framework I'm building — applying the same agent-driven experiment loop to flapping-wing aerodynamic design instead of ML architecture search.

Autonomous ornithopter (flapping-wing) design optimization, inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch). An LLM agent edits wing design parameters, runs an aerodynamic simulation, evaluates the result, keeps improvements, and repeats — potentially running thousands of experiments overnight on a consumer PC.

The aerodynamic solver is [PteraSoftware](https://github.com/camUrban/PteraSoftware), which implements an Unsteady Ring Vortex Lattice Method (UVLM) specifically built for flapping-wing analysis.

## Prerequisites

- Python 3.11+ (PteraSoftware requires 3.11, 3.12, or 3.13)
- [uv](https://docs.astral.sh/uv/) package manager
- No GPU required — PteraSoftware is CPU-bound (uses Numba JIT)

## Quick start

```bash
cd ornithopter

# Install dependencies (pterasoftware + all its deps)
uv sync

# Run the baseline simulation (~60 seconds)
uv run simulate.py

# Visualize the results
uv run visualize.py                    # 3D animation (default)
uv run visualize.py plot               # force time-series plots
uv run visualize.py plot --from-json   # quick plot from saved results
```

## Project structure

| File | Role | Editable? |
|------|------|-----------|
| `design.py` | Wing geometry, flapping kinematics, flight conditions | **Yes** — the agent edits this |
| `simulate.py` | PteraSoftware UVLM wrapper, runs simulation | No |
| `evaluate.py` | Computes fitness metric from simulation results | No |
| `visualize.py` | 3D animation and time-series plotting | No |
| `program.md` | Agent instructions for the autonomous loop | Human edits |
| `results.tsv` | Experiment log (tab-separated) | Agent appends |
| `sim_output.json` | Detailed results from last simulation | Auto-generated |

The pattern mirrors autoresearch exactly:

| Autoresearch (ML) | AutoOrnithopter | Role |
|---|---|---|
| `train.py` | `design.py` | Agent edits this file |
| `prepare.py` | `simulate.py` + `evaluate.py` | Fixed evaluation pipeline |
| `program.md` | `program.md` | Agent instructions |
| `results.tsv` | `results.tsv` | Experiment log |

## How it works

1. The agent edits parameters in `design.py` (wing shape, flapping kinematics, flight speed, etc.)
2. Runs `uv run simulate.py` — builds wing geometry, runs UVLM solver, computes fitness
3. If fitness improved (higher), keep the change. If not, revert.
4. Log every experiment to `results.tsv`.
5. Repeat forever.

**Simulation time**: ~30-90 seconds per run depending on panel count and cycles. This means **40-120 experiments per hour**, or **~500-1000 overnight**.

## Design parameters

All tunable parameters live in `design.py`. The agent can modify any of them:

### Wing geometry

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `SEMI_SPAN` | 0.30 m | 0.10 - 0.60 | Half-wingspan |
| `ROOT_CHORD` | 0.08 m | 0.03 - 0.12 | Chord length at wing root |
| `TAPER_RATIO` | 0.50 | 0.25 - 1.00 | Tip chord / root chord |
| `SWEEP_ANGLE` | 5.0 deg | 0 - 25 | Quarter-chord sweep |
| `DIHEDRAL_ANGLE` | 0.0 deg | -5 - 12 | Upward angle from root |
| `ROOT_AIRFOIL` | "naca2412" | any NACA 4-series | Root airfoil profile |
| `TIP_AIRFOIL` | "naca2412" | any NACA 4-series | Tip airfoil profile |

### Flapping kinematics

Currently uses sinusoidal flap + sinusoidal pitch. See [Future work: advanced flapping kinematics](#future-work-advanced-flapping-kinematics) for plans to support asymmetric strokes, non-sinusoidal waveforms, and figure-8 patterns.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `FLAP_FREQUENCY` | 5.0 Hz | 2 - 20 | Flapping frequency |
| `FLAP_AMPLITUDE` | 30.0 deg | 15 - 70 | Half-stroke amplitude |
| `PITCH_AMPLITUDE` | 15.0 deg | 10 - 40 | Maximum pitch/twist angle |
| `PHASE_OFFSET` | 90.0 deg | 70 - 110 | Phase lag between pitch and flap |
| `MEAN_AOA` | 5.0 deg | 0 - 12 | Mean angle of attack |

### Flight conditions

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `FLIGHT_SPEED` | 5.0 m/s | 1 - 15 | Freestream velocity |
| `AIR_DENSITY` | 1.225 kg/m^3 | — | Sea-level standard |
| `KINEMATIC_VISCOSITY` | 15.06e-6 m^2/s | — | Standard conditions |

### Simulation resolution

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `NUM_SPANWISE_PANELS` | 8 | 4 - 16 | Panels along span (accuracy vs speed) |
| `NUM_CHORDWISE_PANELS` | 6 | 4 - 12 | Panels along chord (accuracy vs speed) |
| `NUM_CYCLES` | 3 | 2 - 5 | Flapping cycles to simulate |

### Derived quantities (auto-computed)

These are calculated from the parameters above and displayed in the output:

- **Aspect ratio** = (2 * SEMI_SPAN)^2 / WING_AREA
- **Reynolds number** = FLIGHT_SPEED * MEAN_CHORD / KINEMATIC_VISCOSITY
- **Strouhal number** = FLAP_FREQUENCY * TIP_EXCURSION / FLIGHT_SPEED (biological optimum: 0.2-0.4)
- **Reduced frequency** = pi * FLAP_FREQUENCY * MEAN_CHORD / FLIGHT_SPEED

## Fitness metric

The primary fitness metric is the **cycle-averaged thrust coefficient (mean_CT)**. Higher is better.

- Positive mean_CT = the flapping wing produces net forward thrust
- Negative mean_CT = the flapping wing produces net drag (bad)
- A **-1.0 penalty** is applied if mean_CL < 0 (design can't produce lift)

The fitness computation is in `evaluate.py` and cannot be modified.

## Output format

After each simulation, `simulate.py` prints a grep-able summary:

```
---
fitness:          0.328560
mean_CT:          0.328560
mean_CL:          1.042215
mean_CD:          -0.328560
L_over_D:         3.172074  (net thrust)
mean_thrust_N:    0.090559
mean_lift_N:      0.287261
mean_drag_N:      -0.090559
sim_seconds:      55.5
num_steps:        290
reynolds:         19920
strouhal:         0.300
reduced_freq:     0.188
```

Detailed per-timestep results are saved to `sim_output.json`.

## Visualization

`visualize.py` provides three visualization modes. Each one runs the simulation first (except `--from-json`).

### 3D animation (interactive)

```bash
uv run visualize.py                          # default: lift-colored panels
uv run visualize.py animate                  # uniform color
uv run visualize.py animate --lift           # color by lift distribution
uv run visualize.py animate --drag           # color by induced drag
uv run visualize.py animate --wake           # show trailing wake vortices
uv run visualize.py animate --lift --wake    # both
uv run visualize.py animate --save           # also save as Animate.webp
```

How the interactive animation works:
1. A static window opens — **orient the view** (rotate/zoom with mouse)
2. Press **Q** to close that window and start the animation rendering
3. Frames render offscreen (window may say "not responding" — this is normal)
4. Window closes automatically when done

### Record to GIF (non-interactive)

```bash
uv run visualize.py record                          # save to ornithopter.gif
uv run visualize.py record --lift                    # with lift coloring
uv run visualize.py record --lift --wake             # with lift + wake trails
uv run visualize.py record -o my_design.gif          # custom output filename
```

This renders all frames offscreen with a fixed camera angle and writes directly to a GIF file — no window interaction needed. Useful for comparing designs or sharing results.

### Time-series plots

```bash
uv run visualize.py plot                     # show interactive matplotlib plots
uv run visualize.py plot --save              # save as ornithopter_plots.png
uv run visualize.py plot --from-json         # plot from sim_output.json (no re-run)
uv run visualize.py plot --from-json --save  # save from existing results
```

Produces four subplots: thrust vs time, lift vs time, CL vs time, CT vs time, with cycle-averaged means shown as dashed lines.

### Force tables

```bash
uv run visualize.py print                    # PteraSoftware's built-in force table
```

## Running the autonomous loop

To run the agent-driven optimization:

1. Initialize git if not already done:
   ```bash
   cd ornithopter
   git init
   git add design.py simulate.py evaluate.py visualize.py program.md results.tsv pyproject.toml README.md
   git commit -m "initial ornithopter framework"
   ```

2. Create an experiment branch:
   ```bash
   git checkout -b ornithopter/mar14
   ```

3. Point your LLM coding agent at the project:
   ```
   Read program.md first, then start the autonomous research loop.
   ```

4. The agent will:
   - Edit `design.py` with a new design idea
   - Commit the change
   - Run `uv run simulate.py > run.log 2>&1`
   - Check fitness via `grep "^fitness:" run.log`
   - Keep if improved, revert if not
   - Log to `results.tsv`
   - Repeat indefinitely

Each experiment takes ~60 seconds, so expect **~60 experiments/hour** or **~500 overnight**.

## Technical notes

### PteraSoftware symmetry workaround

PteraSoftware's `symmetric=True` wing feature creates a reflected wing automatically, but it enforces that the wing's "symmetry type" stays constant across all timesteps. Flapping motion (rotation about the x-axis) changes the wing's local coordinate axes, which can break the symmetry type constraint.

The solution used here is to offset the wing root by 0.001m from the symmetry plane (`Ler_Gs_Cgs=(0.0, 0.001, 0.0)`). This creates "type 5" symmetry (non-coincident), which:
- Auto-generates a reflected wing (so you get both left and right)
- Stays at type 5 throughout flapping (because the root is never exactly on the plane)
- Produces correct symmetric flapping motion

The 0.001m offset is negligible compared to the wing dimensions and has no measurable effect on results.

### Wing-level vs cross-section-level pitch

PteraSoftware requires the root cross-section to always have zero rotation angles. This means pitch oscillation cannot be applied at the cross-section level (it would modify the root's angles). Instead, pitch is applied at the wing level alongside flapping:

```python
ampAngles_Gs_to_Wn_ixyz = (FLAP_AMPLITUDE, PITCH_AMPLITUDE, 0.0)
```

This produces rigid-body pitch (the entire wing twists uniformly). For differential twist along the span, one would need to apply pitch only to non-root cross-sections — a possible future enhancement.

### Force conventions

PteraSoftware uses wind-axis forces where:
- `forces_W[0]` = force in freestream direction (positive = thrust, negative = drag)
- `forces_W[2]` = force perpendicular to freestream (negative = lift in conventional sense)

So: `thrust = forces_W[0]`, `lift = -forces_W[2]`, `drag = -forces_W[0]`.

For a flapping wing producing net thrust, `mean_drag` will be **negative** (there's thrust, not drag). The L/D ratio in this case shows lift per unit thrust.

### UVLM limitations

The Unsteady Vortex Lattice Method is an inviscid, potential flow method. It captures:
- Unsteady aerodynamic forces from flapping motion
- Wake effects and induced drag
- Lift distribution and thrust generation

It does **not** capture:
- Viscous drag (skin friction, pressure drag from separation)
- Leading-edge vortex effects (important at low Re and high AoA)
- Aeroelastic deformation (wings are rigid)
- Clap-and-fling mechanisms (used by insects)

For designs that perform well in UVLM, validate with higher-fidelity CFD (OpenFOAM, SU2) before building hardware.

## Baseline results

The default design in `design.py` produces:

| Metric | Value |
|--------|-------|
| fitness (mean_CT) | 0.329 |
| mean_CL | 1.042 |
| mean_thrust | 0.091 N |
| mean_lift | 0.287 N |
| Strouhal number | 0.300 |
| Reynolds number | 19,920 |
| Simulation time | ~55 s |

## Future work: advanced flapping kinematics

The current simulation uses **sinusoidal flapping and pitching** defined by 5 parameters (frequency, flap amplitude, pitch amplitude, phase offset, mean AoA). This covers a wide design space but constrains the wing to simple harmonic motion:

```
flap(t)  = FLAP_AMPLITUDE * sin(2π * f * t)
pitch(t) = PITCH_AMPLITUDE * sin(2π * f * t + PHASE_OFFSET)
```

PteraSoftware supports more complex motions via custom spacing functions — these would require changes to `simulate.py` to expose as parameters in `design.py`. Potential extensions:

- **Asymmetric upstroke/downstroke**: Faster downstroke (power stroke) with slower upstroke (recovery). Birds and insects use this extensively. PteraSoftware supports this via custom `spacing` callables that are non-symmetric over the period.
- **Non-sinusoidal waveforms**: Trapezoidal, triangular, or clipped-sine profiles that hold the wing at peak angle longer. Could improve thrust by spending more time at effective angles.
- **Variable pitch through the stroke**: Instead of uniform sinusoidal pitch, the pitch angle could follow a more complex profile — e.g., rapid pitch reversal at stroke ends (like insect wings).
- **Figure-8 stroke patterns**: Some hovering insects trace a figure-8 with their wingtips. This can be approximated by adding a harmonic to the vertical heave component (`ampLer_Gs_Cgs` on the WingMovement).
- **Differential spanwise twist**: Apply pitch oscillation only to the tip cross-section (non-root WCS), creating washout that varies through the stroke — more like a real flexible wing.
- **Stroke plane inclination**: Currently the stroke plane is fixed. Adding an oscillation to the wing's z-angle could tilt the stroke plane dynamically.
- **Multi-frequency components**: Add 2nd or 3rd harmonics to the flap/pitch waveforms for finer control of the force profile through each cycle.

These would significantly expand the design space the agent can explore. The trade-off is more parameters = slower convergence, so it's best to first optimize the simple sinusoidal case and then add complexity.

## Key resources

- [PteraSoftware](https://github.com/camUrban/PteraSoftware) — the UVLM solver
- [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) — the ML experiment loop this project is modeled after
- [pymoo](https://pymoo.org/) — multi-objective optimization (potential Tier 2 addition)
- [AeroSandbox](https://github.com/peterdsharpe/AeroSandbox) — differentiable aerospace design optimization
