# PEB-Lift-Mass-v0 protocol (implementation in progress)

Use the normal, unmodified pretrained policy as skill v0 with arm gain 1.0. The candidate
mass interval [0.05, 0.40] kg is a pilot proposal, not a validated benchmark distribution.
Do not freeze formal manifests until a real mass sensitivity pilot has been reviewed.

Separate train, validation and heldout_test by condition ID and seed. Store actual mass
and initial conditions in evaluator-owned manifests. Give proposal agents only typed train
feedback through a serialization boundary. This is an interface boundary, not a secure OS
sandbox against malicious local code.

Reserve physical budgets before launching each rollout, including candidates and validation
comparisons. A simulator crash is INFRA_FAILURE, never a robot task failure. Validation
uses paired conditions and strict positive success-rate improvement, with the threshold fixed
before testing; ties roll back. Rejected candidates leave the incumbent skill hash unchanged.

Freeze checkpoint and final skill hashes before heldout test. Test Frozen and Updated on
the exact same conditions, with at least 16 pairs for the MVP. Test feedback never reaches the
updater. Report raw counts, paired gain and uncertainty without claiming significance from
one smoke run. Feedback-specific superiority additionally requires budget-matched random search.

Sensors not installed must be reported as null/not_measured; no collision or joint-limit
metric is currently implemented. No physical score, candidate promotion or video exists yet.
