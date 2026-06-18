% Plan-inspection renderers — `trace` and `validate` (plan structure).
%
% Both read the loaded theory space (atoms [rule,Label,Kind,Body,Head], [sup,W,L])
% plus the reasoned conclusion list, and emit their Facts:/Rules:/warning lines as
% a STABLE sorted set, so the output is reproducible across runs.
%
% Self-contained apart from the space atom passed in from MeTTa.

% ---- generic space query: Space(Rel, Arg1, ...) ----
mn_q(Space, [Rel|Args]) :- G =.. [Space, Rel | Args], catch(call(G), _, fail).

% literal name = its functor; negation flag from the sign slot.
mn_litname([lit, S, _, _, F, _], S, F).

% ============================================================================
% trace — facts / rules (DFL arrows) / superiorities / positive conclusions
% ============================================================================
mm_print_trace(TheorySp, Concls, true) :-
    once(( with_output_to(string(Out), mn_trace(TheorySp, Concls)), write(Out) )).

mn_trace(TS, Concls) :-
    mn_sep, format("Full Reasoning Trace~n"), mn_sep, nl,
    % Facts:  [label] >> name
    format("Facts:~n"),
    findall(L-N, ( mn_q(TS, [rule, L, fact, _, H]), mn_litname(H, _, N) ), Fs0),
    sort(Fs0, Fs),
    forall(member(L-N, Fs), format("  [~w] >> ~w~n", [L, N])), nl,
    % Rules:  [label] body  arrow  head    (¬ marks negated literals)
    format("Rules:~n"),
    findall(L-Line, ( mn_q(TS, [rule, L, K, B, H]), K \== fact,
                      mn_rule_line(L, K, B, H, Line) ), Rs0),
    sort(Rs0, Rs),
    forall(member(_-Line, Rs), ( write(Line), nl )), nl,
    % Superiorities:  W > L
    findall(W-L, mn_q(TS, [sup, W, L]), Sup0), sort(Sup0, Sups),
    ( Sups == [] -> true
    ; format("Superiorities:~n"),
      forall(member(W-L, Sups), format("  ~w > ~w~n", [W, L])), nl ),
    % Conclusions: positive (+D/+d) only
    format("Conclusions:~n"),
    findall(CL, ( member([Tag, Lit], Concls), mn_pos_sym(Tag, Sym),
                  mn_litname(Lit, S, N), mn_signed(S, N, SN),
                  format(atom(CL), "  ~w ~w", [Sym, SN]) ), Cs0),
    sort(Cs0, Cs),
    forall(member(C, Cs), ( write(C), nl )), nl.

mn_sep :- forall(between(1, 63, _), write("=")), nl.

mn_pos_sym(pD, "+D"). mn_pos_sym(pd, "+d").

mn_signed(neg, N, S) :- !, atom_concat('~', N, S).
mn_signed(_, N, N).

mn_arrow(strict, "->"). mn_arrow(defeasible, "=>"). mn_arrow(defeater, "~>").

mn_rule_line(L, K, Body, Head, Line) :-
    mn_lit_names(Body, BNs), atomic_list_concat(BNs, ', ', BStr),
    ( is_list(Head) , Head = [lit|_] -> mn_lit_names([Head], HNs)
    ; mn_lit_names(Head, HNs) ),
    atomic_list_concat(HNs, ', ', HStr),
    mn_arrow(K, Arr),
    format(atom(Line), "  [~w] ~w ~w ~w", [L, BStr, Arr, HStr]).

% names of the literal body/head items (¬ for negated); non-lit items skipped.
mn_lit_names([], []).
mn_lit_names([It|Its], [Nm|Ns]) :- mn_litname(It, S, N), !, mn_signed_neg(S, N, Nm), mn_lit_names(Its, Ns).
mn_lit_names([_|Its], Ns) :- mn_lit_names(Its, Ns).
mn_signed_neg(neg, N, M) :- !, atom_concat('¬', N, M).
mn_signed_neg(_, N, N).

% ============================================================================
% validate — plan structure checks (default = non-strict)
% ============================================================================
mm_print_plan_validate(TheorySp, Concls, FmtStr, Strict, Valid) :-
    once(( mn_validate(TheorySp, Concls, FmtStr, Strict, Valid, Out), write(Out) )).

