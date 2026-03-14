# AutoOrnithopter: Complete Research & Decision Log

This document captures all research, decisions, alternatives considered, and technical details from the development of the AutoOrnithopter framework — an autonomous ornithopter design optimization system inspired by Karpathy's autoresearch.

---

## 1. Project Genesis & Motivation

### The autoresearch concept

Karpathy's [autoresearch](https://github.com/karpathy/autoresearch) demonstrates that an LLM agent can autonomously iterate on ML model architectures overnight. The loop is simple:

1. Agent edits `train.py` (model architecture, hyperparameters)
2. Runs training (~5 minutes on GPU)
3. Evaluates val_bpb (bits per byte)
4. If better → keep. If worse → revert.
5. Repeat indefinitely.

The key insight: **if the evaluation is fast enough, an agent can explore hundreds of designs overnight.**

### Mapping to ornithopter design

The same pattern applies to aerodynamic design if we have a fast-enough simulator:

| Aspect | Autoresearch (ML) | AutoOrnithopter |
|--------|-------------------|-----------------|
| Agent edits | `train.py` | `design.py` |
| Evaluation | 5 min GPU training | 10-60 sec CPU simulation |
| Metric | val_bpb (lower = better) | mean_CT (higher = better) |
| Experiments/night | ~100 | ~500-3000 |
| Hardware | GPU required | CPU only |
| Setup complexity | Low | Medium |

**The ornithopter case is actually faster per iteration** than the ML case, enabling more exploration.

### Feasibility assessment

The main question was: is there a simulator fast enough for an agent loop? The answer is yes — PteraSoftware's UVLM solver runs in under 60 seconds on a consumer laptop, compared to 5 minutes for autoresearch's ML training. This means **60+ experiments per hour** or potentially **1000+ overnight**.

---

## 2. Technology Stack Research

### Tier 1: Fast Evaluation Loop (the core simulator)

#### PteraSoftware (CHOSEN)

- **What**: Python library implementing Unsteady Ring Vortex Lattice Method (UVLM) specifically for flapping-wing analysis
- **Install**: `pip install pterasoftware` (PyPI, v4.0.1 as of late 2025)
- **Speed**: Under 60 seconds per simulation on consumer PC
- **Method**: Unsteady Vortex Lattice Method — an inviscid potential flow method that models the wing as a lattice of vortex rings and tracks the time-evolving wake
- **Requirements**: Python 3.11-3.13, CPU-bound (uses Numba JIT compilation)
- **GitHub**: https://github.com/camUrban/PteraSoftware
- **Why chosen**: Only Python UVLM solver specifically designed for flapping wings. Fast enough for an agent loop. Pure Python + Numba means no compilation hassles on Windows.

#### Alternatives evaluated

| Tool | Type | Speed | Why not primary |
|------|------|-------|-----------------|
| **AeroSandbox** | Differentiable aerospace design | Very fast | General purpose, not specialized for flapping; better for fixed-wing optimization |
| **PANKH** | Fast hovering airfoil analysis | Fast | Focused on hovering only, less general |
| **NeuralFoil** | Neural network airfoil evaluator | ~5ms | 2D only (airfoil sections), not 3D flapping wings; could be used as a sub-component |
| **OpenFOAM** | Full CFD (Navier-Stokes) | Minutes-hours | Too slow for agent loop; use for validation of best designs |
| **SU2** | Full CFD with optimization | Minutes-hours | Same; has unsteady optimization support but too slow per iteration |

#### CPU vs GPU trade-off

PteraSoftware is **CPU-bound** (Numba JIT on CPU). This is actually an advantage for this use case:
- No GPU required — can run on any laptop
- The GPU is free for other work (or for running the LLM agent itself)
- Numba JIT compiles the inner loops to fast machine code on first run
- Parallelism comes from Numba's automatic vectorization, not GPU kernels
- Typical simulation: 290 timesteps, 48 panels per wing, ~55 seconds on an i7 laptop

If GPU acceleration were needed (e.g., for much larger panel counts), one would need to rewrite the core solver in CUDA — not practical. Instead, the surrogate model approach (Tier 2) is the right path to faster iteration.

### Tier 2: Optimization Framework

#### The LLM agent IS the optimizer (current approach)

For the initial implementation, the LLM agent serves as the optimization framework — just like in autoresearch. The agent:
- Reads past results from `results.tsv`
- Proposes new design modifications based on physical intuition
- Evaluates and keeps/discards based on fitness

This is effective because:
- LLMs have broad knowledge of aerodynamics and can make physically informed proposals
- The "propose → evaluate → keep/discard" loop is simple and robust
- No hyperparameter tuning of the optimizer itself is needed

#### When to switch to formal optimization

