# Bounded skill graph schema v1 (frozen before S physics)

Canonical examples: `configs/core/initial_lift_program.json` and
`configs/core/initial_place_program.json`; parser: `physicalevobench/core/program.py`.
Top-level keys exactly `schema`, `start`, `max_retries`, `nodes`; schema is
`core-skill-graph-1`. One to16 uniquely named nodes, defined entry and edges.
Node keys exactly: `id,target,gripper,guard,tolerance,dwell_s,minimum_s,timeout_s,
next,timeout,mode,offset_m`. No expressions are executed as Python.

Public targets: object_above, object_grasp, anchor, probe, goal_offset,
lift_initial, place_above, place_lower, place_retreat, retreat_anchor.
Guards: pose (position plus orientation), bilateral (two paired normal contacts
and nonempty aperture), follow (object lift and relative drift), object_goal,
elapsed, always. `next` and `timeout` are explicit branch edges. Pose tolerance
0.005–0.06m, guard dwell0.02–0.50s, minimum wait0–1s, node timeout0.1–20s,
vertical offset0–0.15m. Maximum2 recovery entries and64 inter-node transitions;
global task horizon always bounds self-loops. Unknown fields/NaN/dangling edges
are rejected. `mode` chooses the shared executor's existing integral-active phase;
this cannot change gain, actuators or target envelope.

Initial S graphs are transparent executable starting programs, not a claimed
independently calibrated S baseline. P retains the exact existing v2 state machine.
S task scores must be checked physically; CPU guard tests do not prove reachability.
Participant identity and the whole program/memory enter the frozen artifact hash.
