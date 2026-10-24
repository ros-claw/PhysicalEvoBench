# Separate raw-final-policy diagnosis, registered before primary heldout

This follow-up is motivated by observed private validation rollbacks. The main
confirmation's seed 0 rolled back in rounds 1 and 2, so its prerequisite of at least
two promotions per trajectory cannot be met. **The main stability confirmation
cannot pass. This diagnosis never overrides that negative conclusion.**

The original fixed-budget study continues unchanged. This additional study starts
only after it completes, introducing no extra GPU worker during primary evaluation.
Conditions and the selection rule are committed and registered before primary
heldout results exist. No additional learning update occurs.

Question: do the latest raw learned candidates show independent official-task gain
and what sampled-safety tradeoffs accompany it, even when the retention gate rejects
them? This distinguishes candidate learning from system-level accepted evolution.

Select **round 3's raw continual and raw restart candidate for every trajectory**,
regardless of validation scores or main heldout results. Compare both to the original
checkpoint on **64 fresh paired conditions per trajectory**, three trajectories,
three arms: **576 episodes on 192 unique conditions**. Never select the best checkpoint
or easiest condition. The restart arm here is the latest independent retraining
candidate, not a best-of-three search oracle.

Mass distribution remains 0.8–3.2 kg; same original official lift predicate and
success termination, same common +/-1000 numerical envelope, same pinned Arena.
Four blocks of 16 per trajectory, separate per-policy native processes and GPU
rotation. Record raw actions/states, physical readbacks, checkpoint hashes,
reservation ledgers and process codes; independently audit all 576 outcomes and
paired initial states/observations/velocities. Freeze all nine model assignments
before the first diagnostic launch.

Exclude prior published/registered RNG seeds and every seed in the entire main
registration. Keep all diagnostic conditions, including failures. No test or
diagnostic feedback reaches a learner, promotion gate or future training step.

Report every trajectory's raw success counts. Report paired condition-bootstrap
intervals conditional on these fixed learned trajectories for raw continual vs
original, raw restart vs original, and raw continual vs latest raw restart;
10,000 draws, RNG 20261024, Bonferroni alpha=0.05/3. These are diagnostic comparisons,
not proof of stable evolution or superiority to the best possible restart search.
Report the same sampled count/normalized count/per-joint maximum-depth comparisons
and complete safety metrics. A success-rate gain with rejected safety or retention
gates remains an unaccepted candidate, never a retroactive promotion.

This study adds **576 separately accounted evaluation episodes**, zero training
transitions, and zero changes to the 4,610-episode primary registration or its
predeclared decisions. Publish it alongside, not pooled with, the failed main
confirmation. Any positive diagnostic result must retain this distinction.
