# Participant protocol v1

Generic participants receive one JSON request on stdin and return one JSON tool
call on stdout. They need no ROSClaw import. Supported tools are `propose` (validated
artifact), `run_trial` (candidate content hash and opaque training handle) and
`freeze` (known hash and bounded persistent memory). Evaluator allocates paths;
participant cannot choose a filesystem destination. No heldout tool exists.

Each training request includes common initial ability, editable schema, remaining
budgets and previous public tool responses. Feedback contains task outcomes, public
state trajectories/diagnostics and costs; it excludes mass/seed/private split metadata.
Frozen artifacts bind participant identity, program, memory, initial ability, public
interface, shared executor, task and scoring versions. Only the artifact is loaded
in a new testing instance; online transient state is discarded after each episode.

Illegal calls and model timeouts consume declared computational budget. Every
physical reservation is persisted before launch. No task-failure retry exemptions.
Independent evaluator owns physical scoring. The pilot compares P only if using
ReferenceSkill; a P artifact is not an S program. All methods within a comparison
have identical editable space, initial execution capability and online budget.

The local CLI transport disables shell, search and optional MCP configuration,
records actual model events/usage, and starts a fresh ephemeral session for each
request, passing only serialized training context. It remains a trusted participant
transport rather than an adversarial access-control guarantee. External providers
may implement the same stdin/stdout contract; public examples must not require
access to the developer's account or credentials.
