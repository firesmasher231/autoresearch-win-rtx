# MAV Ornithopter Physical Build Guide

Reference document for translating simulation outputs into a flyable proof-of-concept.

**Target**: 30–100 g flapping-wing MAV, 50 g nominal design point.
**Fabrication**: CNC, laser cutter, 3D printer, soldering station, precision hand tools.
**Goal**: Proof of concept — tethered power acceptable for first flights.

---

## 1. Target Specifications

| Parameter            | Value              | Notes                                     |
|----------------------|--------------------|-----------------------------------------|
| All-up weight        | 50 g (30–100 g)   | Includes battery or tether adapter       |
| Total wingspan       | 200–500 mm         | 2 × SEMI_SPAN from design.py            |
| Flap frequency       | 8–18 Hz            | Scaling law f ∝ m^(−0.43) for this class |
| Flight speed         | 2–8 m/s            | MAV regime; lower for initial tests      |
| Wing loading         | 5–20 N/m²          | Computed from wing area and weight       |
| Endurance (battery)  | 3–15 min           | Depends on cell size; tether = unlimited |
| Endurance (tethered) | Unlimited           | 28 AWG tether, bench supply at 3.7 V    |

---

## 2. Reference Platforms

### DelFly Nimble (TU Delft, 2018)
- Weight: 29 g (with battery)
- Wingspan: 290 mm (four wings, X-configuration)
- Flap frequency: 17 Hz
- Endurance: ~5 min
- Actuators: 2 servos for independent wing control
- Key paper: Karásek et al., *Science* 2018

### Festo BionicBee (2023)
- Weight: 34 g
- Wingspan: 240 mm
- Flap frequency: 15–20 Hz
- Three degrees of freedom per wing
- Brushless motor with compact gearbox

### AeroVironment Nano Hummingbird (DARPA, 2011)
- Weight: 19 g (with battery and camera)
- Wingspan: 160 mm
- Flap frequency: 30 Hz
- Endurance: ~8 min hovering
- Two-wing design, figure-eight kinematics

### DelFly Micro (TU Delft, 2008)
- Weight: 3.07 g
- Wingspan: 100 mm
- Weight breakdown: battery 32.6%, motor 14.7%, actuators 16.3%, electronics 19.5%, airframe 16.9%
- This breakdown scales roughly to larger MAVs

---

## 3. Weight Budget Breakdown (50 g nominal)

| Component             | Mass (g) | % of total | Notes                                |
|-----------------------|----------|-----------|--------------------------------------|
| Wings (pair)          | 4–6      | 8–12%     | CF spars + Mylar film + adhesive     |
| Motor + gearbox       | 5–8      | 10–16%    | Coreless motor with 2-stage spur     |
| Linkage mechanism     | 4–6      | 8–12%     | Crank, connecting rod, wing mount    |
| Battery (1S LiPo)     | 12–18    | 24–36%    | 150–300 mAh; or 2 g tether adapter  |
| Electronics (RC)      | 6–10     | 12–20%    | Receiver + 2 actuators + wiring      |
| Fuselage + tail       | 4–6      | 8–12%     | CF tube boom + 3D-printed mounts     |
| Fasteners + adhesive  | 2–3      | 4–6%      | CA glue, thread, micro screws        |
| **Total**             | **37–57**| —         | Target 50 g center of range          |

**Budget rule**: if any subsystem comes in over budget, compensate elsewhere or reduce battery size. Tethered flight removes the battery entirely, saving 12–18 g.

---

## 4. Wing Construction

### Materials

| Material                    | Spec             | Linear/areal density | Source            |
|-----------------------------|------------------|---------------------|-------------------|
| CF rod, leading edge        | Ø 0.7–1.0 mm    | 0.6–1.3 g/m        | Hobby suppliers   |
| CF rod, wing veins          | Ø 0.3–0.5 mm    | 0.1–0.3 g/m        | Hobby suppliers   |
| CF tube, wing root spar     | Ø 1.5 mm        | ~1.5 g/m (tube)    | Hobby suppliers   |
| Mylar film (standard)       | 12.5 μm PET     | 17.4 g/m²          | Drafting supply   |
| Mylar film (ultralight)     | 6 μm PET        | 8.3 g/m²           | Specialty film    |
| Kapton (high fatigue)       | 12.5 μm PI      | 17.8 g/m²          | Electronics supply|
| Icarex P31 (tough option)   | 31 g/m² ripstop  | 33 g/m²           | Kite supply       |

### Wing Mass Estimate