| Tool | Best for | Install |
|------|----------|---------|
| **pymoo** | Multi-objective optimization (e.g., maximize thrust AND minimize power simultaneously). Supports NSGA-II, NSGA-III, and other evolutionary algorithms. | `pip install pymoo` |
| **Optuna** | Bayesian optimization with pruning. Smart exploration of design space with automatic early stopping of bad trials. | `pip install optuna` |
| **OpenMDAO** | NASA-grade multidisciplinary optimization. Connects aerodynamics + structures + kinematics in a single optimization problem with analytic derivatives. | `pip install openmdao` |

Switch to formal optimization when:
- The agent's ad-hoc exploration plateaus
- You want systematic Pareto front exploration (pymoo)
- You want to couple aerodynamics with structural analysis (OpenMDAO)
- You want to build a surrogate model from agent-generated data (Optuna)

#### Surrogate model approach (future)

1. Run ~500 PteraSoftware simulations with diverse random parameters → build training dataset
2. Train a neural network surrogate (predict forces from parameters in ~5ms)
3. Use pymoo evolutionary optimization on the surrogate → find optimal design in seconds
4. Validate top candidates with PteraSoftware / CFD

This approach has achieved 40%+ efficiency improvements in recent flapping-wing research papers.

### Tier 3: High-Fidelity Validation

For designs that perform well in UVLM, validate with higher-fidelity CFD before building hardware.

| Tool | Method | Use case |
|------|--------|----------|
| **OpenFOAM** | Full Navier-Stokes CFD | Has a 2D flapping wing tutorial. Open source. Captures viscous effects, separation, LEV. |
| **SU2** | Full CFD with adjoint optimization | Has unsteady optimization support built in. Can do shape optimization with analytic gradients. |

**UVLM limitations** that high-fidelity CFD addresses:
- **Viscous drag**: UVLM is inviscid — no skin friction or pressure drag from separation
- **Leading-edge vortices (LEV)**: Critical at low Re and high AoA, not captured by UVLM
- **Aeroelastic deformation**: UVLM treats wings as rigid
- **Clap-and-fling**: Insect flight mechanism, not modeled
- **Flow separation**: UVLM assumes attached flow everywhere

### Tier 4: LLM Agent Integration

Several projects demonstrate LLM-driven simulation loops:

| Project | What it does | Performance |
|---------|-------------|-------------|
| **ChatCFD** | LLM automates OpenFOAM simulations end-to-end | 82% success rate |
| **MetaOpenFOAM** | Multi-agent CFD automation with specialized sub-agents | $0.22 per case |
| **Autonomous Engineering Design** (arXiv:2511.03179) | NACA airfoil optimization with LLM agents | Competitive with gradient-based methods |

These demonstrate that the pattern works for aerodynamic design, not just ML.

---

## 3. Ornithopter Design Parameter Research

### Wing Geometry Parameters

| Parameter | Symbol | Units | Range | Notes |
|-----------|--------|-------|-------|-------|
| Semi-span | b/2 | m | 0.10 - 0.60 | Full span 0.20-1.20m. Insect-scale MAVs ~0.05-0.15m; bird-scale 0.20-0.75m |
| Root chord | c_root | m | 0.03 - 0.12 | Drives Reynolds number directly |
| Tip chord | c_tip | m | 0.005 - 0.10 | Must be <= c_root |
| Aspect ratio | AR | - | 3.0 - 15.0 | Hummingbird ~3-4.5; pigeon ~4-6; raptor ~6-8; albatross ~14-18 |
| Taper ratio | lambda | - | 0.2 - 1.0 | c_tip/c_root. Rectangular=1.0; moderate taper ~0.4-0.6; pointed ~0.2 |
| Sweep angle | Lambda | deg | -5 to 30 | Quarter-chord sweep. Most ornithopters use 0-15 deg |
| Dihedral angle | Gamma | deg | -5 to 15 | Positive = upward from root. 0-10 deg for roll stability |
| Wing area | S | m^2 | 0.005 - 0.50 | Derived from span and chord |
| Wing loading | W/S | N/m^2 | 5 - 80 | Insects ~1-10; sparrow ~20-30; pigeon ~40-50 |

### Flapping Kinematics Parameters

| Parameter | Symbol | Units | Range | Notes |
|-----------|--------|-------|-------|-------|
| Flapping frequency | f | Hz | 1.0 - 40.0 | Eagles ~1-3; pigeons ~5-10; hummingbirds ~20-50; insects 200+ |
| Flapping amplitude | phi_0 | deg | 15 - 80 | Half-stroke. Full stroke = 2x. Most bird-scale: 30-60 deg |
| Pitch amplitude | theta_0 | deg | 10 - 45 | Max wing twist. 15-30 deg typical for engineering designs |
| Pitch-flap phase offset | psi | deg | 60 - 120 | 90 deg is theoretical optimum. Range 75-105 covers most designs |
| Stroke plane angle | beta | deg | 0 - 75 | 0 = horizontal (hovering insects). 60-75 = near-vertical (birds in forward flight) |
| Mean angle of attack | alpha_mean | deg | 0 - 15 | 5-10 deg common for cruise |
| Flapping offset | phi_offset | deg | -10 to 10 | Upstroke vs downstroke asymmetry. 0 = symmetric |

