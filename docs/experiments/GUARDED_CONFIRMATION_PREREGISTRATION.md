# Guarded adaptation confirmation: conditional prospective plan

**Status: NOT RUN.** The guarded development gate returned rollback (5/16 vs5/16,
joint samples40 vs38). Accordingly, no formal train/validation/test episode was
launched under this plan. Its 696 episodes are a proposed budget, not executed data.
A future invocation requires an independently audited promoted development gate;
any revised development history/cost must be registered before that future study.

Run this study ONLY after the separately registered guarded development validation
promotes an update and its independent audit passes. Otherwise do not launch it.
All previous data (including temporal safety rollback and guarded validation) are
development data. None contributes a heldout score. Publish plan and code before
any formal rollout. No outcome-dependent extra seed, candidate, exclusion or stopping.

## Controller, training and controls

Keep original checkpoint, .8–3.2kg mass distribution, robot, force limits, success
predicate, 50Hz and five-second timeout. Learn only guarded-1 wrapper parameters.
The six allowed candidates are precisely those in GUARDED_EXPLORATION_PLAN.md.
Developer exploration provides a shared family/prior and costs 224 completed
physical episodes (128 temporal +96 guarded development). Report this cost separately
from each algorithm's within-study budget; do not imply discovery was free.

Three new protocol seeds in configs/guarded_confirmation.yaml each generate eight
stratified training, 16 uniform validation and 32 uniform heldout conditions. IDs and
seeds must be disjoint across splits, learning seeds and all published earlier data,
including archived manifests/configs. Neither agent receives true mass or test outcomes.
Each agent gets a serialized JSON training history in short-lived proposal processes.
It evaluates original plus three candidates, eight train episodes each. Both select
maximum training successes, preserving original on ties, then earlier candidate.

Feedback-directed search uses the training-derived prior: trial1 hold10guard10look2,
trial2 hold10guard6; trial3 chooses hold10guard2 if trial1 training successes >= trial2,
otherwise guard6look2. Random search samples three candidates without replacement
from the same six-value family, independent of outcomes. Both select from their own
training feedback and face the same validation gate. This compares full proposal
strategies conditional on development priors, not a pure causal ablation of all feedback.

Validate each train-selected candidate against shared original on 16 paired conditions,
randomizing arm order. Strictly more successes AND no increase in total sampled hard
joint-limit violations is required to promote; otherwise rollback. Freeze final skills
and end proposal processes BEFORE each seed's test. Test original, identity replay,
feedback final and random final once each on 32 new paired conditions, randomized
balanced cyclic order. Execute all seeds regardless of early outcomes. Retain rollback
identity arms and all failed candidates. Infrastructure failures invalidate affected
attempts, never count as robot failures, and remain documented.

## Fixed costs and predeclared inference

Per seed: physical train 56 + validation48 + test128 =232, three seeds696 episodes.
Each search is charged train32 + validation32 + test32; shared original train/validation
is executed once physically but charged to both. Common prior-development cost224 is
additional. There are96 distinct heldout conditions, not384 distinct conditions.

Use the same predeclared statistics as the previous confirmation: paired wins/losses,
exact one-sided discordant-pair binomial p, Holm correction across feedback vs original,
vs identity replay and vs random; stratified paired-condition bootstrap95% intervals
(10,000 draws), and all per-seed results. All inference is conditional on three learned
skills and does not establish universal cross-learning-seed or real-robot generalization.

Retain the earlier strong criterion unchanged: genuine retained control change in at
least two seeds; positive feedback-minus-original success count in EVERY seed; all
three corrected p<=.05 and all three bootstrap lower bounds>0; zero invalid actions;
feedback test joint-limit sample total<=original. Only then report bounded strong
confirmation. Collisions are unmeasured; no complete safety claim is possible.

Also report a separately named, narrower **task-specific retained adaptation signal**
if the same retained-change/per-seed/safety checks pass and the corrected comparisons
against original AND identity replay pass, even when random superiority does not.
This is not the earlier strong claim and must never be labeled proof of feedback-specific
self-evolution. Always show random outcomes and whether this stronger comparison failed.
A successful data-selected controller need not demonstrate an advantage of its search
algorithm. Degenerate intervals for identical retained policies are replay statistics,
not proof of equivalence. No claim of model-weight learning is made.

Audit original outcomes, actual temporal/guard actions, proprioception, joint counts,
physical mass, paired initial states, whitelist feedback, all proposals/selection,
reserved budgets, frozen skills and source hashes. Preserve full raw evidence and
reproduce audit/metrics after independently extracting delivered archives.
