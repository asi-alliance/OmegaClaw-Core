; lib_directive — Defeasible task-coordination, layered on lib_deontic.
;
; Where lib_deontic answers "what defeasibly holds / what is obligated", this
; library turns that same non-monotonic engine into a coordinator for *work*:
; a plan is a defeasible theory whose conclusions describe the live state of a
; set of tasks, and every coordination command is just reasoning over that
; theory. Pure library — it defines vocabulary and queries, registers no agent
; skill, and does not touch the loop.
;
; What it adds on top of the engine, end to end:
;   task extraction — read the conclusion set as task / ready / claimed /
;     blocked / upstream-blocked / completed groups (prefix conventions on
;     literal names), plus agent assignments;
;   next-actions   — the assignments whose task is currently `ready`, with a
;     state-precedence classifier (done > blocked > upstream-blocked >
;     decomposed > in-progress > ready > backlog) feeding status / board /
;     summary views;
;   lifecycle      — claim / unclaim / block / unblock / complete / assert,
;     each an append-only block of facts and defeasible rules that a later
;     re-reason resolves (a counter-action defeats the prior chain, so state
;     transitions are monotone appends with non-monotonic effect), including
;     failure-propagation rules that block downstream tasks;
;   inspection     — full reasoning trace, plan-structure validation
;     (undefined / unreachable literals, consistency), dependency-cycle
;     (deadlock) detection via SCCs of the support graph, and assignment
;     listing;
;   process-mining — recover a defeasible plan from observed event logs: extract
;     per-case event sequences from claims blocks, compute the directly-follows
;     footprint, and learn rules with trace-level support / confidence plus
;     XOR / mutex conflict detection.
;
; Opt-in: load this facade (it pulls in lib_deontic) to get the coordination
; layer. Load order mirrors the dependency chain — core extraction/lifecycle
; first, then mining and inspection that build on it, then the CLI dispatcher.
!(import! &self (library OmegaClaw-Core lib_deontic))
!(import! &self (library OmegaClaw-Core src/directive/directive))
!(import! &self (library OmegaClaw-Core src/directive/mining))
!(import! &self (library OmegaClaw-Core src/directive/inspect))
!(import! &self (library OmegaClaw-Core src/directive/cli))
