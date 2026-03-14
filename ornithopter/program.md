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
- Modify `design.py` — this is the ONLY file you edit. Everything is fair game:
  - Wing geometry: semi-span, root chord, taper ratio, sweep, dihedral, airfoil
  - Flapping kinematics: frequency, amplitude, pitch angle, phase offset
  - Flight conditions: speed, angle of attack
  - Simulation resolution: panel counts, number of cycles

**What you CANNOT do:**
- Modify `simulate.py`. It contains the fixed simulation pipeline.
- Modify `evaluate.py`. It contains the ground truth fitness computation.
- Install new packages or add dependencies.

**The goal is simple: get the highest `fitness`.** The fitness metric is the cycle-averaged thrust coefficient (mean_CT) with a penalty for negative lift. Higher fitness = better design.

**A good ornithopter design produces:**
- Positive mean_CT (net thrust from flapping — this IS the fitness metric)
- Positive mean_CL (enough lift to fly — negative CL incurs a -1.0 penalty)
- Reasonable L/D ratio (aerodynamic efficiency)
- Strouhal number in [0.2, 0.4] (biologically optimal range for propulsive efficiency)

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
5. Read out the results: `grep "^fitness:\|^mean_CL:\|^sim_seconds:" run.log`
6. If the grep output is empty, the run crashed. Run `tail -n 50 run.log` to read the traceback.
7. Record the results in the TSV
8. If fitness improved (higher), you "advance" the branch, keeping the git commit
9. If fitness is equal or worse, you git reset back to where you started

**Timeout**: If a run exceeds 2 minutes, kill it and treat it as a failure.

**Crashes**: If a run crashes, use your judgment: If it's a fixable bug (typo, bad airfoil name), fix and re-run. If the design is fundamentally invalid (negative chord, extreme angles), log "crash" and move on.

## What to explore

The design space is rich. Here are ideas organized by category:

**Wing planform:**
- Aspect ratio (change span and/or chord)
- Taper ratio (rectangular vs pointed wings)
- Sweep angle (0 to 25 degrees)
- Different root and tip airfoils (naca0012, naca2412, naca4412, naca6412)

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

## NEVER STOP

Once the experiment loop has begun, do NOT pause to ask the human. Do NOT ask "should I keep going?" or "is this a good stopping point?". The human might be asleep and expects you to continue working *indefinitely* until manually stopped.

If you run out of ideas, think harder:
- Try combining parameters from your two best designs
- Try extreme values to map the design space boundaries
- Try systematic sweeps of one parameter at a time
- Re-read the physics notes above for new angles

Each experiment takes ~30 seconds on average, so you can run ~120/hour, ~1000 overnight.
