# Two distinct metric calibrations, 48 actual episodes

The full-horizon low-speed holding calibration **FAILED**: original checkpoint
12/12 instantaneous reaches, 0/12 holding; open-gripper 0/12 on both.
The v2 confirmation was therefore NOT_RUN.

The separately preregistered official-success calibration **PASSED**: original
12/12 official successes, open-gripper 0/12, independent policy processes with
GPU 2/3 crossed. Holding is NOT_MEASURED after official success termination.
No learning update occurred in either calibration. Neither is formal confirmation.

Both raw datasets, logs, source snapshots and SHA256 manifests are included.
`scripts/verify_stability_delivery.py` recomputes both outcomes, including the
failed calibration, from fresh extraction. Read
[the interpretation](../../experiments/STABILITY_INTERIM_RESULTS_20261024.md).
