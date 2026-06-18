% Process-mining kernel — the `learn` commands (extract-log / rules /
% validate-rules).
%
% Event logs are extracted from MeTTa `(claims CAT:NAME :at "TS" ... (given F) ...)`
% blocks (a string scan over the claims/at/given syntax), then the Alpha-style
% footprint + directly-follows relations drive rule learning with trace-level
% support/confidence and XOR/mutex conflict detection.
%
% NOTE on determinism: rules, conflicts, and `r_mined_N` numbering are emitted as
% a STABLE sorted set, so the output is reproducible across runs.
%
% Self-contained: depends only on SWI builtins (no cross-file predicate calls),
% so it loads cleanly via import_prolog_functions_from_file.

% ============================================================================
% Event-log extraction
% ============================================================================

% mm_event_log(+Files, -Cases)
%   Files : list of path atoms/strings (one case per file)
%   Cases : list of [CaseId, Events];  Events : list of [TS, Activity, Actor]
%           (Activity, Actor : atoms;  TS : string), stable-sorted by TS.
mm_event_log(Files, Cases) :-
    once(maplist(mn_file_case, Files, Cases)).

mn_file_case(File, [CaseId, Events]) :-
    ( atom(File) -> P = File ; atom_string(P, File) ),
    mn_case_id(P, CaseId),
    read_file_to_string(P, Content, []),
    mn_extract_events(Content, Events).

mn_case_id(Path, Id) :-
    file_base_name(Path, Base),
    ( file_name_extension(Stem, _, Base), Stem \== '' -> true ; Stem = Base ),
    ( atom(Stem) -> Id = Stem ; atom_string(Id, Stem) ).

% Split each `(claims ...)` block; the first split fragment is pre-amble (skip).
mn_extract_events(Content, Sorted) :-
    mn_split(Content, "(claims ", Frags),
    ( Frags = [_|Parts] -> true ; Parts = [] ),
    mn_parts_events(Parts, Events0),
    mn_stable_by_ts(Events0, Sorted).

mn_parts_events([], []).
mn_parts_events([P|Ps], Events) :-
    mn_one_part(P, Es),
    mn_parts_events(Ps, Rest),
    append(Es, Rest, Events).

% One claims block: leading [\w:]+ actor, first `:at "..."` timestamp, every
% `(given [\w-]+)` fact in scope (the fragment ends at the next `(claims `).
mn_one_part(Part, Events) :-
    mn_lead_word(Part, Actor),
    mn_find_ts(Part, TS),
    findall([TS, Fact, Actor], mn_given_in(Part, Fact), Events).

% ---- string helpers (scan the claims/at/given syntax) ----

% Split String on literal substring Sep.
mn_split(Str, Sep, [Pre|Rest]) :-
    ( sub_string(Str, B, _, _, Sep)
    -> sub_string(Str, 0, B, _, Pre),
       string_length(Sep, L), Skip is B + L,
       sub_string(Str, Skip, _, 0, Post),
       mn_split(Post, Sep, Rest)
    ; Pre = Str, Rest = [] ).

% Leading run of [\w:]  ->  the claim actor (e.g. agent:coder).
mn_lead_word(Str, Word) :-
    string_chars(Str, Cs), mn_take_word(Cs, Wc), atom_chars(Word, Wc).
mn_take_word([C|Cs], [C|Ws]) :- mn_wordc(C), !, mn_take_word(Cs, Ws).
mn_take_word(_, []).
mn_wordc(C) :- ( char_type(C, csym) -> true ; C == ':' ).

% First `:at` followed by whitespace and a quoted string  ->  timestamp ("" if absent).
mn_find_ts(Part, TS) :-
    once(( sub_string(Part, B, _, _, ":at"),
           After is B + 3, sub_string(Part, After, _, 0, R0),
           mn_skip_ws(R0, R1),
           sub_string(R1, 0, 1, _, "\""),
           sub_string(R1, 1, _, 0, R2),
           sub_string(R2, E, _, _, "\""),
           sub_string(R2, 0, E, _, TS)
         ) -> true ; TS = "" ).