### Dimensionless Parameters

| Parameter | Symbol | Definition | Range | Significance |
|-----------|--------|-----------|-------|-------------|
| Reynolds number | Re | U * c / nu | 10^2 - 10^5 | Insects: 10^2-10^4; MAVs: 10^4-5x10^4; bird-scale: 2x10^4-10^5 |
| Strouhal number | St | f * A / U | 0.1 - 0.5 | **Biological optimum: 0.2-0.4** for propulsive efficiency. A = peak-to-peak tip excursion |
| Reduced frequency | k | pi * f * c / U | 0.05 - 4.0 | Large birds: 0.05-0.3; small birds: 0.3-1.0; insects: 0.5-4.0 |
| Advance ratio | J | U / (2*f*phi_0*R) | 0.0 - 1.5 | 0 = hovering; 0.3-0.8 = forward flight; >1.0 = high-speed cruise |

### Fitness Metrics Considered

| Metric | Definition | Target | Status |
|--------|-----------|--------|--------|
| **Propulsive efficiency** | eta_p = T * U / P_input | Maximize (0.3-0.7) | **Not used** — requires input power, which UVLM doesn't directly compute |
| **Thrust coefficient (CT)** | C_T = T / (0.5 * rho * U^2 * S) | Maximize (> 0) | **CHOSEN as primary fitness** — simple, directly comparable |
| **Lift coefficient (CL)** | C_L = L / (0.5 * rho * U^2 * S) | Must be positive | Used as constraint (penalty if CL < 0) |
| **Lift-to-drag ratio** | L/D | Maximize (4-15) | Displayed as auxiliary metric |
| **Power loading** | T/P or W/P (N/W) | Maximize | Not available without power computation |
| **Compound: CT * L/D** | Thrust-weighted efficiency | Maximize | Considered but rejected for simplicity |
| **Flight quality index** | CT * (1 + CL) | Maximize | Considered but adds complexity |

**Decision**: `fitness = mean_CT` with a -1.0 penalty if mean_CL < 0. This is the simplest metric that rewards thrust production while ensuring the design can produce lift. The agent sees all other metrics in the output and can make informed decisions.

### Bio-Inspired Design Patterns

| Pattern | AR | Frequency | Amplitude | Speed | St |
|---------|-----|-----------|-----------|-------|----|
| Hummingbird | ~4 | ~15 Hz | ~50 deg | ~5 m/s | ~0.3 |
| Pigeon | ~6 | ~8 Hz | ~35 deg | ~10 m/s | ~0.25 |
| Albatross | ~12 | ~2 Hz | ~20 deg | ~15 m/s | ~0.15 |
| Dragonfly | ~8 | ~25 Hz | ~60 deg | ~3 m/s | ~0.35 |

### Physical Constraints for Valid Designs

1. **Geometric**: c_tip <= c_root (taper ratio <= 1.0)
2. **Reynolds check**: Re = U * c_mean / nu should be 10^3 - 10^5
3. **Strouhal check**: St should be 0.05 - 0.6 (designs outside this are biologically implausible)
4. **Structural**: AR > 12 with thin membrane is structurally challenging
5. **Frequency-mass scaling**: f decreases with increasing mass (a 1kg ornithopter at 30Hz is unrealistic)
6. **Wing loading**: W/S should be 5-80 N/m^2

---

## 4. PteraSoftware API Deep Dive

### Installation and import

```
pip install pterasoftware
```

Requires Python 3.11, 3.12, or 3.13. Pure Python + Numba JIT.

```python
import pterasoftware as ps
```

### Class hierarchy

```
ps.geometry.airplane.Airplane
  └── ps.geometry.wing.Wing
        └── ps.geometry.wing_cross_section.WingCrossSection
              └── ps.geometry.airfoil.Airfoil

ps.operating_point.OperatingPoint

ps.movements.movement.Movement
  ├── ps.movements.airplane_movement.AirplaneMovement
  │     └── ps.movements.wing_movement.WingMovement
  │           └── ps.movements.wing_cross_section_movement.WingCrossSectionMovement
  └── ps.movements.operating_point_movement.OperatingPointMovement

ps.problems.UnsteadyProblem
ps.unsteady_ring_vortex_lattice_method.UnsteadyRingVortexLatticeMethodSolver
ps.output  (animate, plot_results_versus_time, print_results)
```

### Key constructors

#### Airfoil
```python
ps.geometry.airfoil.Airfoil(
    name="naca2412",           # NACA 4-series or UIUC database name
    resample=True,
    n_points_per_side=400,
)
```

