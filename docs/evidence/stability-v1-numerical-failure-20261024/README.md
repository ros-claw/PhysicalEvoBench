# Numerical failure: all six first-round training jobs

Source `12f8f3b5a4a7e596095a9b4db768685f00a42d57`; 1,352 raw files,
1,200 lossless transition chunks, 3,686,400 actual transitions and 14,892
completed training episodes. Two diagnostic episodes; **zero private validation
and zero heldout evaluation episodes**. All six changed checkpoints remain outside
Git under separate model terms. Five finite-loss private audits passed; the third
continual trajectory's updates 112/113 had infinite value loss and stopped the study.

Read [the interpretation](../../experiments/STABILITY_INTERIM_RESULTS_20261024.md).
`manifest.json` indexes every raw file and its SHA256. `SHA256SUMS.json` covers
the archives and source snapshot. To recompute raw transition values without model
weights, use `scripts/verify_stability_delivery.py --numpy-python <python-with-numpy>`.
A successful data audit reproduces the failure; it does not establish stable learning.