% Every `(given [\w-]+)` fact (atom) in the fragment.
mn_given_in(Part, Fact) :-
    sub_string(Part, B, _, _, "(given"),
    After is B + 6, sub_string(Part, After, _, 0, R0),
    mn_skip_ws1(R0, R1),
    mn_lead_fact(R1, FactStr, Rest),
    FactStr \== "",
    sub_string(Rest, 0, 1, _, ")"),
    atom_string(Fact, FactStr).

mn_skip_ws(S, R) :-
    ( sub_string(S, 0, 1, _, C), mn_ws(C)
    -> sub_string(S, 1, _, 0, S1), mn_skip_ws(S1, R) ; R = S ).
mn_skip_ws1(S, R) :-
    sub_string(S, 0, 1, _, C), mn_ws(C),
    sub_string(S, 1, _, 0, S1), mn_skip_ws(S1, R).
mn_ws(" "). mn_ws("\t"). mn_ws("\n"). mn_ws("\r").

mn_lead_fact(Str, Fact, Rest) :-
    string_chars(Str, Cs), mn_take_fact(Cs, Fc, Rc),
    string_chars(Fact, Fc), string_chars(Rest, Rc).
mn_take_fact([C|Cs], [C|Fs], R) :- mn_factc(C), !, mn_take_fact(Cs, Fs, R).
mn_take_fact(Cs, [], Cs).
mn_factc(C) :- ( char_type(C, csym) -> true ; C == '-' ).

% Stable sort of events by timestamp (keysort is stable; ISO-8601 sorts lexically).
mn_stable_by_ts(Events, Sorted) :-
    findall(TS-E, ( member(E, Events), E = [TS|_] ), Pairs),
    keysort(Pairs, SortedP),
    pairs_values(SortedP, Sorted).

% ============================================================================
% Footprint / directly-follows
% ============================================================================

mn_case_seq([_Id, Events], Seq) :- maplist([E, A]>>(E = [_, A, _]), Events, Seq).

mn_activities(Cases, Acts) :-
    findall(A, ( member(C, Cases), mn_case_seq(C, S), member(A, S) ), As),
    sort(As, Acts).

% directly-follows relation as a sorted set of A-B pairs (consecutive in a case).
mn_df_set(Cases, DF) :-
    findall(A-B, ( member(C, Cases), mn_case_seq(C, S), mn_adj(S, A, B) ), Ps),
    sort(Ps, DF).
mn_adj([A, B|_], A, B).
mn_adj([_|T], A, B) :- mn_adj(T, A, B).

% causal pairs: A->B observed but B->A not  (sorted for determinism).
mn_causal(DF, Causal) :-
    findall(A-B, ( member(A-B, DF), \+ memberchk(B-A, DF) ), C0),
    sort(C0, Causal).

mn_is_causal(DF, A, B)    :- memberchk(A-B, DF), \+ memberchk(B-A, DF).
mn_is_unrelated(DF, A, B) :- \+ memberchk(A-B, DF), \+ memberchk(B-A, DF).

% ---- trace-level support & confidence ----

% support(a,b): # cases where a directly precedes b at least once.
mn_support(Cases, A, B, Sup) :-
    aggregate_all(count, ( member(C, Cases), mn_case_has_adj(C, A, B) ), Sup).
mn_case_has_adj(C, A, B) :- mn_case_seq(C, S), ( mn_adj_eq(S, A, B) -> true ).
mn_adj_eq([X, Y|_], A, B) :- X == A, Y == B, !.
mn_adj_eq([_|T], A, B) :- mn_adj_eq(T, A, B).