#### WingCrossSection
```python
ps.geometry.wing_cross_section.WingCrossSection(
    airfoil=...,                                        # Required
    num_spanwise_panels=8,                              # int for root/mid; None for tip
    chord=1.0,                                          # meters, > 0
    Lp_Wcsp_Lpp=(0.0, 0.0, 0.0),                      # (x,y,z) relative to parent LE
    angles_Wcsp_to_Wcs_ixyz=(0.0, 0.0, 0.0),          # twist/rotation, degrees [-90,90]
    control_surface_symmetry_type=None,                 # "symmetric", "asymmetric", or None
    control_surface_hinge_point=0.75,                   # chord fraction
    control_surface_deflection=0.0,                     # degrees
    spanwise_spacing="cosine",                          # "cosine" or "uniform"; None for tip
)
```

**Constraints:**
- Root WCS: `Lp_Wcsp_Lpp` must be `(0,0,0)`, `angles_Wcsp_to_Wcs_ixyz` must be `(0,0,0)`
- All WCS: `Lp_Wcsp_Lpp[1]` (y-component) must be >= 0
- Tip WCS: `num_spanwise_panels` must be None, `spanwise_spacing` must be None

#### Wing
```python
ps.geometry.wing.Wing(
    wing_cross_sections=[root_wcs, tip_wcs],    # >= 2 sections
    name="Main Wing",
    Ler_Gs_Cgs=(0.0, 0.0, 0.0),                # LE root position relative to CG
    angles_Gs_to_Wn_ixyz=(0.0, 0.0, 0.0),      # Wing orientation, degrees [-90,90]
    symmetric=True,                              # Auto-creates reflected wing
    mirror_only=False,
    symmetryNormal_G=(0.0, 1.0, 0.0),           # Required if symmetric or mirror_only
    symmetryPoint_G_Cg=(0.0, 0.0, 0.0),
    num_chordwise_panels=6,
    chordwise_spacing="uniform",                 # "uniform" for unsteady (not "cosine")
)
```

**Critical**: `angles_Gs_to_Wn_ixyz` elements are limited to [-90, 90] degrees.

#### Airplane
```python
ps.geometry.airplane.Airplane(
    wings=[main_wing],
    name="Ornithopter",
)
```

After construction with `symmetric=True`, `airplane.wings` may have MORE entries than passed (reflected wings are auto-created).

#### OperatingPoint
```python
ps.operating_point.OperatingPoint(
    rho=1.225,           # Air density kg/m^3
    vCg__E=10.0,         # Freestream velocity m/s
    alpha=1.0,           # Angle of attack degrees
    beta=0.0,            # Sideslip degrees
    nu=15.06e-6,         # Kinematic viscosity m^2/s
)
```

### Movement definition (flapping kinematics)

Flapping is defined via **oscillatory parameters**, NOT per-timestep geometry. PteraSoftware generates geometry at each timestep internally.

```
value(t) = base_value + amplitude * spacing_function(2*pi*t/period + phase)
```

Where `spacing_function` is `"sine"` (default), `"uniform"`, or a custom callable.

#### WingCrossSectionMovement
```python
ps.movements.wing_cross_section_movement.WingCrossSectionMovement(
    base_wing_cross_section=wcs,
    # Position oscillation:
    ampLp_Wcsp_Lpp=(0.0, 0.0, 0.0),
    periodLp_Wcsp_Lpp=(0.0, 0.0, 0.0),
    phaseLp_Wcsp_Lpp=(0.0, 0.0, 0.0),
    # Angle oscillation:
    ampAngles_Wcsp_to_Wcs_ixyz=(0.0, 0.0, 0.0),
    periodAngles_Wcsp_to_Wcs_ixyz=(0.0, 0.0, 0.0),
    phaseAngles_Wcsp_to_Wcs_ixyz=(0.0, 0.0, 0.0),
)
```

#### WingMovement
```python
ps.movements.wing_movement.WingMovement(
    base_wing=wing,
    wing_cross_section_movements=[root_wcsm, tip_wcsm],
    # Flapping + pitching at wing level:
    ampAngles_Gs_to_Wn_ixyz=(30.0, 15.0, 0.0),    # (flap, pitch, yaw) degrees
    periodAngles_Gs_to_Wn_ixyz=(0.2, 0.2, 0.0),    # seconds
    phaseAngles_Gs_to_Wn_ixyz=(0.0, 90.0, 0.0),    # degrees
)
```

#### Movement (top-level)
```python
ps.movements.movement.Movement(
    airplane_movements=[airplane_movement],
    operating_point_movement=op_movement,
    delta_time=None,    # None = auto-optimize timestep
    num_cycles=3,       # Number of flapping cycles
)
```

### Running the solver

