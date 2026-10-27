# T1 — Pick–Transport–Place (development candidate)

ID `core-place-h20-v2-dev`; 20s proposed horizon, same robot/table/cube and executor.
Target center XY is initial object XY plus (0.12,0.12)m; center Z is0.021m
(the supported cube center height, not the airborne reset height0.055m). All are public.
Require actual lift≥0.05m and horizontal travel≥0.08m, then continuous0.50s within
horizontal0.05m /vertical0.025m of target, speed≤0.10m/s, both finger positions
≥0.035m and EE/object separation≥0.06m. Evaluate actual object, finger and EE states;
a controller return value cannot decide success. Score per control and record
terminal state before reset. Forced-open reference is the degenerate control.

This card is not calibrated evidence. Freeze a final ID/config only after bounded
development; independent confirmation must precede any claim about transfer.
See the registered bounds and stopping rules in CORE_PROTOCOL_20261027.md.