% confidence(a,b): support / (# cases where a has any outgoing transition).
mn_confidence(Cases, A, B, Conf) :-
    mn_support(Cases, A, B, Sup),
    aggregate_all(count, ( member(C, Cases), mn_has_out(C, A) ), D),
    ( D =:= 0 -> Conf = 0.0 ; Conf is float(Sup) / float(D) ).
mn_has_out(C, A) :- mn_case_seq(C, S), ( append(_, [A, _|_], S) -> true ).

% ============================================================================
% Rule learning
% ============================================================================

% mm_mine_rules(+Files, +MinSup, +MinConf, -Rules)
%   Rules : list of [Body, Head, Support, ConfStr] (ConfStr = "%.2f"),
%           sorted by (Body,Head) — deterministic.
mm_mine_rules(Files, MinSup, MinConf, Rules) :-
    once(( mm_event_log(Files, Cases),
           mn_rules_full(Cases, MinSup, MinConf, Full),
           findall([A, B, Sup, CS], member([A, B, Sup, _, CS], Full), Rules) )).

% internal: full 5-tuple [Body, Head, Support, ConfFloat, ConfStr], sorted.
mn_rules_full(Cases, MinSup, MinConf, Full) :-
    mn_df_set(Cases, DF),
    mn_causal(DF, Causal),
    findall([A, B, Sup, Conf, CS],
      ( member(A-B, Causal),
        mn_support(Cases, A, B, Sup),
        mn_confidence(Cases, A, B, Conf),
        Sup >= MinSup, Conf >= MinConf,
        format(string(CS), "~2f", [Conf]) ),
      Full).

% ---- dfl render (default `directive learn rules` output) ----
mm_mine_dfl(Files, MinSup, MinConf, Out) :-
    once(( mm_event_log(Files, Cases),
           mn_rules_full(Cases, MinSup, MinConf, Full),
           with_output_to(string(Out),
             forall(nth1(I, Full, [A, B, Sup, _, CS]),
               format("r_mined_~w: ~w >> ~w  ; support=~w, confidence=~w~n",
                      [I, A, B, Sup, CS]))) )).

% ---- summary render ----
mm_mine_summary(Files, MinSup, MinConf, Out) :-
    once(( mm_event_log(Files, Cases),
           mn_rules_full(Cases, MinSup, MinConf, Full),
           mn_conflicts(Cases, Conflicts),
           length(Cases, NC), length(Full, NR), length(Conflicts, NK),
           with_output_to(string(Out), (
             format("Mining Results~n==============~n", []),
             format("Traces: ~w~n", [NC]),
             format("Rules learned: ~w~n", [NR]),
             format("Conflicts detected: ~w~n~n", [NK]),
             ( Full == [] -> true
             ; format("Learned Rules:~n", []),
               forall(nth1(I, Full, R), ( mn_rule_block_line(I, R, 1, L), write(L), nl )) ),
             ( Conflicts == [] -> true
             ; nl, format("Conflicts:~n", []),
               forall(member(K, Conflicts), ( mn_conflict_line(K, L), write(L), nl )) )
           )) )).

% MeTTa line for a learned rule; Gap = #spaces between the rule and "(support...".
mn_rule_block_line(I, [A, B, Sup, _, CS], Gap, Line) :-
    ( Gap =:= 2 -> Sp = "  " ; Sp = " " ),
    format(string(Line),
      "  (normally r_mined_~w (~w) (~w))~w(support: ~w, confidence: ~w)",
      [I, A, B, Sp, Sup, CS]).

% ============================================================================
% Conflict detection (Alpha Petri-net structure: XOR-choice + mutex)
% ============================================================================

mn_conflicts(Cases, Conflicts) :-
    mn_df_set(Cases, DF),
    mn_causal(DF, Causal),
    mn_activities(Cases, Acts),
    mn_start_acts(Cases, Start),
    mn_maximal_pairs(DF, Acts, Causal, Maximal),
    % XOR-choice groups: >1 start activities, or a maximal-pair B-set with >1 member
    findall(G, ( ( Start = [_, _|_], G = Start )
               ; ( member(_-B, Maximal), B = [_, _|_], G = B ) ), Choices),
    findall([choice, G], member(G, Choices), ChoiceConf),
    mn_mutex(Cases, Acts, Choices, Mutex),
    findall([mutex, P], member(P, Mutex), MutexConf),
    append(ChoiceConf, MutexConf, Conflicts).

mn_start_acts(Cases, S) :-
    findall(A, ( member(C, Cases), mn_case_seq(C, [A|_]) ), As), sort(As, S).
mn_end_acts(Cases, E) :-
    findall(A, ( member(C, Cases), mn_case_seq(C, Seq), last(Seq, A) ), As), sort(As, E).

% pairs (a,b) of activities (a@<b) that never co-occur and aren't a known choice.
mn_mutex(Cases, Acts, Choices, Pairs) :-
    findall([A, B],
      ( mn_ordpair(Acts, A, B),
        \+ mn_co_occur(Cases, A, B),
        \+ ( member(G, Choices), memberchk(A, G), memberchk(B, G) ) ),
      Pairs).
mn_ordpair(Acts, A, B) :- append(_, [A|Rest], Acts), member(B, Rest).
mn_co_occur(Cases, A, B) :-
    once(( member(C, Cases), mn_case_seq(C, S), memberchk(A, S), memberchk(B, S) )).

% ---- Alpha maximal-pair discovery (sorted sets for determinism) ----
mn_maximal_pairs(DF, Acts, Causal, Maximal) :-
    findall(As-Bs,
      ( member(A-B, Causal),
        mn_extend(DF, Acts, [A], [B], a, A1),
        mn_extend(DF, Acts, A1, [B], b, B1),
        sort(A1, As), sort(B1, Bs) ),
      Extended0),
    sort(Extended0, Unique),
    include(mn_is_maximal(Unique), Unique, Maximal).

mn_is_maximal(All, A-B) :-
    \+ ( member(A2-B2, All), (A2-B2) \== (A-B),
         ord_subset(A, A2), ord_subset(B, B2) ).

mn_extend(DF, Acts, Set0, Other, Which, Set) :-
    foldl(mn_try_add(DF, Other, Which), Acts, Set0, Set).
mn_try_add(DF, B, a, Act, Ain, Aout) :-
    ( \+ memberchk(Act, Ain), New = [Act|Ain],
      mn_all_unrelated(DF, New), mn_all_causal(DF, New, B)
    -> Aout = New ; Aout = Ain ).
mn_try_add(DF, A, b, Act, Bin, Bout) :-
    ( \+ memberchk(Act, Bin), New = [Act|Bin],
      mn_all_unrelated(DF, New), mn_all_causal(DF, A, New)
    -> Bout = New ; Bout = Bin ).

mn_all_unrelated(DF, Set) :-
    forall( ( member(X, Set), member(Y, Set), X @< Y ), mn_is_unrelated(DF, X, Y) ).
mn_all_causal(DF, SetA, SetB) :-
    forall( ( member(A, SetA), member(B, SetB) ), mn_is_causal(DF, A, B) ).

mn_conflict_line([choice, G], Line) :-
    atomic_list_concat(G, ', ', Acts),
    format(string(Line), "  Choice: ~w", [Acts]).
mn_conflict_line([mutex, [A, B]], Line) :-
    format(string(Line), "  Mutex: ~w, ~w", [A, B]).

% ============================================================================
% extract-log renders
% ============================================================================

mm_extract_summary(Files, Out) :-
    once(( mm_event_log(Files, Cases),
           aggregate_all(sum(N), ( member([_, Es], Cases), length(Es, N) ), Total0),
           ( Total0 == '' -> Total = 0 ; Total = Total0 ),
           length(Cases, NC),
           with_output_to(string(Out), (
             format("Event Log Summary~n=================~n", []),
             format("Cases: ~w~n", [NC]),
             format("Total events: ~w~n~n", [Total]),
             forall(member([Id, Es], Cases), (
               length(Es, NE),
               format("Case: ~w (~w events)~n", [Id, NE]),
               forall(member([TS, Act, Actor], Es),
                 format("  ~w: ~w (~w)~n", [TS, Act, Actor]))
             ))
           )) )).

% events as MeTTa-friendly tuples for tests: [CaseId, [[TS,Act,Actor],...]]
mm_extract_events_list(Files, Cases) :- mm_event_log(Files, Cases).

% ---- extract-log JSON (the DEFAULT `extract-log` format; deterministic) ----
% Pretty JSON (2-space indent) with keys in a fixed sorted order:
% activity<actor<annotations<bindings<timestamp within an event, events<id within
% a case, cases<metadata at the top level.
mm_extract_json(Files, Out) :-
    once(( mm_event_log(Files, Cases),
           with_output_to(string(Out), mn_json_log(Cases)) )).

mn_json_log(Cases) :-
    format("{~n  \"cases\": ", []),
    mn_json_cases(Cases, 2),
    format(",~n  \"metadata\": {}~n}", []).

mn_json_cases([], _)  :- write("[]").
mn_json_cases([C|Cs], Ind) :-
    format("[~n", []), I1 is Ind + 2,
    mn_json_seq([C|Cs], I1, mn_json_case),
    nl, mn_indent(Ind), write("]").

mn_json_case([Id, Events], Ind) :-
    mn_indent(Ind), format("{~n", []), I1 is Ind + 2,
    mn_indent(I1), write("\"events\": "), mn_json_events(Events, I1),
    format(",~n", []),
    mn_indent(I1), write("\"id\": "), mn_jstr(Id), nl,
    mn_indent(Ind), write("}").

mn_json_events([], _) :- write("[]").
mn_json_events([E|Es], Ind) :-
    format("[~n", []), I1 is Ind + 2,
    mn_json_seq([E|Es], I1, mn_json_event),
    nl, mn_indent(Ind), write("]").

mn_json_event([TS, Act, Actor], Ind) :-
    mn_indent(Ind), format("{~n", []), I1 is Ind + 2,
    mn_indent(I1), write("\"activity\": "), mn_jstr(Act), write(","), nl,
    mn_indent(I1), write("\"actor\": "), mn_jstr(Actor), write(","), nl,
    mn_indent(I1), write("\"annotations\": {},"), nl,
    mn_indent(I1), write("\"bindings\": {},"), nl,
    mn_indent(I1), write("\"timestamp\": "), mn_jstr(TS), nl,
    mn_indent(Ind), write("}").

% JSON string literal with " and \ escaped.
mn_jstr(V) :-
    ( atom(V) -> atom_string(V, S) ; ( string(V) -> S = V ; term_string(V, S) ) ),
    write("\""), string_chars(S, Cs),
    forall(member(C, Cs),
      ( C == '"'  -> write("\\\"")
      ; C == '\\' -> write("\\\\")
      ; write(C) )),
    write("\"").

% comma-separated JSON array body, one Goal(Item, Indent) per element.
mn_json_seq([X], Ind, Goal)      :- !, call(Goal, X, Ind).
mn_json_seq([X|Xs], Ind, Goal)   :- call(Goal, X, Ind), format(",~n", []), mn_json_seq(Xs, Ind, Goal).

mn_indent(N) :- forall(between(1, N, _), write(" ")).

% ---- validate-rules render ----
% ExistingCount is computed MeTTa-side (non-fact rules in the `against` theory).
mm_mine_validate(Traces, ExistingCount, Out) :-
    once(( mm_event_log(Traces, Cases),
           mn_rules_full(Cases, 1, 0.0, Full),
           length(Cases, NC), length(Full, NLearned),
           include(mn_high_conf, Full, High),
           exclude(mn_high_conf, Full, Low),
           length(High, NHigh), length(Low, NLow),
           with_output_to(string(Out), (
             format("Validation Report~n=================~n", []),
             format("Traces analyzed: ~w~n", [NC]),
             format("Rules learned: ~w~n", [NLearned]),
             format("Existing rules: ~w~n~n", [ExistingCount]),
             format("Confidence:~n", []),
             format("  High confidence (>=0.70): ~w rules~n", [NHigh]),
             format("  Low confidence (<0.70): ~w rules (review recommended)~n~n", [NLow]),
             ( Full == [] -> true
             ; format("Learned Rules:~n", []),
               forall(nth1(I, Full, R), ( mn_rule_block_line(I, R, 2, L), write(L), nl )) ),
             ( Low == [] -> true
             ; nl, format("Low Confidence Rules (review recommended):~n", []),
               forall(member(R, Low), ( nth1(I, Full, R), mn_rule_block_line(I, R, 2, L), write(L), nl )) )
           )) )).
mn_high_conf([_, _, _, Conf, _]) :- Conf >= 0.7.

% ---- side-effecting printers (write EXACT CLI bytes; no added newline) ----
mm_print_extract_summary(Files, true) :-
    once(( mm_extract_summary(Files, S), write(S) )).
mm_print_extract_json(Files, true) :-
    once(( mm_extract_json(Files, S), write(S), nl )).
mm_print_mine_dfl(Files, MinSup, MinConf, true) :-
    once(( mm_mine_dfl(Files, MinSup, MinConf, S), write(S) )).
mm_print_mine_summary(Files, MinSup, MinConf, true) :-
    once(( mm_mine_summary(Files, MinSup, MinConf, S), write(S) )).
mm_print_validate(Traces, ExistingCount, true) :-
    once(( mm_mine_validate(Traces, ExistingCount, S), write(S) )).

% Count non-fact rules in a theory space (for validate-rules "Existing rules").
mm_count_nonfact(TheorySp, N) :-
    once(aggregate_all(count,
      ( G =.. [TheorySp, rule, _, Kind, _, _], catch(G, _, fail), Kind \== fact ),
      N)).

% ---- CLI argv parsing for the `learn` namespace ----
% argv layout (run.sh): 0=entry file, 1=--silent, 2=top command, 3..=args.
mn_learn_args(Args) :-
    current_prolog_flag(argv, Argv),
    findall(A, ( nth0(I, Argv, A), I >= 3 ), Args).

mm_learn_files(Files)  :- once(( mn_learn_args(A), mn_files(A, Files) )).
mm_learn_format(Def, V):- once(( mn_learn_args(A), mn_flag(A, '--format', Def, V) )).
mm_learn_against(Def, V):- once(( mn_learn_args(A), mn_flag(A, '--against', Def, V0),
                                  ( atom(V0) -> V = V0 ; atom_string(V, V0) ) )).
mm_learn_minsup(Def, V):- once(( mn_learn_args(A), mn_flag_num(A, '--min-support', Def, V) )).
mm_learn_minconf(Def, V):- once(( mn_learn_args(A), mn_flag_num(A, '--min-confidence', Def, V) )).

mn_files([], []).
mn_files([A|As], Fs) :-
    ( mn_is_flag(A)
    -> ( mn_takes_val(A) -> mn_drop_val(As, Rest) ; Rest = As ), mn_files(Rest, Fs)
    ;  atom_string(A, S), Fs = [S|Fs1], mn_files(As, Fs1) ).
mn_drop_val([_|R], R).
mn_drop_val([], []).
mn_is_flag(A) :- atom(A), sub_atom(A, 0, 2, _, '--').
mn_takes_val('--format').
mn_takes_val('--min-support').
mn_takes_val('--min-confidence').
mn_takes_val('--against').
mn_flag(Args, F, Def, Val) :- ( append(_, [F, V|_], Args) -> Val = V ; Val = Def ).
mn_flag_num(Args, F, Def, Val) :-
    ( append(_, [F, V|_], Args), atom_number(V, N) -> Val = N ; Val = Def ).