For a single wing with SEMI_SPAN = 0.20 m, ROOT_CHORD = 0.08 m, TAPER_RATIO = 0.5:
- Planform area: 0.5 × (0.08 + 0.04) × 0.20 = 0.012 m²
- Film mass (12.5 μm Mylar): 0.012 × 17.4 = 0.21 g
- Leading edge spar (0.8 mm CF, 0.20 m): 0.8 × 0.20 = 0.16 g
- Root spar section (1.0 mm CF, 0.08 m): 1.3 × 0.08 = 0.10 g
- Two vein ribs (0.4 mm CF, avg 0.05 m each): 0.2 × 0.10 = 0.02 g
- Adhesive (CA + reinforcement tape): ~0.2 g
- **Single wing total: ~0.7 g**
- **Wing pair: ~1.5 g** (well within 4–6 g budget; budget remainder covers wing mount hardware)

### Fabrication Steps

1. **Cut CF rods to length** — rotary tool with diamond disc, deburr ends
2. **Lay out spar frame on flat template** — laser-cut acrylic jig recommended
3. **Bond joints with thin CA glue** — apply with needle applicator; reinforce root joint with thread wrap + CA
4. **Apply film** — lay Mylar on frame, heat-shrink with iron at 120°C for PET (80°C for pre-shrunk), or use spray adhesive for Kapton
5. **Trim film** — hobby knife along spar outline, leave 2 mm margin folded over leading edge
6. **Verify symmetry** — weigh both wings; mass difference < 0.1 g

### Passive Pitch via Film Flexibility

The simulation parameter PITCH_AMPLITUDE is realized physically through the wing's chordwise flexibility. A rigid leading edge spar with a flexible trailing membrane naturally produces pitch variation during the flap stroke. The membrane's stiffness (controlled by film thickness and chord length) determines the effective pitch amplitude and phase.

- **More pitch (higher PITCH_AMPLITUDE)**: use thinner film (6 μm), fewer chord ribs, longer chord
- **Less pitch (lower PITCH_AMPLITUDE)**: use thicker film (12.5 μm), add chord-stiffening ribs, shorter chord
- **Phase offset** is inherently ~90° for passive pitch, matching the theoretical optimum

---

## 5. Motor Selection

### Requirements

For flapping at frequency *f* with gear ratio *G*:
- Motor RPM = f × 60 × G
- Example: 15 Hz × 60 × 25:1 = 22,500 RPM (typical for 4–7 mm coreless motors)

Motor must deliver enough torque through the gearbox to overcome:
1. Wing inertial loads (dominant at high frequency)
2. Aerodynamic loads (dominant at high speed / large wings)
3. Mechanism friction losses

### Candidate Motors

| Motor                  | Diameter | Mass (bare) | Mass (w/ gearbox) | Voltage | Typical RPM    | Power   |
|------------------------|----------|-------------|-------------------|---------|----------------|---------|
| Chaoli CL-0408-14000   | 4 mm     | 1.2 g       | 2.5–3.5 g        | 3.7 V   | 14,000 RPM     | 0.3–0.8 W |
| Chaoli CL-0612-17000   | 6 mm     | 2.0 g       | 3.5–5.0 g        | 3.7 V   | 17,000 RPM     | 0.5–1.5 W |
| Didel MK04S-10         | 4 mm     | —           | 3.1 g             | 3.0 V   | 10,000 RPM     | 0.5–1.0 W |
| Didel MK06M-25         | 6 mm     | —           | 4.5 g             | 3.7 V   | 25,000 RPM     | 0.8–2.0 W |
| Generic 7 mm coreless  | 7 mm     | 3.5 g       | 5.0–7.0 g        | 3.7 V   | 20,000–30,000  | 1.0–3.0 W |

### Gear Ratio Selection

| Flap frequency target | Recommended gear ratio | Motor RPM needed |
|----------------------|----------------------|------------------|
| 8–10 Hz              | 20:1                 | 9,600–12,000     |
| 12–15 Hz             | 25:1                 | 18,000–22,500    |
| 15–18 Hz             | 30:1                 | 27,000–32,400    |

Two-stage spur gearbox is standard. Gear material: Delrin/POM for first stage, nylon for second stage. 3D-print the gearbox housing (SLA resin for precision). Didel sells pre-built gearboxes; for DIY, module-0.3 gears from SDP/SI or Mädler.

### Torque Verification

After the agent produces a best design, verify the motor can drive it:

1. Compute wing moment of inertia: I ≈ (1/3) × m_wing × SEMI_SPAN²
2. Peak angular acceleration: α = (2π × f)² × FLAP_AMPLITUDE_rad
3. Required torque at wing root: τ_wing = I × α + τ_aero (from simulation mean_drag_N × SEMI_SPAN/3)
4. Required motor torque: τ_motor = τ_wing / G / η_gear (η_gear ≈ 0.6 for two-stage spur)
5. Check that τ_motor < motor stall torque at operating voltage

---

## 6. Linkage Mechanism

The motor's continuous rotation must convert to oscillating flap motion. Two main options:

### Option A: Four-Bar Crank-Rocker

- Simplest mechanism: motor drives a crank, wing is the rocker
- **Amplitude limit: 50–65°** — this is the hard constraint on FLAP_AMPLITUDE
- Advantages: simple, low part count, easy to 3D print
- Sizing: crank radius ≈ FLAP_AMPLITUDE / (2 × linkage ratio), coupler length ~ 2× crank
- For 40° amplitude: crank radius ~5 mm, coupler ~12 mm, rocker ~15 mm

### Option B: Slider-Crank with Rocker

- Adds a sliding joint to overcome the four-bar amplitude limit
- **Can achieve 60–80° amplitude**, but adds friction and mass
- Use only if the agent's optimal design requires FLAP_AMPLITUDE > 55°
- More complex to fabricate; consider 3D-printed guides with PTFE inserts

### Recommendation

Start with a **four-bar crank-rocker**. Constrain FLAP_AMPLITUDE ≤ 55° in the agent's search space (practical limit with reliable operation; theoretical 65° minus margin). If the agent consistently pushes against this limit, build a slider-crank for the next iteration.

### Fabrication

- 3D-print the crank disc and rocker mount (SLA resin, 0.05 mm layer)
- Use 0.8 mm steel music wire for the crank pin and connecting rod
- Wing root attaches to the rocker arm via a press-fit CF tube collar
- All pivot points: brass eyelet bearings or 0.5 mm ID brass tubing

---

## 7. Power System

### Power Draw Estimate

From simulation output, estimate electrical power:

1. Aerodynamic power: P_aero ≈ mean_drag_N × FLIGHT_SPEED (watts)
2. Inertial power: P_inertia ≈ 2 × (1/3) × m_wing × SEMI_SPAN² × (2π × f)² × FLAP_AMPLITUDE_rad² × f
3. Mechanical power: P_mech = P_aero + P_inertia
4. Electrical power: P_elec = P_mech / (η_motor × η_gear) where η_motor ≈ 0.55, η_gear ≈ 0.60
5. Typical range for 50 g MAV: **1–3 W electrical**

### Battery Options (1S LiPo, 3.7 V nominal)

| Capacity | Mass    | Energy (Wh) | Flight time at 2W |
|----------|---------|-------------|-------------------|
| 100 mAh  | 2.5 g   | 0.37        | ~11 min           |
| 150 mAh  | 4.0 g   | 0.56        | ~17 min           |
| 200 mAh  | 5.5 g   | 0.74        | ~22 min           |
| 300 mAh  | 8.0 g   | 1.11        | ~33 min           |

Rule of thumb: **~1 g per 30 mAh** at 140–200 Wh/kg energy density.

### Tethered Power (recommended for early flights)

- 28–30 AWG silicone wire, 2-conductor (power + ground)
- Tether mass: ~3 g/m; keep under 1 m for indoor tests
- Bench power supply: 3.7 V, 1 A current limit
- Add a 2 g tether adapter board (small PCB with decoupling cap + connector)
- **Saves 12–18 g** vs battery — huge margin for a 50 g vehicle

### Trade-off

| Mode     | Mass overhead | Endurance  | Best for                        |
|----------|-------------|------------|--------------------------------|
| Battery  | 4–8 g       | 10–30 min  | Outdoor tests, free flight     |
| Tethered | 2–3 g       | Unlimited  | First flights, tuning, indoors |

Start tethered. Switch to battery only after the mechanism is validated.

---

## 8. Electronics

### Minimum RC Control Stack

| Component                        | Mass   | Function                          |
|----------------------------------|--------|----------------------------------|
| 2.4 GHz receiver (e.g., FrSky XM) | 1.6 g  | RC link to transmitter           |
| Brushed motor ESC (1S, 5A)      | 1.0 g  | Throttle control                 |
| Magnetic actuator × 2 (Didel)   | 1.5 g each | Rudder + elevator steering   |
| Wiring + connector              | 1.0 g  | JST-PH for battery, signal wires|
| **Total**                        | **6.6 g** |                               |

### Optional: Autopilot / Stabilization

| Component                        | Mass   | Notes                            |
|----------------------------------|--------|----------------------------------|
| ESP32-C3 module                  | 2.0 g  | WiFi telemetry, basic IMU fusion |
| MPU-6050 IMU breakout            | 1.0 g  | 6-axis gyro + accel              |
| BMP280 barometer                 | 0.5 g  | Altitude hold                    |
| Custom STM32 FC (designed PCB)   | 1.5 g  | All-in-one, minimal mass         |

For proof-of-concept, skip the autopilot. Manual RC control is sufficient.

---

## 9. From Simulation to Hardware

When the agent produces an optimized design.py, translate each parameter to physical dimensions:

### Wing Geometry

