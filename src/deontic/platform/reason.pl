%%% Fast DL(d) reasoner — WORKLIST algorithm over INTERNED
%%% integer literal-ids (an integer-id interning of literals).
%%%
%%% Every literal is interned to a small integer ONCE (term_hash computed once,
%%% at intern time); all subsequent indexing — status, rule-by-head, rule-by-
%%% body-occurrence, the worklist, complements — is keyed on that integer, which
%%% SWI first-argument-indexes perfectly. This removes the repeated term_hash of
%%% list-structured literals that dominated the per-probe constant.
%%%
%%% Algorithm = the standard DL(d) fixed-point procedure: per-rule body counters
%%% (mm_pend/mm_disc) maintained incrementally, only affected literals re-examined.
%%% It reaches the same least fixpoint as the textbook definition, so the proof
%%% tags it assigns are identical to a naive evaluation.
%%% Exports (defp Lit)/(dft Lit V) into the status space.
%%%
%%% Contract: mm_reason(GroundSp, TheorySp, StatSp, true), after grounding.

:- dynamic mm_idlit/2, mm_litid/3, mm_ulitid/1, mm_compl/2,
           mm_rd/5, mm_rfh/2, mm_rfb/2,
           mm_d/2, mm_dd/2, mm_pend/2, mm_disc/1, mm_sup_i/2, mm_wlq/1.

mm_reason(GS, TS, SS, true) :-
    once(( mm_reason_clear,
           mm_reason_index(GS, TS, SS),
           mm_phase1,
           mm_phase2,
           mm_phase3,
           mm_reason_export(SS) )).

mm_reason_clear :-
    retractall(mm_idlit(_,_)), retractall(mm_litid(_,_,_)), retractall(mm_ulitid(_)),
    retractall(mm_compl(_,_)), retractall(mm_rd(_,_,_,_,_)),
    retractall(mm_rfh(_,_)), retractall(mm_rfb(_,_)),
    retractall(mm_d(_,_)), retractall(mm_dd(_,_)),
    retractall(mm_pend(_,_)), retractall(mm_disc(_)),
    retractall(mm_sup_i(_,_)), retractall(mm_wlq(_)),
    nb_setval(mm_idc, 0).

% --- interning: literal <-> integer id (term_hash computed once) -----------
mm_intern(Lit, Id) :-
    term_hash(Lit, H),
    ( mm_litid(H, Lit, Id0) -> Id = Id0
    ; nb_getval(mm_idc, N), Id is N + 1, nb_setval(mm_idc, Id),
      assertz(mm_litid(H, Lit, Id)), assertz(mm_idlit(Id, Lit)),
      mm_lit_compl(Lit, CLit), mm_intern_compl(CLit, Id) ).

% intern the complement and link both ways (so mm_compl is a pure integer hop)
mm_intern_compl(CLit, Id) :-
    term_hash(CLit, CH),
    ( mm_litid(CH, CLit, CId)
    -> assertz(mm_compl(Id, CId)), assertz(mm_compl(CId, Id))
    ;  nb_getval(mm_idc, N), CId is N + 1, nb_setval(mm_idc, CId),
       assertz(mm_litid(CH, CLit, CId)), assertz(mm_idlit(CId, CLit)),
       assertz(mm_compl(Id, CId)), assertz(mm_compl(CId, Id)) ).

mm_lit_compl([lit, pos, M, T, F, A], [lit, neg, M, T, F, A]).
mm_lit_compl([lit, neg, M, T, F, A], [lit, pos, M, T, F, A]).

mm_reason_index(GS, TS, SS) :-
    % universe first, so every occurring literal (and its complement) is interned
    forall(mm_space(SS, [ulit, Lit]),
           ( mm_intern(Lit, Id), ( mm_ulitid(Id) -> true ; assertz(mm_ulitid(Id)) ) )),
    % rules, with head/body interned to ids
    nb_setval(mm_rid, 0),
    forall(mm_space(GS, [grule, L, K, B, H]),
           ( nb_getval(mm_rid, N), N1 is N + 1, nb_setval(mm_rid, N1),
             mm_intern(H, HId), maplist(mm_intern, B, BIds),
             assertz(mm_rd(N1, L, K, BIds, HId)),
             assertz(mm_rfh(HId, N1)),
             forall(member(BId, BIds), assertz(mm_rfb(BId, N1))) )),
    forall(mm_space(TS, [sup, W, L]), assertz(mm_sup_i(W, L))).

mm_space(Space, [Rel|Args]) :- G =.. [Space, Rel | Args], catch(call(G), _, fail).

mm_compl_of(Id, CId) :- ( mm_compl(Id, CId0) -> CId = CId0 ; CId = 0 ). % 0 = absent

mm_def_kind(fact). mm_def_kind(strict).
mm_sd_kind(fact). mm_sd_kind(strict). mm_sd_kind(defeasible).

