"""
Ornithopter Design Parameters
==============================

Edit any parameter below to change the wing design, then run:

    uv run simulate.py > run.log 2>&1

Parameter ranges (physically buildable bounds — see build_details.md):
  SEMI_SPAN:           0.10 - 0.25 m   (total wingspan 200-500 mm)
  ROOT_CHORD:          0.04 - 0.10 m
  TAPER_RATIO:         0.30 - 1.00     (below 0.3 too fragile for film wing)
  SWEEP_ANGLE:         0 - 15 deg      (above 15 hard with straight CF spars)
  DIHEDRAL_ANGLE:      0 - 8 deg
  MID_SPAN_FRACTION:   0.20 - 0.80     (mid-section position along span)
  MID_CHORD_RATIO:     0.50 - 2.00     (mid chord / root chord; >1 = butterfly)
  MID_SWEEP_OFFSET:    -0.02 - 0.02 m  (fore/aft shift at mid-section)
  FLAP_FREQUENCY:      8 - 18 Hz       (scaling law for 30-100g MAV)
  FLAP_AMPLITUDE:      20 - 55 deg     (four-bar linkage limit)
  PITCH_AMPLITUDE:     10 - 30 deg     (passive pitch from film flex)
  PHASE_OFFSET:        75 - 105 deg
  MEAN_AOA:            2 - 8 deg
  FLIGHT_SPEED:        2 - 8 m/s       (MAV regime)
  ROOT_AIRFOIL:        NACA 4-series (e.g. "naca0012", "naca2412", "naca4412")
  TIP_AIRFOIL:         NACA 4-series
"""

import math

# ---------------------------------------------------------------------------
# Wing Geometry
# ---------------------------------------------------------------------------

SEMI_SPAN = 0.20             # Half-wingspan, meters
ROOT_CHORD = 0.08            # Chord at wing root, meters
TAPER_RATIO = 0.50           # Tip chord / root chord [0.25 - 1.0]
SWEEP_ANGLE = 5.0            # Quarter-chord sweep, degrees
DIHEDRAL_ANGLE = 0.0         # Upward angle from root, degrees
ROOT_AIRFOIL = "naca2412"    # Root airfoil profile
TIP_AIRFOIL = "naca2412"     # Tip airfoil profile

# Mid-span section — controls wing planform shape
# Set MID_CHORD_RATIO > 1.0 for butterfly-like (wider at middle)
# Set MID_CHORD_RATIO < 1.0 for wasp-like (narrower at middle)
# Set MID_CHORD_RATIO = linear interpolation value for standard taper
MID_SPAN_FRACTION = 0.50     # Where along span (0=root, 1=tip)
MID_CHORD_RATIO = 0.75       # Chord at mid / root chord (0.75 = linear taper)
MID_SWEEP_OFFSET = 0.0       # Fore/aft shift at mid-section, meters

# ---------------------------------------------------------------------------
# Flapping Kinematics
# ---------------------------------------------------------------------------

FLAP_FREQUENCY = 12.0        # Flapping frequency, Hz
FLAP_AMPLITUDE = 30.0        # Half-stroke amplitude, degrees
PITCH_AMPLITUDE = 15.0       # Maximum pitch/twist angle, degrees
PHASE_OFFSET = 90.0          # Phase lag between pitch and flap, degrees
MEAN_AOA = 5.0               # Mean angle of attack, degrees

# ---------------------------------------------------------------------------
# Flight Conditions
# ---------------------------------------------------------------------------

FLIGHT_SPEED = 5.0           # Freestream velocity, m/s
AIR_DENSITY = 1.225          # Air density, kg/m^3  *** LOCKED — physical constant ***
KINEMATIC_VISCOSITY = 15.06e-6  # Kinematic viscosity, m^2/s  *** LOCKED — physical constant ***

# ---------------------------------------------------------------------------
# Simulation Resolution
# ---------------------------------------------------------------------------

NUM_SPANWISE_PANELS = 8      # Panels along span (min 4; higher = more accurate, slower)
NUM_CHORDWISE_PANELS = 6     # Panels along chord (min 3; higher = more accurate, slower)
NUM_CYCLES = 3               # *** LOCKED at 3 — do not change ***

# ---------------------------------------------------------------------------
# Derived Quantities (computed from above, do not edit directly)
# ---------------------------------------------------------------------------

TIP_CHORD = ROOT_CHORD * TAPER_RATIO
MID_CHORD = ROOT_CHORD * MID_CHORD_RATIO
MID_Y = MID_SPAN_FRACTION * SEMI_SPAN
# Wing area: inner trapezoid (root→mid) + outer trapezoid (mid→tip), both wings
WING_AREA = ((ROOT_CHORD + MID_CHORD) / 2 * MID_Y +
             (MID_CHORD + TIP_CHORD) / 2 * (SEMI_SPAN - MID_Y)) * 2
MEAN_CHORD = WING_AREA / (2 * SEMI_SPAN)
ASPECT_RATIO = (2 * SEMI_SPAN) ** 2 / WING_AREA
FLAP_PERIOD = 1.0 / FLAP_FREQUENCY
REYNOLDS_NUMBER = FLIGHT_SPEED * MEAN_CHORD / KINEMATIC_VISCOSITY
TIP_EXCURSION = 2 * SEMI_SPAN * math.sin(math.radians(FLAP_AMPLITUDE))
STROUHAL_NUMBER = FLAP_FREQUENCY * TIP_EXCURSION / FLIGHT_SPEED
REDUCED_FREQUENCY = math.pi * FLAP_FREQUENCY * MEAN_CHORD / FLIGHT_SPEED
