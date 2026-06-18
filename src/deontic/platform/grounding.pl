%%% Fast Datalog grounding (replaces the naive MeTTa fixpoint).
%%%
%%% The naive bottom-up grounding in ground.metta re-grounds every rule each
%%% pass and dedups with an O(existing) space scan, so transitive closure goes
%%% O(N^4) (anc100 ~ 36s). This computes the SAME ground instances by:
%%%   1. computing the Herbrand base ONCE with a TABLED least-fixpoint (mm_hb/1);
%%%   2. MATERIALIZING it into mm_hbf/5, keyed on the literal's functor so SWI
%%%      first-argument indexing makes body joins O(1) per probe (the list
%%%      representation [lit,...] is opaque to indexing, hence the projection);
%%%   3. emitting instances by indexed join, with term_hash O(1) dedup.
%%% Semantics are identical to the naive ground.metta fixpoint — same set of
%%% ground rule instances, just computed far more cheaply.
%%%
%%% Contract: mm_ground(TheorySp, GroundSp, HerbSp, StatSp, true), called AFTER
%%% the plan is ingested. The space anchors are stashed in module globals so the tabled
%%% mm_hb/1 keys only on the literal (avoids per-call-pattern table variants).

:- dynamic mm_seen_g/1, mm_hbf/5, mm_g_ts/1, mm_g_hs/1.
% incremental (append-only) grounding state — kept alive between delta calls:
%   mm_rule_done/1  term_hash of a rule already joined against the base
%   mm_delta/5      current frontier of new base atoms (semi-naive)
%   mm_newdelta/5   atoms derived this round (next frontier)
:- dynamic mm_rule_done/1, mm_delta/5, mm_newdelta/5.