% --- status (all integer-keyed) ------------------------------------------
mm_defp(Id)     :- mm_d(Id, true).
mm_d_known(Id)  :- mm_d(Id, _).
mm_set_d(Id, V) :- ( mm_d(Id, _) -> true ; assertz(mm_d(Id, V)) ).

mm_dft(Id, V)    :- ( mm_dd(Id, V0) -> V = V0 ; V = unknown ).
mm_dd_known(Id)  :- mm_dd(Id, _).
mm_set_dd(Id, V) :- ( mm_dd(Id, _) -> true ; assertz(mm_dd(Id, V)) ).

mm_rule_head(Id, Rid, L, K, B) :- mm_rfh(Id, Rid), mm_rd(Rid, L, K, B, Id).
mm_applicable(Rid) :- mm_pend(Rid, 0), \+ mm_disc(Rid).

% =====================================================================
% Phase 1: definite provability (strict rules)
% =====================================================================
mm_phase1 :-
    retractall(mm_pend(_,_)), retractall(mm_disc(_)), retractall(mm_wlq(_)),
    forall(( mm_rd(Rid, _, strict, B, _), length(B, N) ), assertz(mm_pend(Rid, N))),
    forall(( mm_rd(_, _, fact, _, H) ), mm_d1_set(H, true)),
    forall(( mm_ulitid(Q), \+ mm_d_known(Q),
             \+ mm_rule_head(Q, _, _, strict, _),
             \+ mm_rule_head(Q, _, _, fact, _) ),
           mm_d1_set(Q, false)),
    mm_d1_drain.

mm_d1_set(Q, V) :- ( \+ mm_ulitid(Q) -> true ; mm_d_known(Q) -> true
                   ; mm_set_d(Q, V), assertz(mm_wlq(Q-V)) ).

mm_d1_drain :-
    ( retract(mm_wlq(Q-Proved))
    -> forall(( mm_rfb(Q, Rid), mm_rd(Rid, _, strict, _, _) ), mm_d1_update(Rid, Proved)),
       mm_d1_drain
    ;  true ).

mm_d1_update(Rid, true) :-
    ( mm_disc(Rid) -> true
    ; retract(mm_pend(Rid, N)), N1 is N - 1, assertz(mm_pend(Rid, N1)),
      ( N1 =:= 0 -> mm_rd(Rid, _, _, _, H), mm_d1_set(H, true) ; true ) ).
mm_d1_update(Rid, false) :-
    ( mm_disc(Rid) -> true ; assertz(mm_disc(Rid)) ),
    mm_rd(Rid, _, _, _, H),
    ( mm_d_known(H) -> true
    ; ( \+ ( mm_rule_head(H, R2, _, strict, _), \+ mm_disc(R2) ) -> mm_d1_set(H, false) ; true ) ).

% =====================================================================
% Phase 2: defeasible provability (all rules)
% =====================================================================
mm_phase2 :-
    retractall(mm_pend(_,_)), retractall(mm_disc(_)), retractall(mm_wlq(_)),
    forall(( mm_rd(Rid, _, _, B, _), length(B, N) ), assertz(mm_pend(Rid, N))),
    forall(( mm_ulitid(Q), mm_defp(Q) ),
           ( mm_compl_of(Q, NQ),
             ( mm_defp(NQ) -> mm_d2_set(Q, false) ; mm_d2_set(Q, true) ) )),
    forall(( mm_ulitid(Q), \+ mm_dd_known(Q), mm_d(Q, false), \+ mm_has_sd(Q) ),
           mm_d2_set(Q, false)),
    forall(( mm_rd(_, _, K, [], H), mm_sd_kind(K) ), mm_try_pd(H)),
    mm_d2_drain.

mm_has_sd(Q) :- mm_rule_head(Q, _, _, K, _), mm_sd_kind(K), !.

mm_d2_set(Q, V) :- ( \+ mm_ulitid(Q) -> true ; mm_dd_known(Q) -> true
                   ; mm_set_dd(Q, V), assertz(mm_wlq(Q-V)) ).

mm_d2_drain :-
    ( retract(mm_wlq(Q-Proved)) -> mm_d2_propagate(Q, Proved), mm_d2_drain ; true ).

mm_d2_propagate(Q, Proved) :-
    forall(mm_rfb(Q, Rid), mm_d2_count(Rid, Proved)),
    ( Proved == true -> mm_d2_on_pos(Q) ; mm_d2_on_neg(Q) ).

mm_d2_count(Rid, true) :-
    ( mm_disc(Rid) -> true ; retract(mm_pend(Rid, N)), N1 is N - 1, assertz(mm_pend(Rid, N1)) ).
mm_d2_count(Rid, false) :-
    ( mm_disc(Rid) -> true ; assertz(mm_disc(Rid)) ).

mm_d2_on_pos(Q) :-
    forall(( mm_rfb(Q, Rid), mm_applicable(Rid), mm_rd(Rid, _, K, _, H) ),
           ( mm_compl_of(H, NH),
             ( mm_sd_kind(K) -> mm_try_pd(H), mm_try_pd(NH), mm_try_nd(NH)
             ;                  mm_try_pd(NH), mm_try_nd(NH) ) )),
    mm_compl_of(Q, NQ), mm_try_nd(NQ).