```python
problem = ps.problems.UnsteadyProblem(movement=movement)
solver = ps.unsteady_ring_vortex_lattice_method.UnsteadyRingVortexLatticeMethodSolver(
    unsteady_problem=problem,
)
solver.run(
    prescribed_wake=True,        # True = faster/stable; False = free-wake (more accurate)
    logging_level="Warning",     # "Debug", "Info", "Warning", "Error", "Critical"
    calculate_streamlines=True,
)
```

Note: `show_progress` is NOT a valid parameter (despite some documentation suggesting it). The parameter is `logging_level`.

### Force conventions (CRITICAL)

PteraSoftware uses **wind-axis forces**:

```
forces_W[0] = FX_W = force in freestream direction
forces_W[1] = FY_W = side force
forces_W[2] = FZ_W = force perpendicular to freestream
```

Sign conventions:
- **Thrust** = `forces_W[0]` (positive = forward/thrust, negative = drag)
- **Lift** = `-forces_W[2]` (negated because FZ is negative for upward lift)
- **Drag** = `-forces_W[0]` (negated; positive drag when FX is negative)

For coefficients: same pattern with `forceCoefficients_W`.

**For a flapping wing producing net thrust:**
- `forces_W[0]` > 0 (positive = thrust)
- `mean_drag = -forces_W[0]` < 0 (negative = there's thrust, not drag)
- `mean_CD` < 0
- L/D ratio is misleading — report as lift/|thrust| instead

### Extracting cycle-averaged results

```python
up = solver.unsteady_problem
mean_forces = up.finalMeanForces_W[0]       # [airplane_index]
mean_coeffs = up.finalMeanForceCoefficients_W[0]
rms_forces = up.finalRmsForces_W[0]
```

Per-timestep:
```python
for step in range(up.first_results_step, up.num_steps):
    ap = up.steady_problems[step].airplanes[0]
    thrust = ap.forces_W[0]
    lift = -ap.forces_W[2]
    CL = -ap.forceCoefficients_W[2]
```

### Panel vertex attributes

Panel corners (for visualization):
```python
panel.Flpp_GP1_CgP1   # front-left
panel.Frpp_GP1_CgP1   # front-right
panel.Brpp_GP1_CgP1   # back-right
panel.Blpp_GP1_CgP1   # back-left
panel.area             # panel area (for computing coefficients)
panel.forces_W         # per-panel forces in wind axes
```

Wake ring vortex vertices (stored on the solver, not individual objects):
```python
solver.list_num_wake_vortices[step]
solver.listStackFrwrvp_GP1_CgP1[step]   # front-right vertices
solver.listStackFlwrvp_GP1_CgP1[step]   # front-left
solver.listStackBlwrvp_GP1_CgP1[step]   # back-left
solver.listStackBrwrvp_GP1_CgP1[step]   # back-right
```

### Typical panel counts

- `num_chordwise_panels`: 6 (moderate resolution)
- `num_spanwise_panels`: 8 (moderate resolution)
- Higher counts = more accurate but slower (scales roughly as N^2)

---

## 5. Technical Decisions & Workarounds

### The Symmetry Problem (most significant challenge)

PteraSoftware has 5 symmetry types for wings:

| Type | symmetric | mirror_only | coincident | Behavior |
|------|-----------|-------------|------------|----------|
| 1 | False | False | N/A | No symmetry — standalone wing |
| 2 | False | True | True | Mirror mesh, coincident with symmetry plane |
| 3 | False | True | False | Mirror mesh, NOT coincident |
| 4 | True | N/A | True | Single wing, mesh includes reflection |
| 5 | True | N/A | False | Creates two wings (original + reflected) |

**Coincident** means: (1) wing y-axis is parallel to symmetry normal, AND (2) wing root is on the symmetry plane.

#### Attempt 1: `symmetric=True` with root at origin (Type 4)

```python
Wing(symmetric=True, Ler_Gs_Cgs=(0.0, 0.0, 0.0),
     symmetryNormal_G=(0.0, 1.0, 0.0), symmetryPoint_G_Cg=(0.0, 0.0, 0.0))
```

**Failed**: Required `control_surface_symmetry_type` on all WCS (even without control surfaces). After fixing that, flapping motion rotated the wing's y-axis away from the symmetry normal, changing the symmetry type from 4 to 1 at the next timestep.

**Error**: `Wing 0 changed from type 4 symmetry at time step 0 to type 1 symmetry at time step 1`

#### Attempt 2: WCS-level pitch oscillation

Applied `ampAngles_Wcsp_to_Wcs_ixyz` on each WingCrossSectionMovement for pitch.

**Failed**: Root WCS must always have `angles_Wcsp_to_Wcs_ixyz = (0,0,0)`. PteraSoftware enforces this constraint because the root cross section defines the wing's reference frame.

**Error**: `The root WingCrossSection's angles_Wcsp_to_Wcs_ixyz must be np.array([0.0, 0.0, 0.0])`

#### Attempt 3: Two explicit wings with 180-degree rotation

Created left wing (extending +y) and right wing with `angles_Gs_to_Wn_ixyz=(180.0, 0.0, 0.0)` to flip it.

**Failed**: `angles_Gs_to_Wn_ixyz` elements are limited to [-90, 90] degrees.

**Error**: `All elements of angles_Gs_to_Wn_ixyz must lie in the range [-90, 90] degrees`

#### Attempt 4: Two explicit wings with negative y-offset

Used `Lp_Wcsp_Lpp=(sweep, -SEMI_SPAN, dihedral)` for the right wing tip.

**Would have failed**: `Lp_Wcsp_Lpp[1]` (y-component) must be >= 0 (enforced in constructor).

#### Solution: Type 5 symmetry with root offset (ADOPTED)

```python
Wing(
    symmetric=True,
    Ler_Gs_Cgs=(0.0, 0.001, 0.0),  # 1mm offset from symmetry plane
    symmetryNormal_G=(0.0, 1.0, 0.0),
    symmetryPoint_G_Cg=(0.0, 0.0, 0.0),
)
```

**Why this works:**
1. Root at y=0.001 is NOT on the symmetry plane (y=0) → type 5 (non-coincident)
2. Type 5 creates two wings: original (becomes type 1) + reflected (becomes type 3)
3. During flapping, wing y-axis rotates → no longer parallel to symmetry normal → still non-coincident → type stays the same
4. Original wing: type 1 → type 1 (always, no symmetry checks)
5. Reflected wing: type 3 → type 3 (non-coincident is preserved because root is always at y=0.001, never exactly on the plane)
6. The 0.001m offset is negligible compared to the 0.30m semi-span (~0.3%)

**PteraSoftware's type 5 processing:**
- Creates a reflected wing with `mirror_only=True`
- Resets original wing to `symmetric=False, mirror_only=False`
- Sets `control_surface_symmetry_type=None` on all WCS of both wings (compatible with types 1 and 3)
- The reflected wing's mesh is mirrored about the symmetry plane during `generate_mesh`

**Symmetric flapping:**
The same movement parameters applied to both wings produce correct symmetric flapping because the reflected wing's mesh is mirrored. When the original wing tip goes up (+z), the mirrored mesh tip also goes up (+z) because mirroring about the xz plane only negates y, not z.

### Wing-Level vs Cross-Section-Level Pitch

**Decision**: Apply pitch at the wing level, not the WCS level.

```python
ampAngles_Gs_to_Wn_ixyz=(FLAP_AMPLITUDE, PITCH_AMPLITUDE, 0.0)
```

**Trade-off:**
- Wing-level pitch: entire wing twists uniformly (rigid-body rotation). Simpler, compatible with root WCS constraint.
- WCS-level pitch: can apply differential twist along span (e.g., more twist at tip than root). More physical but cannot be applied to root WCS.

**Future enhancement**: Apply pitch only to non-root WCS (tip section) to get spanwise twist variation.

### Fitness Metric Selection

**Decision**: `fitness = mean_CT` with CL < 0 penalty.

**Alternatives considered:**
1. **Propulsive efficiency** (eta = T*V/P) — requires aerodynamic input power, which UVLM doesn't directly compute. Would need to integrate moment × angular velocity over a cycle.
2. **CT * L/D** — rewards both thrust and efficiency but is a compound metric harder to interpret.
3. **CL with CT constraint** — could optimize for lift with minimum thrust requirement, but thrust is the harder quantity to produce.
4. **Multi-objective (Pareto)** — would need pymoo, adds complexity without clear benefit for agent-based exploration.

`mean_CT` was chosen for simplicity (single scalar, higher = better) and because thrust production is the distinguishing challenge of flapping-wing design — any wing can produce lift at positive AoA, but producing net thrust from flapping is the engineering challenge.

---

## 6. Architecture Decisions

### Subdirectory structure

The ornithopter project lives in `ornithopter/` within the autoresearch repo rather than:
- **Separate repo**: Would lose the context of how it relates to autoresearch
- **Mixed with ML files**: Would conflict on `program.md`, `results.tsv`, and have incompatible dependencies (torch vs pterasoftware)

The subdirectory has its own `pyproject.toml` and `.venv`, keeping dependencies separate.

### design.py as config (not script)

In autoresearch, the agent edits `train.py` (a full script). In AutoOrnithopter, the agent edits `design.py` (a config file with constants).

**Rationale**: For ornithopter design, the interesting variation is in parameters (wing shape, kinematics), not in code structure. Making `design.py` a pure config file constrains the agent to physically meaningful modifications and prevents it from accidentally breaking the simulation pipeline.

### Separate simulate.py and evaluate.py

In autoresearch, `prepare.py` contains both data loading and evaluation. AutoOrnithopter separates them:
- `simulate.py`: Builds geometry, runs solver, extracts raw results
- `evaluate.py`: Computes fitness from raw results, validates design parameters

**Rationale**: Cleaner separation of concerns. The fitness metric can be changed independently of the simulation pipeline. Validation logic is separate from simulation logic.

---

## 7. Visualization

### PteraSoftware's built-in animate()

**How it works** (from source code analysis):
1. Opens a PyVista window showing the first timestep
2. User orients the view (rotate, zoom)
3. User presses Q to close the window
4. Iterates through all timesteps, rendering each frame offscreen (window may appear frozen)
5. If `save=True`, captures each frame as a WebP image and combines into animated WebP
6. Closes all plotters when done

The "not responding" behavior during rendering is normal — VTK is doing heavy offscreen rendering between frames.

### Custom record command

Built a non-interactive recording pipeline using PyVista's offscreen rendering:
1. Sets `pv.OFF_SCREEN = True` and creates an offscreen plotter
2. Uses a fixed isometric camera angle: `(-0.8, -0.8, 0.5)` looking at origin
3. Opens either `plotter.open_gif()` (for .gif) or `plotter.open_movie()` (for .mp4/.avi/.mov/.mkv)
4. Iterates through all timesteps, building meshes and writing frames
5. Supports lift/drag/side-force coloring and wake vortex display
6. Dark mode (`--dark`) switches background to black, text to white, panels to cyan

### Panel mesh construction

Panel meshes are built from PteraSoftware's panel vertex attributes:
```python
panel.Flpp_GP1_CgP1  # front-left point (in geometry axes, relative to CG)
panel.Frpp_GP1_CgP1  # front-right
panel.Brpp_GP1_CgP1  # back-right
panel.Blpp_GP1_CgP1  # back-left
```

Each panel becomes a quad face in a PyVista PolyData mesh.

### Scalar coloring

Per-panel scalar values (matching PteraSoftware's convention):
```python
lift_coefficient = -panel.forces_W[2] / q_inf / panel.area
drag_coefficient = -panel.forces_W[0] / q_inf / panel.area
side_coefficient =  panel.forces_W[1] / q_inf / panel.area
```

Scalars are repeated 4x per panel (once per vertex) for PyVista mesh coloring.

### Output formats

| Format | Method | Size (baseline) | Notes |
|--------|--------|-----------------|-------|
| GIF | `plotter.open_gif()` via imageio | ~7.2 MB | Large files, universal playback |
| MP4 | `plotter.open_movie()` via imageio-ffmpeg | ~1.8 MB | Much smaller, needs ffmpeg |
| AVI/MOV/MKV | `plotter.open_movie()` | Varies | Also supported |
| WebP | PteraSoftware's built-in `save=True` | Varies | Only via interactive animate() |

---

## 8. Baseline Results & Interpretation

### Default design parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| SEMI_SPAN | 0.30 m | Mid-range bird-scale (~pigeon size) |
| ROOT_CHORD | 0.08 m | Gives reasonable aspect ratio and Reynolds number |
| TAPER_RATIO | 0.50 | Moderate taper, common in bird wings |
| SWEEP_ANGLE | 5.0 deg | Slight sweep for stability |
| FLAP_FREQUENCY | 5.0 Hz | Mid-range for bird-scale ornithopter |
| FLAP_AMPLITUDE | 30.0 deg | Moderate half-stroke |
| PITCH_AMPLITUDE | 15.0 deg | Moderate feathering |
| PHASE_OFFSET | 90.0 deg | Theoretical optimum |
| MEAN_AOA | 5.0 deg | Moderate angle of attack |
| FLIGHT_SPEED | 5.0 m/s | Low-speed forward flight |

### Baseline results

```
fitness:          0.328560
mean_CT:          0.328560
mean_CL:          1.042215
mean_CD:          -0.328560
L_over_D:         3.172074  (net thrust — L/|T| ratio)
mean_thrust_N:    0.090559
mean_lift_N:      0.287261
mean_drag_N:      -0.090559
sim_seconds:      55.5
num_steps:        290
reynolds:         19920
strouhal:         0.300
reduced_freq:     0.188
```

### Physical interpretation

- **mean_thrust = 0.091 N** (~9.3 grams of thrust): The flapping wing produces net forward thrust. This is enough to overcome the drag of a small (~50g) ornithopter body.
- **mean_lift = 0.287 N** (~29.3 grams of lift): The wing produces lift. Combined with the static lift from angle of attack, this could support a ~50-60g vehicle.
- **mean_CT = 0.329**: Strong positive thrust coefficient. The flapping motion is effectively converting oscillatory motion into forward thrust.
- **mean_CL = 1.042**: Good lift coefficient, indicating the wing is generating useful lift.
- **mean_CD = -0.329**: Negative drag coefficient confirms net thrust (the flapping wing is "dragging" the aircraft forward, not backward).
- **St = 0.300**: Right in the biological optimum range (0.2-0.4). This is encouraging — the default parameters are already in a good regime.
- **Re = 19,920**: Low Reynolds number regime typical of small bird-scale flyers. Viscous effects (not captured by UVLM) would be significant at this Re.
- **Simulation time = 55.5s**: ~65 experiments per hour, ~500+ overnight.

### Caveats

These results are from an inviscid solver. Real-world performance would differ:
- Viscous drag would reduce net thrust
- Flow separation at high AoA would reduce lift
- Leading-edge vortices (not modeled) could enhance or reduce performance
- Structural flexibility (not modeled) would modify the effective kinematics

The results are best interpreted as **relative comparisons** between designs, not absolute predictions of flight performance.

---

## 9. Future Directions

### Immediate improvements

1. **Differential spanwise twist**: Apply pitch oscillation to tip WCS (non-root sections only) for more realistic wing kinematics. The root stays fixed, the tip twists — like a real bird wing.

2. **Parameter bounds enforcement**: Add hard limits in `validate_design()` for all parameters, not just the current basic checks.

3. **Multi-point evaluation**: Evaluate each design at multiple flight speeds to find designs that are good across a range of conditions.

### Medium-term enhancements

4. **Surrogate model**: After accumulating ~500 experiment results, train a neural network to predict fitness from design parameters. Then use pymoo to optimize on the surrogate (seconds instead of minutes per evaluation). Validate top candidates with PteraSoftware.

5. **Multi-objective optimization**: Use pymoo's NSGA-II to find the Pareto front of thrust vs lift vs power. The agent currently optimizes a single scalar; multi-objective would reveal trade-offs.

6. **Aeroelastic coupling**: Model wing flexibility by parameterizing spanwise stiffness distribution and computing effective kinematics from structural deflection under aerodynamic loads.

7. **Multi-wing configurations**: Tandem wings (dragonfly-style) or biplane configurations. Would require code changes to simulate.py to add additional Wing objects.

### Long-term vision

8. **High-fidelity validation pipeline**: UVLM screening (seconds) → OpenFOAM validation (hours) → wind tunnel testing. The agent explores with UVLM, the top N designs get validated with CFD.

9. **Hardware-in-the-loop**: Connect the optimization loop to a physical test rig. The agent designs → 3D prints a wing → tests on a force balance → iterates.

10. **Real-time flight simulation**: Couple the aerodynamic model with a flight dynamics model to simulate full vehicle behavior (stability, control, trajectory).

---

## 10. Key Resources & References

### Core tools

| Resource | URL | Description |
|----------|-----|-------------|
| PteraSoftware | https://github.com/camUrban/PteraSoftware | UVLM solver for flapping wings |
| Karpathy's autoresearch | https://github.com/karpathy/autoresearch | The ML experiment loop this project mirrors |
| pymoo | https://pymoo.org/ | Multi-objective optimization framework |
| OpenMDAO | https://openmdao.org/ | NASA MDO framework |
| AeroSandbox | https://github.com/peterdsharpe/AeroSandbox | Differentiable aerospace design |
| PANKH | https://github.com/coding4Acause/PANKH | Fast hovering airfoil analysis |

### Papers

| Paper | URL | Relevance |
|-------|-----|-----------|
| ChatCFD | https://arxiv.org/html/2506.02019v2 | LLM-driven CFD automation (82% success rate) |
| Autonomous Engineering Design | https://arxiv.org/html/2511.03179 | LLM airfoil optimization |
| NeuralFoil | https://arxiv.org/html/2503.16323v1 | 1000x faster airfoil evaluation via neural network |

### Ornithopter design references

- Sandra Mau, "Ornithopter Wing Optimization", University of Toronto
- MDPI Aerospace: "Ornithopter Type Flapping Wings for Autonomous MAVs"
- ResearchGate: "Kinematic and Aerodynamic Modelling of Flapping Wing Ornithopter"
- ScienceDirect: "Flapping Wing MAV: Kinematics, Membranes, and Flapping Mechanisms"
- Royal Society: "Aerodynamic Efficiency of Bioinspired Flapping Wing at Low Re"
- Nathan Chronister, "The Ornithopter Design Manual" (ornithopter.org)
- ornithopter.org: "How Ornithopters Work — Wing Design"

### Biology references

- PLOS ONE: "Universal Wing- and Fin-Beat Frequency Scaling"
- J Exp Biol: "Scaling of Wingbeat Frequency with Body Mass in Bats"
- Stanford: "Wing Shapes and Flight"
- Royal Society Interface: "Hummingbird Wing Efficacy and Aspect Ratio"
