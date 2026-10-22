# Confirmation evidence, 2026-10-22

The preregistered claim was NOT_CONFIRMED. Both searches rolled back in every seed;
all four final arms used the same original skill. Differences between their test
scores are replay variation, not algorithmic improvement or degradation.

These archives contain 528 real completed episodes and 72 distinct heldout conditions.
No checkpoint weights or runtime environment is included. Each archive preserves its
seed directory and all JSON action/state traces, official scores, skills and logs.
The zero-episode HDF5 startup failure and same-condition retry are retained separately.
The initial supervisor returned nonzero for that startup attempt; retry-process.json
records its successful replacement. Nothing is silently excluded from robot scores.

From this directory, verify and extract into a fresh destination:

```bash
sha256sum -c SHA256SUMS
mkdir replay
cp *.json replay/
cp -r startup-failures replay/
for archive in seed-*.tar.gz; do tar -xzf "$archive" -C replay; done
# Run from the PhysicalEvoBench project (current confirmation branch):
uv run python -m physicalevobench.evaluation.confirmation_audit --study-dir /absolute/path/to/replay
```

The delivered archives were independently extracted and reaudited: all 528 episodes
passed and every recomputed metric matched. See delivery-verification.json.
Physical executions used preregistered code commit 8135a26; later changes strengthen
artifact audits/reporting and isolate recorder output paths without altering scores.
The original v0.1.0 release and its earlier evidence remain historical records.