mn_validate(TS, Concls, FmtStr, Strict, Valid, Out) :-
    % defined literals: heads of facts + heads of rules
    findall(N, ( mn_q(TS, [rule, _, _, _, H]), mn_litname(H, _, N) ), Def0),
    sort(Def0, Defined),
    % concluded literals: positive conclusions
    findall(N, ( member([Tag, Lit], Concls), mn_pos_sym(Tag, _), mn_litname(Lit, _, N) ), Con0),
    sort(Con0, Concluded),
    % scan non-fact rule bodies for undefined / unreachable literals
    findall(undef(N, L),
      ( mn_q(TS, [rule, L, K, B, _]), K \== fact,
        member(It, B), mn_litname(It, _, N),
        \+ memberchk(N, Defined), \+ mn_lifecycle_lit(N) ),
      Undef0),
    sort(Undef0, Undef),
    findall(unreach(N, L),
      ( mn_q(TS, [rule, L, K, B, _]), K \== fact,
        % rule has some body literal that is neither concluded nor defined
        ( member(X, B), mn_litname(X, _, XN),
          \+ memberchk(XN, Concluded), \+ memberchk(XN, Defined), \+ mn_lifecycle_lit(XN) ),
        member(It, B), mn_litname(It, _, N),
        \+ memberchk(N, Concluded), \+ memberchk(N, Defined), \+ mn_lifecycle_lit(N) ),
      Unr0),
    sort(Unr0, Unreach),
    % consistency: circular superiorities + contradictory definite conclusions
    mn_consistency(TS, Concls, Cons),
    % build warning lines (sorted set; non-strict -> all are warnings, valid=true)
    findall(W, ( member(unreach(N, L), Unreach),
                 format(atom(W), "Literal '~w' in rule '~w' can never be derived (body unsatisfiable)", [N, L]) ), W1),
    findall(W, ( member(undef(N, _), Undef),
                 format(atom(W), "Literal '~w' used in rule body but never defined", [N]) ), W2),
    ( Strict == true -> mn_strict_warnings(TS, FmtStr, W3) ; W3 = [] ),
    append([W1, W2, W3, Cons], Ws0), sort(Ws0, Warns),
    % strict: undefined-literal warnings are errors
    ( Strict == true -> Errs = W2 ; Errs = [] ),
    ( Errs == [] -> Valid = true ; Valid = false ),
    with_output_to(string(Out), (
      ( Valid == true -> format("Valid ~w plan.~n", [FmtStr])
      ; format("Invalid ~w plan:~n", [FmtStr]) ),
      forall(member(E, Errs), format("  ERROR: ~w~n", [E])),
      ( Strict == true -> mn_warn_set(Warns, W2, Out2) ; Out2 = Warns ),
      forall(member(Wn, Out2), format("  WARNING: ~w~n", [Wn]))
    )).

% in strict mode the undefined-literal lines are reported as errors, not warnings
mn_warn_set(All, ErrLines, Rest) :- subtract(All, ErrLines, Rest).

mn_consistency(TS, Concls, Lines) :-
    % circular superiority pairs (W>L and L>W)
    findall(Line,
      ( mn_q(TS, [sup, A, B]), mn_q(TS, [sup, B, A]), A @< B,
        format(atom(Line), "Circular superiority: prefer(~w,~w) and prefer(~w,~w)", [A, B, B, A]) ),
      Circ0),
    sort(Circ0, Circ),
    % contradictory definite conclusions: +D lit and +D complement
    findall([S, N], ( member([pD, Lit], Concls), mn_litname(Lit, S, N) ), Defs),
    findall(Line,
      ( member([pos, N], Defs), memberchk([neg, N], Defs),
        format(atom(Line), "Contradictory definite conclusions: both +D ~w and +D ~~~w", [N, N]) ),
      Contra0),
    sort(Contra0, Contra),
    append(Circ, Contra, Lines).

mn_strict_warnings(TS, FmtStr, Ws) :-
    findall(W, ( mn_q(TS, [rule, L, K, _, _]), K \== fact, \+ mn_lifecycle_rule(L),
                 format(atom(W), "Rule '~w' has no source annotation (defaults to anonymous)", [L]) ), W1),
    ( FmtStr == 'MeTTa', \+ mn_q(TS, [metainfo, plan, _])
      -> W2 = ['Missing (meta plan ...) block'] ; W2 = [] ),
    append(W1, W2, Ws).

