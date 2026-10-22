# Self-adaptation confirmation: protocol fixed before new physics

This is a prospective extension of v0.1.0, not a reinterpretation of its two runs.
The existing 20261021 conditions are development data and never contribute new test scores.
The config, implementation and this plan must be committed before launching any new episode.
No outcome-dependent extra seeds, stopping, retuning, or exclusion is allowed. Infrastructure
failure invalidates the affected execution and remains recorded; it is never a robot failure.

## Claim and interventions

We test whether training-feedback-driven **bounded action-gain search** yields a retained
skill that improves independent physical lift performance. This is adaptation of a frozen
controller through a scalar wrapper, not weight learning, autonomous new-skill invention,
or proof of general self-evolution. Mass range, official task success, timeout, state-based
observations, checkpoint, action semantics and simulator remain those of v0.1.0.

Three new protocol seeds in `configs/confirmation.yaml` independently generate eight train,
eight validation and 24 heldout conditions each. Conditions and episode seeds are disjoint
between splits and protocol seeds, and checked against all prior committed episode seeds.
Training masses evenly span the fixed interval. Test masses are sampled uniformly. Per seed:

- Frozen baseline and identity replay: identical hashed original skill; replay estimates
  stochastic physics variation. They have no adaptation cost and separate test rollouts.
- Feedback search: evaluate original plus three proposals, eight train episodes each.
  Proposal 1 is gain 0.90, proposal 2 is 1.10. Proposal 3 uses ONLY training successes:
  extend to 0.85/1.15 if the better side strictly beats original; otherwise refine that side
  to 0.95/1.05. Ties prefer the lower side. Pick by training successes, preferring original
  on ties, then smaller gain change. All requests/responses are serialized child processes.
- Budget-matched random search: sample three gains without replacement from the same
  predeclared six-value grid, independently of outcomes; choose by the exact same training
  selection rule. Both searches have 32 charged train episodes and 16 charged validation
  episodes. Shared original rollouts are physically executed once and charged to each agent;
  physical and algorithmic budgets are reported separately.

Both candidate jobs within each of the three rounds and every paired validation/test block randomize
agent execution order. Train candidates share paired conditions with original. Validation
compares each train-selected candidate to original on eight new conditions. Promote only
with strictly more successes and no increase in total sampled joint-limit violations;
otherwise retain original. Validation is a trusted gate, never a proposal input.
Freeze all four test skills before running ANY test episode in that seed, and terminate
proposal processes. Four arms run once per condition in balanced, randomized cyclic order,
including both identity arms even if a search rolls back. No test feedback is provided to
an updater, and no test outcome changes the remaining seeds' policies or plan.

## Fixed budget, analysis and interpretation

Each seed uses 56 physical train + 24 validation + 96 test = 176 episodes; three seeds use
528 episodes, including 72 distinct heldout conditions, four physical rollouts per condition.
All raw actions, states, masses, official scores, per-episode skill hashes, proposal history,
reserved budgets, order and provenance are retained. Existing workers and upstream stay
unchanged. No mock/synthetic rollout contributes a score.

Three predeclared comparisons: feedback vs frozen, feedback vs identity replay, feedback
vs budget-matched random. Report paired wins/losses, absolute success-rate difference,
stratified paired-condition bootstrap 95% intervals (10,000 draws), and exact one-sided
binomial/McNemar p-values on discordant pairs, with Holm correction across the three tests.
Formula: sum(comb(wins+losses,k), k=wins..wins+losses)/2**(wins+losses); p=1 for no discordance.
Reference: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html

These condition-level intervals/tests are conditional on three learned skills, not a
well-powered estimate over all possible learning seeds. Always report per-seed outcomes.
A **bounded positive confirmation** requires ALL: genuinely changed retained control in at
least two seeds; strictly positive feedback-minus-frozen success count in EACH seed;
all three corrected p-values <= .05 and all three bootstrap lower bounds > 0; zero invalid
actions; feedback test joint-limit samples no greater than frozen. Otherwise the declared
claim is NOT CONFIRMED, including if power is insufficient. No positive claim will be rescued
by pooling old data, dropping a failed seed, reporting only training/validation, redefining
success, widening gain limits, or adding outcome-dependent trials. Random search can improve
without proving that feedback-directed proposals helped. Identity replay can differ despite
no learning. Collisions remain not_measured, so no complete safety claim is possible.

Tests and independent artifact audit must verify isolation, actual gain execution, mass
readback, matching initial states, budget reconciliation, frozen skill identity and official
outcome consistency. Publish full positive or negative results in a feature PR; preserve
v0.1.0 and its historical evidence. Larger search spaces or additional studies require a
new preregistration and fresh heldout conditions, never retroactive tuning of this study.