% --- tabled Herbrand base (least fixpoint over the theory's rules) ---------
:- table mm_hb/1.
mm_hb(Lit)  :- mm_g_hs(HS), mm_call_space(HS, [ha, Lit]).        % ground seeds
mm_hb(Head) :- mm_g_ts(TS), mm_call_space(TS, [rule, _L, _K, Body, Head]),
               mm_hb_body(Body), ground(Head).

mm_call_space(Space, [Rel|Args]) :- G =.. [Space, Rel | Args], catch(call(G), _, fail).

mm_hb_body([]).
mm_hb_body([I|R]) :- mm_hb_item(I), mm_hb_body(R).

% Interval-variable temporal: bind the handle to a temporal variant in the base.
mm_hb_item([lit, S, M, T, F, A]) :- var(T), !, mm_hb([lit, S, M, T, F, A]).
% Base-family wildcard: a non-temporal body lit matches any temporal variant.
mm_hb_item([lit, S, M, none, F, A]) :- !, mm_hb([lit, S, M, _T, F, A]).
mm_hb_item([lit, S, M, [iv, Ts, Te], F, A]) :- !, mm_hb([lit, S, M, [iv, Ts, Te], F, A]).
mm_hb_item([acmp, Op, L, R]) :- !, mm_acmp(Op, L, R, true).
mm_hb_item([tcmp, Rel, L, R]) :- !, mm_tcmp(Rel, L, R, true).
mm_hb_item([abind, V, Ax]) :- !, mm_ax_eval(Ax, V).

% --- driver ---------------------------------------------------------------
% Default (one-shot path): full from-scratch ground, base dropped at the end.
mm_ground(TS, GS, HS, SS, true) :- once(mm_ground_run(TS, GS, HS, SS, drop)).
% Incremental session init: same full ground, but KEEP the materialized base
% (mm_hbf), per-rule completion marks, and dedup set alive for later deltas.
mm_ground_incr_init(TS, GS, HS, SS, true) :- once(mm_ground_run(TS, GS, HS, SS, keep)).

mm_ground_run(TS, GS, HS, SS, Mode) :-
    retractall(mm_seen_g(_)), retractall(mm_hbf(_,_,_,_,_)),
    retractall(mm_rule_done(_)), retractall(mm_delta(_,_,_,_,_)),
    retractall(mm_newdelta(_,_,_,_,_)),
    retractall(mm_g_ts(_)), retractall(mm_g_hs(_)),
    assertz(mm_g_ts(TS)), assertz(mm_g_hs(HS)),
    abolish_all_tables,
    % 1. compute the tabled Herbrand base once, materialize functor-indexed
    forall(mm_hb([lit, S, M, T, F, A]),
           ( mm_hbf(F, A, S, M, T) -> true ; assertz(mm_hbf(F, A, S, M, T)) )),
    abolish_all_tables,
    % 2. seed dedup with grules already emitted by mm_add_rule (ground rules)
    forall(mm_call_space(GS, [grule, L0, K0, B0, H0]),
           ( term_hash(g(L0, K0, B0, H0), GH0),
             ( mm_seen_g(GH0) -> true ; assertz(mm_seen_g(GH0)) ) )),
    % 3. emit every satisfiable instance by indexed join over mm_hbf
    forall(( mm_call_space(TS, [rule, L, K, Body, Head]),
             ( Mode == keep -> mm_mark_rule(L, K, Body, Head) ; true ),
             mm_inst_body(Body, GBody0),
             exclude(==(dropped), GBody0, GBody),
             ground([GBody, Head]) ),
           mm_store_grule(GS, HS, SS, L, K, GBody, Head)),
    ( Mode == drop -> retractall(mm_hbf(_,_,_,_,_)) ; true ).

% mark a rule as already joined against the base (so deltas know it is "old").
% Rules carry variables (?x), so a variant-stable ground hash is needed —
% term_hash/2 leaves the hash UNBOUND on non-ground terms (which would make every
% rule compare equal). copy_term+numbervars grounds it up to variable renaming.
mm_rule_hash(L, K, B, H, RH) :-
    copy_term(r(L, K, B, H), T), numbervars(T, 0, _), term_hash(T, RH).
mm_mark_rule(L, K, B, H) :-
    mm_rule_hash(L, K, B, H, RH), ( mm_rule_done(RH) -> true ; assertz(mm_rule_done(RH)) ).
mm_rule_old(L, K, B, H) :- mm_rule_hash(L, K, B, H, RH), mm_rule_done(RH).

% --- incremental (semi-naive, add-only) delta grounding --------------------
% After new facts/rules are appended to the theory + herb seeds, derive ONLY
% the new closure: new seed atoms form the frontier; brand-new rules are joined
% against the full base; existing rules are re-joined only where >=1 body literal
% comes from the frontier. Pure assertz — the base is never retracted.
mm_ground_delta(TS, GS, HS, SS, true) :-
    once(( retractall(mm_delta(_,_,_,_,_)), retractall(mm_newdelta(_,_,_,_,_)),
           % dedup against grules mm_add_rule already emitted for appended ground
           % facts (else the new-rule join re-emits them as duplicates)
           forall(mm_call_space(GS, [grule, L0, K0, B0, H0]),
                  ( term_hash(g(L0, K0, B0, H0), GH0),
                    ( mm_seen_g(GH0) -> true ; assertz(mm_seen_g(GH0)) ) )),
           % new herb seeds (appended facts) -> base + initial frontier
           forall(( mm_call_space(HS, [ha, [lit, S, M, T, F, A]]),
                    \+ mm_hbf(F, A, S, M, T) ),
                  ( assertz(mm_hbf(F, A, S, M, T)), mm_add_delta(F, A, S, M, T) )),
           mm_delta_loop(TS, GS, HS, SS) )).

mm_add_delta(F, A, S, M, T) :- ( mm_delta(F, A, S, M, T) -> true ; assertz(mm_delta(F, A, S, M, T)) ).

mm_delta_loop(TS, GS, HS, SS) :-
    ( ( \+ mm_delta(_,_,_,_,_), \+ mm_new_rule_exists(TS) ) -> true
    ; retractall(mm_newdelta(_,_,_,_,_)),
      % brand-new rules: full join against the whole base
      forall(( mm_call_space(TS, [rule, L, K, B, H]), \+ mm_rule_old(L, K, B, H),
               mm_mark_rule(L, K, B, H),
               mm_inst_body(B, GB0), exclude(==(dropped), GB0, GB), ground([GB, H]) ),
             mm_store_grule_d(GS, HS, SS, L, K, GB, H)),
      % existing rules: semi-naive join (>=1 body literal from the frontier)
      forall(( mm_call_space(TS, [rule, L, K, B, H]), mm_rule_old(L, K, B, H),
               mm_inst_body_d(B, GB0, true), exclude(==(dropped), GB0, GB), ground([GB, H]) ),
             mm_store_grule_d(GS, HS, SS, L, K, GB, H)),
      % swap frontier := newly derived atoms
      retractall(mm_delta(_,_,_,_,_)),
      forall(mm_newdelta(F, A, S, M, T), mm_add_delta(F, A, S, M, T)),
      retractall(mm_newdelta(_,_,_,_,_)),
      mm_delta_loop(TS, GS, HS, SS) ).

mm_new_rule_exists(TS) :- mm_call_space(TS, [rule, L, K, B, H]), \+ mm_rule_old(L, K, B, H), !.

% body instantiation that also reports whether any literal came from the frontier.
mm_inst_body_d([], [], false).
mm_inst_body_d([I|R], [GI|GR], Used) :-
    mm_inst_item_d(I, GI, U1), mm_inst_body_d(R, GR, U2),
    ( U1 == true -> Used = true ; Used = U2 ).
mm_inst_item_d([lit, S, M, T, F, A], [lit, S, M, T, F, A], U) :- var(T), !,
    mm_hbf(F, A, S, M, T), ( mm_delta(F, A, S, M, T) -> U = true ; U = false ).
mm_inst_item_d([lit, S, M, none, F, A], [lit, S, M, T, F, A], U) :- !,
    mm_hbf(F, A, S, M, T), ( mm_delta(F, A, S, M, T) -> U = true ; U = false ).
mm_inst_item_d([lit, S, M, [iv, Ts, Te], F, A], [lit, S, M, [iv, Ts, Te], F, A], U) :- !,
    mm_hbf(F, A, S, M, [iv, Ts, Te]),
    ( mm_delta(F, A, S, M, [iv, Ts, Te]) -> U = true ; U = false ).
mm_inst_item_d([acmp, Op, L, R], dropped, false) :- !, mm_acmp(Op, L, R, true).
mm_inst_item_d([tcmp, Rel, L, R], dropped, false) :- !, mm_tcmp(Rel, L, R, true).
mm_inst_item_d([abind, V, Ax], dropped, false) :- !, mm_ax_eval(Ax, V).

% store a delta grule; a newly derivable head joins the base and next frontier.
mm_store_grule_d(GS, HS, SS, L, K, B, H) :-
    term_hash(g(L, K, B, H), GH),
    ( mm_seen_g(GH) -> true
    ; assertz(mm_seen_g(GH)),
      St =.. [GS, grule, L, K, B, H], assertz(St),
      mm_store_atom(HS, [ha, H]),
      mm_store_atom(SS, [ulit, H]),
      forall(member(Lit, B), mm_store_atom(SS, [ulit, Lit])),
      H = [lit, S, M, T, F, A],
      ( mm_hbf(F, A, S, M, T) -> true ; assertz(mm_hbf(F, A, S, M, T)) ),
      ( mm_newdelta(F, A, S, M, T) -> true ; assertz(mm_newdelta(F, A, S, M, T)) ) ).

% Instantiate a body against the materialized base (mm_hbf is functor-indexed,
% so F bound => fast probe), dropping constraints (they fold out of the body).
mm_inst_body([], []).
mm_inst_body([I|R], [GI|GR]) :- mm_inst_item(I, GI), mm_inst_body(R, GR).

mm_inst_item([lit, S, M, T, F, A], [lit, S, M, T, F, A]) :- var(T), !,
    mm_hbf(F, A, S, M, T).                              % bind interval handle from base
mm_inst_item([lit, S, M, none, F, A], [lit, S, M, T, F, A]) :- !,
    mm_hbf(F, A, S, M, T).                              % concrete temporal from base
mm_inst_item([lit, S, M, [iv, Ts, Te], F, A], [lit, S, M, [iv, Ts, Te], F, A]) :- !,
    mm_hbf(F, A, S, M, [iv, Ts, Te]).                  % match exact interval
mm_inst_item([acmp, Op, L, R], dropped) :- !, mm_acmp(Op, L, R, true).
mm_inst_item([tcmp, Rel, L, R], dropped) :- !, mm_tcmp(Rel, L, R, true).
mm_inst_item([abind, V, Ax], dropped) :- !, mm_ax_eval(Ax, V).

mm_store_grule(GS, HS, SS, L, K, B, H) :-
    term_hash(g(L, K, B, H), GH),
    ( mm_seen_g(GH) -> true
    ; assertz(mm_seen_g(GH)),
      St =.. [GS, grule, L, K, B, H], assertz(St),
      mm_store_atom(HS, [ha, H]),
      mm_store_atom(SS, [ulit, H]),
      forall(member(Lit, B), mm_store_atom(SS, [ulit, Lit])) ).

mm_store_atom(Space, [Rel|Args]) :-
    G =.. [Space, Rel | Args],
    ( catch(call(G), _, fail) -> true ; assertz(G) ).
