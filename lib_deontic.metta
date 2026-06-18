; lib_deontic — Defeasible + Deontic + Temporal logic for OmegaClaw.
;
; A reasoning library, sibling to lib_nal / lib_pln. Where NAL/PLN grade how much
; a fact is believed, this library answers what *defeasibly holds* under
; conflicting rules and what is *obligated / permitted / forbidden* — that is,
; non-monotonic and normative reasoning (Nute's Defeasible Logic + Standard
; Deontic Logic, with Event-Calculus temporal grounding). Pure library: it
; defines vocabulary and inference; it registers no agent skill and does not
; touch the loop.
;
; Theory of operation, end to end:
;   load   — parse a theory (facts; strict -> / defeasible => / defeater ~> rules;
;            superiority) into spaces;
;   ground — instantiate variable rules over the Herbrand base (Datalog join);
;   reason — DL(d) fixpoints produce four provability tags: +D/-D (definite, the
;            monotonic core) and +d/-d (defeasible, ambiguity-blocking);
;   read   — enumerate the tagged conclusion set; the deontic, temporal, and
;            trust analyses all fold over it.
!(import! &self (library OmegaClaw-Core src/deontic/platform/platform))
!(import! &self (library OmegaClaw-Core src/deontic/types))
!(import! &self (library OmegaClaw-Core src/deontic/ground))
!(import! &self (library OmegaClaw-Core src/deontic/reason))
!(import! &self (library OmegaClaw-Core src/deontic/engine))
!(import! &self (library OmegaClaw-Core src/deontic/query))
!(import! &self (library OmegaClaw-Core src/deontic/explain))
!(import! &self (library OmegaClaw-Core src/deontic/trust))
!(import! &self (library OmegaClaw-Core src/deontic/deontic))
!(import! &self (library OmegaClaw-Core src/deontic/eventcalc))