mm_d2_on_neg(Q) :-
    forall(( mm_rfb(Q, Rid), mm_rd(Rid, _, _, _, H) ),
           ( mm_try_nd(H), mm_compl_of(H, NH), mm_try_pd(NH) )),
    mm_compl_of(Q, NQ), mm_try_pd(NQ).

% --- try-prove a literal defeasibly ---
mm_try_pd(Q) :-
    ( \+ mm_ulitid(Q) -> true
    ; mm_dd_known(Q) -> true
    ; \+ mm_pd_has_applicable(Q) -> true
    ; mm_compl_of(Q, NQ), mm_defp(NQ) -> true        % (2): ~q must NOT be +D
    ; mm_pd_attacks_clear(Q) -> mm_d2_set(Q, true)
    ; true ).

mm_pd_has_applicable(Q) :- mm_rule_head(Q, Rid, _, K, _), mm_sd_kind(K), mm_applicable(Rid), !.

% (3): every attacker in R[~q] is discarded, or applicable+nonstrict+beaten.
% Undecided attacker (neither) fails the forall ⇒ wait; re-triggered when it
% resolves (its head's complement is q).
mm_pd_attacks_clear(Q) :-
    mm_compl_of(Q, NQ),
    forall( mm_rule_head(NQ, Rid, Ls, Ks, _),
            ( mm_disc(Rid)
            ; mm_applicable(Rid), Ks \== strict, mm_beaten(Q, Ls) )).

mm_beaten(Q, Ls) :-
    mm_rule_head(Q, Rid, Lt, K, _), mm_sd_kind(K), mm_applicable(Rid), mm_sup_i(Lt, Ls), !.

% --- try-disprove a literal defeasibly ---
mm_try_nd(Q) :-
    ( \+ mm_ulitid(Q) -> true
    ; mm_dd_known(Q) -> true
    ; mm_defp(Q) -> true
    ; mm_compl_of(Q, NQ), mm_defp(NQ) -> mm_d2_set(Q, false)
    ; mm_nd_all_discarded(Q) -> mm_d2_set(Q, false)
    ; mm_nd_unbeatable(Q) -> mm_d2_set(Q, false)
    ; true ).

mm_nd_all_discarded(Q) :-
    \+ ( mm_rule_head(Q, Rid, _, K, _), mm_sd_kind(K), \+ mm_disc(Rid) ).

mm_nd_unbeatable(Q) :-
    mm_compl_of(Q, NQ),
    mm_rule_head(NQ, Rid, Ls, Ks, _), mm_applicable(Rid),
    ( Ks == strict -> true
    ; \+ mm_nd_defender_undecided(Q, Ls), mm_nd_defenders_fail(Q, Ls) ), !.

mm_nd_defender_undecided(Q, Ls) :-
    mm_rule_head(Q, Rid, Lt, K, _), mm_sd_kind(K),
    \+ mm_disc(Rid), \+ mm_applicable(Rid), mm_sup_i(Lt, Ls), !.

mm_nd_defenders_fail(Q, Ls) :-
    \+ ( mm_rule_head(Q, Rid, Lt, K, _), mm_sd_kind(K), \+ mm_disc(Rid), mm_sup_i(Lt, Ls) ).

% =====================================================================
% Phase 3: closed-world negatives
% =====================================================================
mm_phase3 :-
    forall(( mm_ulitid(Q), \+ mm_d_known(Q) ), mm_set_d(Q, false)),
    forall(( mm_ulitid(Q), \+ mm_dd_known(Q) ), mm_set_dd(Q, false)).

% =====================================================================
% export status to &st (recover literals from ids)
% =====================================================================
mm_reason_export(SS) :-
    forall(( mm_d(Id, true), mm_idlit(Id, Lit) ),
           ( G =.. [SS, defp, Lit], ( catch(call(G), _, fail) -> true ; assertz(G) ) )),
    forall(( mm_dd(Id, V), mm_idlit(Id, Lit) ),
           ( D =.. [SS, dft, Lit, V], ( catch(call(D), _, fail) -> true ; assertz(D) ) )).

% Fast conclusion enumeration straight from the interned (integer-indexed)
% status — O(universe) + sort, vs a MeTTa collapse over the &st space. The
% interned tables persist until the next mm_reason, so this is valid right
% after reasoning. Returns sorted [Tag, Lit] tuples (pD/nD/pd/nd).
mm_conclusions(Cs) :-
    findall([T, Lit], ( mm_ulitid(Id), mm_idlit(Id, Lit), mm_concl_tag(Id, T) ), Cs0),
    sort(Cs0, Cs).

mm_concl_tag(Id, 'pD') :- mm_d(Id, true).
mm_concl_tag(Id, 'nD') :- mm_d(Id, false).
mm_concl_tag(Id, 'pd') :- mm_dd(Id, true).
mm_concl_tag(Id, 'nd') :- mm_dd(Id, false).
