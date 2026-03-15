# auto-ornithopter

Autonomous ornithopter (flapping-wing) design optimization using PteraSoftware UVLM.
The LLM agent iterates on wing design parameters, simulates each design, and keeps improvements.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `mar14`). The branch `ornithopter/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b ornithopter/<tag>` from current main.
3. **Read the in-scope files**: Read these files for full context:
   - `design.py` — the ONLY file you modify. Wing geometry, flapping kinematics, flight conditions.
   - `simulate.py` — simulation runner. Wraps PteraSoftware UVLM. Do not modify.
   - `evaluate.py` — fitness computation. Do not modify.
4. **Verify PteraSoftware installed**: Run `uv run python -c "import pterasoftware; print('OK')"`.
5. **Initialize results.tsv**: Create with just the header row if not already present.
6. **Confirm and go**: Confirm setup looks good.

Once confirmed, start the experimentation loop.

## Experimentation

Each experiment simulates one ornithopter design using the Unsteady Ring Vortex Lattice Method (UVLM). Typical simulation time: **10-60 seconds** (much faster than autoresearch's 5-minute ML training). You can run **60+ experiments per hour**.

**What you CAN do:**
- Modify `design.py` — this is the ONLY file you edit. You may change:
  - Wing geometry: semi-span, root chord, taper ratio, sweep, dihedral, airfoil
  - Wing planform shape: mid-span fraction, mid-chord ratio, mid-sweep offset
  - Flapping kinematics: frequency, amplitude, pitch angle, phase offset
  - Flight conditions: speed, angle of attack
  - Panel counts: NUM_SPANWISE_PANELS (min 4), NUM_CHORDWISE_PANELS (min 3)

**What you MUST NOT change in design.py:**
- `AIR_DENSITY` — physical constant (1.225 kg/m³), not a design parameter
- `KINEMATIC_VISCOSITY` — physical constant (15.06e-6 m²/s), not a design parameter
- `NUM_CYCLES` — locked at 3 (fewer = unreliable cycle-averaging, more = wasted time)

**What you CANNOT do:**
- Modify `simulate.py`. It contains the fixed simulation pipeline.
- Modify `evaluate.py`. It contains the ground truth fitness computation.
- Install new packages or add dependencies.

**The goal is simple: get the highest `fitness`.** The fitness metric is **propulsive efficiency** — thrust per watt of estimated flapping power. Higher fitness = more efficient design.

`fitness = corrected_thrust / P_flap_estimate`

Where corrected_thrust subtracts estimated parasitic drag (UVLM is inviscid and doesn't model skin friction), and P_flap_estimate captures the cubic scaling of flapping power with tip speed.

**A good ornithopter design produces:**
- mean_lift_N ≥ 0.49 N (enough lift to support 50g — **hard requirement**, steep penalty below this)
- Positive corrected_thrust (net thrust after parasitic drag)
- High fitness (thrust achieved cheaply — low flapping power cost)
- Strouhal number in [0.2, 0.4] (biologically optimal range for propulsive efficiency)
- Low P_flap_est_W (less power needed = smaller motor, longer flight time)

**Simulation time** is a soft constraint. Most runs complete in 10-60 seconds. If a run exceeds 2 minutes, consider reducing NUM_SPANWISE_PANELS, NUM_CHORDWISE_PANELS, or NUM_CYCLES.

**Simplicity criterion**: All else being equal, simpler designs are better. A small fitness improvement from a very unusual parameter combination is still interesting — this is research. But if two designs give similar fitness, prefer the one with more conventional parameters, as it's more likely to transfer to real hardware.

**The first run**: Always establish the baseline first by running the initial design as-is.

## Output format

Once the simulation finishes it prints a summary like this:

```
---
fitness:          0.012345
mean_CT:          0.012345
mean_CL:          0.345678
mean_CD:          0.023456
L_over_D:         14.735000
mean_thrust_N:    0.123456
mean_lift_N:      3.456789
mean_drag_N:      0.234567
sim_seconds:      23.4
num_steps:        180
reynolds:         26533
strouhal:         0.250
reduced_freq:     0.251
```

Extract the key metric: `grep "^fitness:" run.log`

## Logging results

When an experiment is done, log it to `results.tsv` (tab-separated, NOT comma-separated).

The TSV has a header row and 5 columns:

```
commit	fitness	sim_time	status	description
```

1. git commit hash (short, 7 chars)
2. fitness achieved (e.g. 0.012345) — use 0.000000 for crashes
3. simulation time in seconds, round to .1f (e.g. 23.4) — use 0.0 for crashes
4. status: `keep`, `discard`, or `crash`
5. short text description of what this experiment tried

Example:

```
commit	fitness	sim_time	status	description
a1b2c3d	0.012345	23.4	keep	baseline
b2c3d4e	0.018900	31.2	keep	increase flap amplitude to 40 deg
c3d4e5f	0.005200	19.8	discard	switch to naca0012 symmetric airfoil
d4e5f6g	0.000000	0.0	crash	aspect ratio too high (structural)
```

## The experiment loop

The experiment runs on a dedicated branch (e.g. `ornithopter/mar14`).

LOOP FOREVER:

1. Look at the current design in `design.py` and past results in `results.tsv`
2. Modify `design.py` with an experimental idea
3. git commit
4. Run the experiment: `uv run simulate.py > run.log 2>&1`
5. Read out the results: `grep "^fitness:\|^mean_lift_N:\|^P_flap_est_W:\|^sim_seconds:" run.log`
6. If the grep output is empty, the run crashed. Run `tail -n 50 run.log` to read the traceback.
7. Record the results in the TSV
8. If fitness improved (higher), you "advance" the branch, keeping the git commit
9. If fitness is equal or worse, you git reset back to where you started
10. Sync results to mounted volume: `./sync-results.sh` (if running in Docker)

**Timeout**: If a run exceeds 2 minutes, kill it and treat it as a failure.

**Crashes**: If a run crashes, use your judgment: If it's a fixable bug (typo, bad airfoil name), fix and re-run. If the design is fundamentally invalid (negative chord, extreme angles), log "crash" and move on.

## What to explore

The design space is rich. Here are ideas organized by category:

**Wing planform:**
- Aspect ratio (change span and/or chord)
- Taper ratio (rectangular vs pointed wings)
- Sweep angle (0 to 15 degrees)
- Different root and tip airfoils (naca0012, naca2412, naca4412, naca6412)
- **Planform shape via mid-section** (the 3-section wing is root → mid → tip):
  - Butterfly: MID_CHORD_RATIO = 1.5-2.0 (wide at middle, narrow at root+tip)
  - Wasp/dragonfly: MID_CHORD_RATIO = 0.5-0.7 (narrow throughout)
  - Elliptical: MID_CHORD_RATIO ≈ 1.1, MID_SPAN_FRACTION ≈ 0.4
  - Scalloped: combine MID_SWEEP_OFFSET with high MID_CHORD_RATIO
  - Delta: low TAPER_RATIO + MID_CHORD_RATIO close to linear interpolation

**Flapping kinematics:**
- Frequency (higher frequency = more thrust but more power)
- Amplitude (15-70 degrees half-stroke)
- Pitch amplitude and phase offset (theoretical optimum: phase=90 deg)
- Try hummingbird kinematics (high freq ~15Hz, moderate amplitude ~50 deg)
- Try albatross kinematics (low freq ~3Hz, low amplitude ~20 deg, high speed)

**Flight conditions:**
- Speed sweep (find optimal cruise speed for a given wing)
- Angle of attack optimization

**Bio-inspired patterns:**
- Hummingbird: AR~4, f~15Hz, amp~50deg, V~5m/s
- Pigeon: AR~6, f~8Hz, amp~35deg, V~10m/s
- Albatross: AR~12, f~2Hz, amp~20deg, V~15m/s
- Dragonfly: two sets of wings (would need code change, skip for now)

**Strouhal number tuning:**
- Biological flyers converge on St=0.2-0.4
- Adjust frequency, amplitude, and speed to hit this range
- Lower St = more efficient cruise, higher St = more thrust

**Key physics to keep in mind:**
- Thrust comes from the component of aerodynamic force in the flight direction during flapping
- The pitch-flap phase offset controls whether the wing "feathers" to reduce drag on the upstroke
- Higher aspect ratio = less induced drag but more structural challenge
- Lower Reynolds number = thicker boundary layers, earlier separation

## Physical Constraints

The simulation must produce designs that are physically buildable as a 30–100 g MAV (50 g nominal). These bounds come from real hardware limits — motor/gearbox availability, linkage mechanism geometry, structural material properties, and scaling laws for flapping flight. See `build_details.md` for derivations.

**Hard parameter bounds (override the wider ranges in design.py header):**

| Parameter          | Min   | Max   | Physical reason                                        |
|--------------------|-------|-------|-------------------------------------------------------|
| `SEMI_SPAN`        | 0.10 m | 0.25 m | Total wingspan 200–500 mm; longer needs heavier spars |
| `ROOT_CHORD`       | 0.04 m | 0.10 m | Narrower saves wing mass; wider is structurally easier |
| `TAPER_RATIO`      | 0.30  | 1.00  | Below 0.3, tip is too fragile for film membrane       |
| `SWEEP_ANGLE`      | 0°    | 15°   | Above 15° hard to build with straight CF spars        |
| `DIHEDRAL_ANGLE`   | 0°    | 8°    | Negative is unstable; above 8° hard at root joint     |
| `MID_SPAN_FRACTION`| 0.20  | 0.80  | Mid-section position; too near root/tip = degenerate  |
| `MID_CHORD_RATIO`  | 0.50  | 2.00  | Mid chord / root chord; >1 = butterfly-like planform  |
| `MID_SWEEP_OFFSET` | -0.02 m | 0.02 m | Fore/aft shift at mid-section                      |
| `FLAP_FREQUENCY`   | 8 Hz  | 18 Hz | Scaling law f ∝ m^(−0.43) for 30–100 g class         |
| `FLAP_AMPLITUDE`   | 20°   | 55°   | Above 55° exceeds four-bar linkage practical limit    |
| `PITCH_AMPLITUDE`  | 10°   | 30°   | Passive pitch from film flex; above 30° causes flutter |
| `PHASE_OFFSET`     | 75°   | 105°  | 90° optimal; membrane wings self-select near this     |
| `MEAN_AOA`         | 2°    | 8°    | Below 2° insufficient lift; above 8° risks stall     |
| `FLIGHT_SPEED`     | 2 m/s | 8 m/s | MAV regime; below 2 is near-hover, above 8 is large-bird |

**Derived constraints to verify after each run:**
- **Lift check**: `mean_lift_N` ≥ 0.49 N (supports 50 g against gravity)
- **Wing loading**: target weight / WING_AREA should be 5–20 N/m²
- **Strouhal number**: 0.2–0.5 (already penalized in evaluate.py outside this range)

These constraints are meant to keep the agent in the buildable regime. The agent should still explore the full range within these bounds — the optimal design is unknown.

## Exporting results

When you've converged (fitness hasn't improved in 10+ experiments, or you've exhausted the design space), export a snapshot of ALL experiment data before continuing.

**Export procedure:**

1. Determine the next version number by listing existing folders:
   ```
   ls auto-research-results/
   ```
   Pick the next `vN-<tag>` name (e.g., if `v2-mar15` exists, use `v3-mar15`).

2. Create the export folder and copy results:
   ```bash
   EXPORT_DIR="auto-research-results/v3-mar15"
   mkdir -p "$EXPORT_DIR/designs"

   # Core files
   cp results.tsv "$EXPORT_DIR/"
   cp design.py "$EXPORT_DIR/"
   cp sim_output.json "$EXPORT_DIR/" 2>/dev/null
   cp run.log "$EXPORT_DIR/" 2>/dev/null
   ```

3. Export every design.py snapshot from git history (one per experiment):
   ```bash
   git log --oneline --all -- design.py | while read hash msg; do
     safe_msg=$(echo "$msg" | tr ' /:' '_' | head -c 60)
     git show "${hash}:design.py" > "$EXPORT_DIR/designs/${hash}_${safe_msg}.py" 2>/dev/null
   done
   ```

4. If running in Docker, also sync to the mounted volume:
   ```bash
   cp -r "$EXPORT_DIR" /app/results/ 2>/dev/null
   ./sync-results.sh 2>/dev/null
   ```

5. Log the export:
   ```
   echo "Exported to $EXPORT_DIR at $(date)"
   ```

After exporting, **keep going** — the export is a checkpoint, not a stop signal. Try new strategies, wider sweeps, or revisit discarded ideas with fresh combinations.

## NEVER STOP

Once the experiment loop has begun, do NOT pause to ask the human. Do NOT ask "should I keep going?" or "is this a good stopping point?". The human might be asleep and expects you to continue working *indefinitely* until manually stopped.

If you run out of ideas, think harder:
- Try combining parameters from your two best designs
- Try extreme values to map the design space boundaries
- Try systematic sweeps of one parameter at a time
- Re-read the physics notes above for new angles

Each experiment takes ~30 seconds on average, so you can run ~120/hour, ~1000 overnight.