| design.py parameter  | Physical meaning                              | How to realize                              |
|----------------------|----------------------------------------------|---------------------------------------------|
| `SEMI_SPAN`          | Half-wingspan in meters                      | Cut leading edge CF rod to this length      |
| `ROOT_CHORD`         | Wing width at root                           | Root rib length (CF + film)                 |
| `TAPER_RATIO`        | Tip chord / root chord                       | Cut tip rib to ROOT_CHORD × TAPER_RATIO    |
| `SWEEP_ANGLE`        | Leading edge sweep                           | Angle the LE spar back from the root hinge  |
| `DIHEDRAL_ANGLE`     | Wing upward angle                            | Bend or shim the wing root mount            |
| `ROOT_AIRFOIL`       | Airfoil profile (simulation only)            | Flat plate in practice; camber from film sag|
| `TIP_AIRFOIL`        | Airfoil profile (simulation only)            | Flat plate; thin film has negligible camber  |

Note: at MAV Reynolds numbers (Re < 50,000), thin flat-plate and cambered-plate airfoils perform comparably to profiled airfoils. The simulation's NACA profiles give directional guidance on camber benefit, but the physical wing is a membrane that naturally adopts a cambered shape under aero load.

### Flapping Kinematics

| design.py parameter  | Physical meaning                              | How to realize                              |
|----------------------|----------------------------------------------|---------------------------------------------|
| `FLAP_FREQUENCY`     | Flapping rate (Hz)                           | Motor RPM / gear ratio / 60                 |
| `FLAP_AMPLITUDE`     | Half-stroke angle (degrees)                  | Set by crank radius / rocker arm length     |
| `PITCH_AMPLITUDE`    | Wing twist during flap                       | Passive — controlled by film stiffness      |
| `PHASE_OFFSET`       | Pitch-flap phase lag                         | Passive — naturally ~90° for membrane wings |
| `MEAN_AOA`           | Body angle relative to flight path           | Set by CG position and tail incidence       |

### Flight Conditions

| design.py parameter  | Physical meaning                              | How to realize                              |
|----------------------|----------------------------------------------|---------------------------------------------|
| `FLIGHT_SPEED`       | Forward airspeed (m/s)                       | Achieved in flight; test on treadmill/wind tunnel for validation |

### Quick Translation Checklist

Given a final design.py from the agent:

1. **Wing planform**: draw on graph paper at 1:1 scale. Verify it looks reasonable.
2. **Wing area**: compute WING_AREA. Check lift: L = 0.5 × 1.225 × FLIGHT_SPEED² × WING_AREA × mean_CL. Must exceed weight (0.05 × 9.81 = 0.49 N).
3. **Frequency**: select motor + gear ratio to hit FLAP_FREQUENCY ± 10%.
4. **Amplitude**: size crank-rocker linkage for FLAP_AMPLITUDE. If > 55°, need slider-crank.
5. **Motor power**: estimate P_elec (section 7). Select motor and battery accordingly.
6. **Weight check**: sum all components (section 3). Must be < lift / 9.81.

---

## 10. Physical Constraints for program.md

These are the bounds to add to the agent's instructions so it only explores buildable designs.

```
SEMI_SPAN:       0.10 – 0.25 m     Total wingspan 200–500 mm. Longer needs heavier spars.
ROOT_CHORD:      0.04 – 0.10 m     Narrower saves wing mass; wider is structurally easier.
TAPER_RATIO:     0.30 – 1.00       Below 0.3, tip is too fragile for film membrane.
SWEEP_ANGLE:     0 – 15 deg        Above 15° is hard to build with straight CF spars.
DIHEDRAL_ANGLE:  0 – 8 deg         Negative is unstable; above 8° is hard at the root joint.
FLAP_FREQUENCY:  8 – 18 Hz         Scaling law for 30–100 g class. Motor/gear constraint.
FLAP_AMPLITUDE:  20 – 55 deg       Above 55° exceeds four-bar linkage practical limit.
PITCH_AMPLITUDE: 10 – 30 deg       Passive pitch from film flex; above 30° causes flutter.
PHASE_OFFSET:    75 – 105 deg      90° optimal; real wings self-select near this range.
MEAN_AOA:        2 – 8 deg         Below 2° gives insufficient lift; above 8° risks stall.
FLIGHT_SPEED:    2 – 8 m/s         MAV regime. Below 2 is near-hover; above 8 is large-bird scale.
```

**Derived constraints the agent should verify after each simulation:**
- Wing loading (weight / WING_AREA) should be 5–20 N/m²
- mean_lift_N must exceed target weight × g (0.49 N for 50 g)
- Strouhal number should be 0.2–0.5 (already checked in evaluate.py)
- Reynolds number will be in 5,000–50,000 range (low-Re regime; expected)
