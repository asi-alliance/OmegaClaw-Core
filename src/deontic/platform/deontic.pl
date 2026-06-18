% Optional Standard Deontic Logic (SDL) inference layer (beyond plain defeasible
% logic).
%
% The base Defeasible Logic carries deontic modes O/P/F on literals but does not
% infer with them. This module adds the Standard Deontic Logic bridges so
% obligations, permissions and prohibitions interact (Governatori's defeasible
% deontic logic). The canonical SDL relationships:
%
%   im p = ob ¬p   ->   F p ≡ O ¬p     (forbidden = obligatory-not)
%   pe p = ¬ob ¬p  ->   O p → P p      ("ought implies may", under the D axiom)
%
% DEFEASIBLE INTERACTION: the equivalences are injected as parallel grules that
% reuse the SOURCE RULE'S LABEL, kind, and body — not fresh strict rules. Because
% the DL(d) engine keys superiority and applicability by rule LABEL, a deontic
% consequence then inherits the source rule's strength and superiorities. So two
% defeasible rules concluding conflicting deontic literals (O p from r1, F p from
% r2) resolve under `prefer r1 r2` exactly like an ordinary p/¬p conflict: F p is
% rewritten to O¬p under r2, O p (r1) attacks O¬p (r2), and r1 > r2 decides it.
% Deontic CONFLICT thus falls out of the normal sign-complement defeat machinery.
%
% Runs to a fixpoint (a bridged head can trigger further bridges) and registers
% new heads in the universe. OPT-IN: the default reason path never calls this, so
% plain defeasible reasoning is left completely untouched.

mm_deontic_bridge(GS, HS, SS, true) :- once(mm_deo_fix(GS, HS, SS)).

mm_deo_fix(GS, HS, SS) :-
    findall(rule(L, OK, B, Head),
      ( mm_deo_q(GS, [grule, L, K, B, H]), mm_deo_rule(K, H, OK, Head),
        \+ mm_deo_q(GS, [grule, L, OK, B, Head]) ),
      New),
    ( New == [] -> true
    ; forall(member(rule(L, OK, B, Head), New), mm_deo_emit(GS, HS, SS, L, OK, B, Head)),
      mm_deo_fix(GS, HS, SS) ).

mm_deo_q(Sp, [R|As]) :- G =.. [Sp, R | As], catch(call(G), _, fail).

% (InKind, Head) -> (OutKind, NewHead). Sign flip = proposition ¬.
%   F p ⊢ O ¬p   ;   O p ⊢ F ¬p   (the F↔O equivalence) ;   O p ⊢ P p   (same kind)
%   STRONG PERMISSION: P p emits a DEFEATER concluding O p, which blocks the
%   contrary prohibition O ¬p (= F p) without proving the obligation — an explicit
%   permission undercuts a defeasible prohibition (beaten only by a superior one).
% F↔O equivalence applies to every kind (so a permission's defeater blocks the
% prohibition in BOTH its F and O¬ forms; terminates via dedup):
mm_deo_rule(K, [lit, S, 'F', T, F, A], K, [lit, Sn, 'O', T, F, A]) :- mm_deo_flip(S, Sn).
mm_deo_rule(K, [lit, S, 'O', T, F, A], K, [lit, Sn, 'F', T, F, A]) :- mm_deo_flip(S, Sn).
% O→P and P→defeater(O) only from genuine (non-defeater) duties:
mm_deo_rule(K, [lit, S, 'O', T, F, A], K, [lit, S, 'P', T, F, A]) :- K \== defeater.
mm_deo_rule(K, [lit, S, 'P', T, F, A], defeater, [lit, S, 'O', T, F, A]) :- K \== defeater.

mm_deo_flip(pos, neg).
mm_deo_flip(neg, pos).

% Inject the equivalent grule under the SAME label/kind/body, and register its
% head (and any body literals) in the universe + Herbrand base for the reasoner.
mm_deo_emit(GS, HS, SS, L, K, B, Head) :-
    ( mm_deo_q(GS, [grule, L, K, B, Head]) -> true
    ; G =.. [GS, grule, L, K, B, Head], assertz(G),
      mm_deo_reg(HS, [ha, Head]),
      mm_deo_reg(SS, [ulit, Head]),
      forall(member(Bl, B), mm_deo_reg(SS, [ulit, Bl])) ).

mm_deo_reg(Sp, [R|As]) :- G =.. [Sp, R | As], ( catch(call(G), _, fail) -> true ; assertz(G) ).

% (compliance/dilemma AND deadline compliance LOGIC now live in idiomatic MeTTa —
%  src/deontic/deontic.metta. This module keeps the grule-level SDL bridge + thin
%  report formatters. Deadline metadata is stored at ingest as [deadlineinfo Sgn
%  Mode F A Type St En Sanc] in &st; the MeTTa layer reads it via match.)

% deadline report formatter. Rows = [[LitWindowStr, Type, Status, Sanc], ...]
mm_print_deadlines2(Now, Rows, true) :-
    once(( with_output_to(string(O), (
             format("Deadline Compliance (now=~w)~n", [Now]),
             format("===========================~n", []),
             ( Rows == [] -> format("  (no deadline obligations)~n", [])
             ; forall(member([L, Type, St, Sanc], Rows),
                 ( ( St == violated, Sanc \== none )
                   -> format("  ~w (~w): ~w  -> sanction OBL ~w~n", [L, Type, St, Sanc])
                   ;  format("  ~w (~w): ~w~n", [L, Type, St]) )) ) )),
           write(O) )).

% --- thin report formatters (LOGIC lives in src/deontic/deontic.metta; these only
%     format pre-computed results, like format/2 over a MeTTa-built list) ---------
mm_print_verdicts(Title, Vs, true) :-
    once(( with_output_to(string(O), (
             format("~w~n", [Title]), string_length(Title, N), forall(between(1, N, _), write("=")), nl,
             ( Vs == [] -> format("  (none)~n", [])
             ; forall(member([L, S], Vs), format("  ~w: ~w~n", [L, S])) ) )),
           write(O) )).

mm_print_dilemmas2(Ls, true) :-
    once(( with_output_to(string(O), (
             format("Deontic Dilemmas~n================~n", []),
             ( Ls == [] -> format("  none~n", [])
             ; forall(member([lit, _, _, T, F, A], Ls),
                 ( mm_lit_str([lit, pos, none, T, F, A], P),
                   format("  dilemma: O ~w vs O ~~~w  (unresolved — add a superiority)~n", [P, P]) )) ) )),
           write(O) )).
