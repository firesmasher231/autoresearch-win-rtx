# AutoOrnithopter — Agent Instructions

Read `program.md` for full instructions, then start the autonomous research loop immediately.

Quick summary:
1. Edit `design.py` to try a new wing design (must stay within PHYSICAL_BOUNDS — see evaluate.py)
2. git commit
3. Run: `uv run simulate.py > run.log 2>&1`
4. Check: `grep "^fitness:\|^mean_lift_N:\|^P_flap_est_W:\|^sim_seconds:" run.log`
5. If fitness improved (higher) → keep. If worse → `git reset --hard HEAD~1`
6. Log to `results.tsv`
7. Sync: `./sync-results.sh`
8. Repeat forever. NEVER STOP.

The goal: maximize `fitness` (propulsive efficiency = thrust per watt of flapping power). Higher = better.
The design MUST produce mean_lift_N >= 0.49 (support 50g) or fitness gets crushed by penalty.