% lifecycle literal / rule-label prefixes (asserted at runtime by claim/etc.)
mn_lifecycle_lit(N) :- atom(N),
    member(P, ['completed-','completed_','claimed-','claimed_','blocked-','blocked_',
               'unblocked-','unblocked_','claim-v','claim_v','unclaim-v','unclaim_v',
               'block-v','block_v','unblock-v','unblock_v','state-claimed-','state-claimed_',
               'state-blocked-','state-blocked_','state-unclaimed-','state-unclaimed_',
               'state-unblocked-','state-unblocked_']),
    atom_concat(P, _, N), !.
mn_lifecycle_rule(L) :- atom(L),
    member(P, ['r-cl-','r-cl_','r-ucl-','r-ucl_','r-bl-','r-bl_','r-ubl-','r-ubl_']),
    atom_concat(P, _, L), !.

% ============================================================================
% assign — agent assignment lines
% ============================================================================
mm_print_assign(Agent, Names, true) :-
    once(( with_output_to(string(Out), (
             ( Agent == "" -> format("Agent assignments:~n")
             ; format("Assignments for ~w:~n", [Agent]) ),
             ( Names == [] -> format("  (no assignments)~n")
             ; forall(member(N, Names), format("  +d ~w~n", [N])) )
           )), write(Out) )).

% optional CLI positional (user index N), or Default if absent.
mm_argn_or(N, Default, Val) :-
    once(( current_prolog_flag(argv, Argv), Idx is N + 2,
           ( nth0(Idx, Argv, A) -> Val = A ; Val = Default ) )).

% plan format label from the path extension (.dfl -> DFL, else MeTTa).
mm_plan_fmt(Path, Fmt) :-
    once(( ( atom(Path) -> P = Path ; atom_string(P, Path) ),
           ( sub_atom(P, _, _, 0, '.dfl') -> Fmt = 'DFL' ; Fmt = 'MeTTa' ) )).

% ============================================================================
% plan analysis — dependency cycles (deadlocks) + self-inconsistency
% ============================================================================
% The cycle ALGORITHM and the consistency BOOLEAN live in idiomatic MeTTa
% (src/directive/inspect.metta): cycles are SCCs of the support-dependency graph
% (defeaters excluded — they block, don't support); a cyclic literal can never be
% grounded from facts -> a deadlock. This module keeps only the report formatter
% plus the consistency LINES, the same lines `validate` emits (mn_consistency).

% analyze report. Groups = MeTTa-computed list of SCC literal-lists.
mm_print_analyze2(Groups, TheorySp, Concls, true) :-
    once(( mn_consistency(TheorySp, Concls, Cons),
           with_output_to(string(Out), (
             format("Plan Analysis~n=============~n", []),
             ( Groups == []
             -> format("Dependency cycles: none~n", [])
             ;  length(Groups, NC), format("Dependency cycles: ~w~n", [NC]),
                forall(member(G, Groups),
                       ( maplist(mn_litname_str, G, Ns), atomic_list_concat(Ns, ' -> ', S),
                         format("  cycle: ~w~n", [S]) )) ),
             ( Cons == []
             -> format("Consistency: consistent~n", [])
             ;  format("Consistency: INCONSISTENT~n", []),
                forall(member(C, Cons), format("  ~w~n", [C])) )
           )), write(Out) )).

% literal name for display (functor; ~ for negated; mode bracket if modal)
mn_litname_str([lit, S, M, _, F, _], Str) :-
    ( M == none -> MS = '' ; atom_concat('[', M, M0), atom_concat(M0, ']', MS) ),
    ( S == neg -> atomic_list_concat([MS, '~', F], Str) ; atomic_list_concat([MS, F], Str) ).

% honest stub for commands requiring external services (LLM / OS / net / crypto).
mm_print_stub(Cmd, Needs, true) :-
    once(( format("Command '~w' is not available in this pure-logic engine.~n", [Cmd]),
           format("It requires ~w, outside the reasoning and task-coordination core.~n", [Needs]) )).
