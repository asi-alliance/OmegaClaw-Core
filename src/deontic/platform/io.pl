%%% lib_deontic platform kernel (the SWI-Prolog side of the MeTTa engine).
%%%
%%% A small deterministic Prolog kernel behind stable MeTTa-callable predicates
%%% (last argument is the output; pure side effects return true). MeTTa surface
%%% syntax is normalized HERE because its heads (not/and/arith/comparison)
%%% collide with registered MeTTa functions.
%%%
%%% HARD RULE: every exported predicate is deterministic (once/1) — PeTTa wraps
%%% runnables in findall, which would exhaustively backtrack stray choicepoints.

:- dynamic mm_label_counter/2.

%%% ----------------------------------------------------------------------
%%% Generic file / misc helpers
%%% ----------------------------------------------------------------------

% Plan/theory files are .metta source, read via PeTTa's native loader
% (load_metta_file/3 in mm_load_into below); no separate s-expression reader.

% Reconstruct the exact source float of a tagged decimal (identical to what the
% reader produced before tagging), or pass a non-decimal value through unchanged.
mm_decf([dec, M, Sc], V) :- !, mm_dec_str(M, Sc, Str), atom_number(Str, V).
mm_decf(X, X).

mm_path(Path, P) :- ( atom(Path) -> P = Path ; atom_string(P, Path) ).

mm_append_file(Path, Str, true) :-
    once(( mm_path(Path, P), open(P, append, Out), write(Out, Str), close(Out) )).

mm_write_file(Path, Str, true) :-
    once(( mm_path(Path, P), open(P, write, Out), write(Out, Str), close(Out) )).

mm_read_file(Path, Str) :-
    once(( mm_path(Path, P), read_file_to_string(P, Str, []) )).

mm_exists(Path, R) :-
    once(( mm_path(Path, P), ( exists_file(P) -> R = true ; R = false ) )).

mm_now_iso(Iso) :-
    once(( get_time(T), stamp_date_time(T, DT, 'UTC'),
           format_time(string(Iso), '%FT%TZ', DT) )).

mm_clear_space(Space, true) :-
    once(forall(( current_predicate(Space/A), functor(H, Space, A) ), retractall(H))).

mm_gensym(Prefix, Sym) :-
    once(( ( retract(mm_label_counter(Prefix, N)) -> true ; N = 0 ),
           N1 is N + 1, assertz(mm_label_counter(Prefix, N1)),
           format(atom(Sym), '~w~w', [Prefix, N1]) )).

mm_reset_labels :- retractall(mm_label_counter(f, _)),
                   retractall(mm_label_counter(r, _)).

mm_halt(Code, true) :- halt(Code).

% Seed the global RNG (for reproducible Structural Random Indexing embeddings).
mm_srand(N, true) :- once(set_random(seed(N))).

% Raw print (no quotes around strings, unlike println! of a string).
mm_print(S, true) :- once(( write(S), nl )).

% Bulk-print a conclusion tuple list in ONE Prolog call (avoids per-line MeTTa
% eval overhead — ~0.3s on an 8k-conclusion theory). Cs = [[Tag,Lit], ...].
mm_print_concls(Cs, true) :-
    once(( with_output_to(string(Buf),
             forall(member(C, Cs), ( mm_concl_str(C, S), write(S), nl ))),
           write(Buf) )).

% Same for trust-annotated conclusions [tconcl,...].
mm_print_tconcls(Cs, true) :-
    once(( with_output_to(string(Buf),
             forall(member(C, Cs), ( mm_trust_str(C, S), write(S), nl ))),
           write(Buf) )).

% Parse a CLI literal token into an internal 6-slot lit:
%   "flies" -> [lit,pos,none,none,flies,[]]
%   "~flies"/"-flies" -> [lit,neg,none,none,flies,[]]
%   "(flies tweety)" -> [lit,pos,none,none,flies,[tweety]]
%   "(must pay)" / "(during meeting 10 20)" route through mm_lit.
mm_parse_lit(Tok, Lit) :-
    once(( ( atom(Tok) -> A = Tok ; atom_string(A, Tok) ),
           atom_chars(A, Cs),
           ( Cs = ['~'|Rest] -> Neg = neg, atom_chars(Body, Rest)
           ; Cs = ['-'|Rest] -> Neg = neg, atom_chars(Body, Rest)
           ; Neg = pos, Body = A ),
           ( sub_atom(Body, 0, 1, _, '(')
             -> sread(Body, Sexpr), mm_lit(Sexpr, [lit, S0, M, T, F, Args]),
                ( Neg == neg -> mm_flip(S0, S1) ; S1 = S0 ),
                Lit = [lit, S1, M, T, F, Args]
             ;  Lit = [lit, Neg, none, none, Body, []] ) )).

%% Standard MeTTa stdlib file API (handle-based), backed by Prolog streams.
'file-open!'(Path, Opts, Handle) :-
    once(( mm_path(Path, P), mm_open_mode(Opts, Mode), open(P, Mode, Handle) )).
mm_open_mode(Opts, Mode) :-
    ( sub_string(Opts, _, _, _, "a") -> Mode = append
    ; sub_string(Opts, _, _, _, "w") -> Mode = write
    ; Mode = read ).
'file-close!'(Handle, true) :- once(close(Handle)).
'file-read-to-string!'(Handle, Str) :- once(read_string(Handle, _, Str)).
'file-write!'(Handle, Str, true) :- once(write(Handle, Str)).
'file-get-size!'(Handle, Size) :- once(stream_property(Handle, file_name(F))), size_file(F, Size).
'file-seek!'(Handle, Pos, true) :- once(seek(Handle, Pos, bof, _)).

%% DL reasoning backend: native (atomspace MeTTa engine) | prolog (fast kernel).
%% Default reads $OMEGACLAW_DL_ENGINE (else prolog); a runtime set overrides it.
%% The same theory runs through either path with identical conclusions.
:- dynamic mm_dl_engine_mode/1.
mm_dl_engine_get(M) :-
    ( mm_dl_engine_mode(M0) -> M = M0
    ; getenv('OMEGACLAW_DL_ENGINE', E), downcase_atom(E, native) -> M = native
    ; M = prolog ).
mm_dl_engine_set(M, true) :-
    once(( retractall(mm_dl_engine_mode(_)), assertz(mm_dl_engine_mode(M)) )).

%% Minimal logger (same spirit as petta_lib_logger, zero external deps).
:- dynamic mm_log_level/1, mm_log_path/1.
mm_log_level(info).
mm_log_path("").
mm_level_num(trace, 0). mm_level_num(debug, 1). mm_level_num(info, 2).
mm_level_num(warn, 3).  mm_level_num(error, 4). mm_level_num(fatal, 5).

mm_log_set_level(L, true) :-
    once(( retractall(mm_log_level(_)), assertz(mm_log_level(L)) )).
mm_log_set_path(P, true) :-
    once(( retractall(mm_log_path(_)), assertz(mm_log_path(P)) )).
mm_log(Level, Msg, true) :-
    once(( mm_log_level(Cur), mm_level_num(Cur, CN), mm_level_num(Level, LN),
           ( LN < CN -> true
           ; swrite(Msg, S),
             get_time(T), format_time(atom(TS), '%T', T),
             string_upper(Level, UL),
             format(user_error, "[~w] [~w] ~w~n", [TS, UL, S]),
             mm_log_path(LP),
             ( LP == "" -> true
             ; open(LP, append, Out), format(Out, "[~w] [~w] ~w~n", [TS, UL, S]), close(Out) ) ) )).

%%% ----------------------------------------------------------------------
%%% Arithmetic (MeTTa arithmetic semantics, mapped onto SWI numbers)
%%%   Integer  -> SWI integer (arbitrary precision)
%%%   Decimal  -> SWI rational (exact)
%%%   Float    -> SWI float (contagious)
%%% Errors (div by zero, type mismatch, unbound var) FAIL silently: a body
%%% constraint that fails simply discards the candidate substitution, so the
%%% offending rule instance is never grounded.
%%% Expressions arrive as [ax, Op, Args] trees built by the MeTTa normalizer.
%%% ----------------------------------------------------------------------

mm_ax_eval(X, _) :- var(X), !, fail.
mm_ax_eval(X, X) :- number(X), !.
mm_ax_eval([dec, M, Sc], V) :- !, mm_decf([dec, M, Sc], V).
mm_ax_eval([ax, Op, Args], Out) :- !,
    maplist(mm_ax_eval, Args, Vals),
    mm_ax_apply(Op, Vals, Out0),
    mm_finite(Out0),
    Out = Out0.
mm_ax_eval(_, _) :- fail.

mm_finite(X) :- ( float(X) -> X =:= X, abs(X) =\= inf ; true ).

mm_ax_apply('+', [V|Vs], Out) :- foldl([A,B,C]>>(C is B + A), Vs, V, Out).
mm_ax_apply('-', [V], Out) :- !, Out is -V.
mm_ax_apply('-', [V|Vs], Out) :- foldl([A,B,C]>>(C is B - A), Vs, V, Out).
mm_ax_apply('*', [V|Vs], Out) :- foldl([A,B,C]>>(C is B * A), Vs, V, Out).
mm_ax_apply('/', [A,B], Out) :- B =\= 0,
    ( (integer(A), integer(B)) -> Out is A rdiv B   % exact "Decimal" division
    ; Out is A / B ).
mm_ax_apply(div, [A,B], Out) :- integer(A), integer(B), B =\= 0, Out is A div B.
mm_ax_apply(rem, [A,B], Out) :- integer(A), integer(B), B =\= 0, Out is A - (A div B) * B.
mm_ax_apply('**',  [A,B], Out) :-
    ( integer(A), integer(B), B >= 0 -> Out is A ** B
    ; integer(A), integer(B) -> Out is 1 rdiv (A ** (-B))
    ; Out is A ** B ).
mm_ax_apply(abs, [V], Out) :- Out is abs(V).
mm_ax_apply(min, [V|Vs], Out) :- foldl([A,B,C]>>(C is min(A,B)), Vs, V, Out).
mm_ax_apply(max, [V|Vs], Out) :- foldl([A,B,C]>>(C is max(A,B)), Vs, V, Out).

mm_cmp_op('=',  '=:='). mm_cmp_op('!=', '=\\='). mm_cmp_op('<', '<'). mm_cmp_op('>', '>').
mm_cmp_op('<=', '=<').  mm_cmp_op('>=', '>=').

%% MeTTa-callable: evaluate an [ax|...] tree (fails -> branch pruned).
mm_arith_eval(Ax, Out) :- once(mm_ax_eval(Ax, Out)).

%% MeTTa-callable: comparison constraint, returns true/false (fail-free).
mm_acmp(Op, L, R, Out) :-
    once(( mm_ax_eval(L, LV), mm_ax_eval(R, RV), mm_cmp_op(Op, P)
           -> ( call(P, LV, RV) -> Out = true ; Out = false )
           ;  Out = false )).

%% Numeric cross-type equality for grounding (Integer 2 == Decimal 2.0 ...).
mm_num_eq(A0, B0, Out) :-
    once(( mm_decf(A0, A), mm_decf(B0, B),
           number(A), number(B), A =:= B -> Out = true ; Out = false )).

% Integer percentage (done*100/total, floor division).
mm_pct(D, T, P) :- once(( T > 0 -> P is (D * 100) // T ; P = 0 )).

%%% ----------------------------------------------------------------------
%%% MeTTa ingestion: forms -> theory atoms in a space
%%%
%%% Theory space atoms:
%%%   [rule, Label, Kind, Body, Head]   Kind: fact|strict|defeasible|defeater
%%%       Body: list of [lit,S,F,Args] | [acmp,Op,AxL,AxR] | [abind,Var,Ax]
%%%       Head: [lit, pos|neg, Functor, Args]
%%%   [sup, Winner, Loser]
%%%   [metainfo, Label, KVs]
%%%   [trustinfo, Form]                 (trusts/claims-attr/decays/threshold, raw)
%%%   [claiminfo, Source, At, Note]     provenance of appended claims blocks
%%% Ground rules additionally seed (in their own spaces):
%%%   GroundSpace: [grule, Label, Kind, LogicBody, Head]  (constraints folded)
%%%   HerbSpace:   [ha, Head]
%%%   StatSpace:   [ulit, Lit] for every ground literal occurring
%%% Rules whose constant constraints are false get body [[lit,pos,'%never%',[]]]
%%% so they stay in the universe but can never fire.
%%% ----------------------------------------------------------------------

%% Load a plan/theory .metta file into Space via PeTTa's native loader: each
%% top-level form is added to Space as for any .metta source. Rule labels are
%% reset per load; the loader's per-form trace output is discarded. The MeTTa
%% layer (dl-load-native) then enumerates Space and ingests each form.
mm_load_into(Path, Space, true) :-
    once(( mm_reset_labels, mm_path(Path, P),
           with_output_to(string(_), load_metta_file(P, _, Space)) )).

%% Surface format of a plan/theory path: dfl (arrow syntax) or metta (s-expr).
mm_plan_format(Path, Format) :-
    once(( mm_path(Path, P), string_lower(P, PL),
           ( sub_string(PL, _, 4, 0, ".dfl") -> Format = dfl ; Format = metta ) )).

%%% ----------------------------------------------------------------------
%%% DFL (Defeasible Logic Format) — arrow syntax, propositional. A textbook-style
%%% surface notation for defeasible theories (Nute; Antoniou et al.), offered in
%%% addition to the s-expression MeTTa syntax. Grammar:
%%%   facts       >> p              |  label: >> p
%%%   strict      label: a, b -> q
%%%   defeasible  label: a, b => q
%%%   defeater    label: a, b ~> q
%%%   superiority  r1 > r2
%%%   negation    -p  /  ¬p
%%%   conjunction comma-separated body literals
%%%   comments    # to end of line
%%%   front-matter --- ... --- annotation blocks (metadata; skipped for reasoning)
%%% Maps to the SAME theory representation as the MeTTa ingester.
%%% ----------------------------------------------------------------------
mm_load_dfl(Path, TS, GS, HS, SS, Count) :-
    once(( mm_reset_labels,
           mm_path(Path, P), read_file_to_string(P, S, []),
           split_string(S, "\n", "", Lines),
           foldl(mm_dfl_line(TS, GS, HS, SS), Lines, fm(none)-0, fm(_)-Count) )).

% State threads a front-matter flag (in/out of a --- block) and the count.
mm_dfl_line(TS, GS, HS, SS, Line0, FM0-N0, FM-N) :-
    mm_dfl_strip(Line0, L),
    ( L == "" -> FM = FM0, N = N0
    ; L == "---" -> ( FM0 = fm(in) -> FM = fm(none) ; FM = fm(in) ), N = N0
    ; FM0 = fm(in) -> FM = FM0, N = N0                     % annotation line: skip
    ; FM = fm(none),
      ( mm_dfl_stmt(L, TS, GS, HS, SS) -> N is N0 + 1
      ; mm_log(warn, ["dfl skipped", L], _), N = N0 ) ).

% strip a # comment (to EOL) and trim surrounding whitespace
mm_dfl_strip(Line0, Trimmed) :-
    ( sub_string(Line0, B, _, _, "#") -> sub_string(Line0, 0, B, _, NoComment) ; NoComment = Line0 ),
    normalize_space(string(Trimmed), NoComment).

% one DFL statement -> theory. Check 2-char ops before the 1-char '>'.
mm_dfl_stmt(L, TS, GS, HS, SS) :-
    ( sub_string(L, _, _, _, "->") -> mm_dfl_rule(L, "->", strict, TS, GS, HS, SS)
    ; sub_string(L, _, _, _, "=>") -> mm_dfl_rule(L, "=>", defeasible, TS, GS, HS, SS)
    ; sub_string(L, _, _, _, "~>") -> mm_dfl_rule(L, "~>", defeater, TS, GS, HS, SS)
    ; sub_string(L, _, _, _, ">>") -> mm_dfl_fact(L, TS, GS, HS, SS)
    ; sub_string(L, _, _, _, ">")  -> mm_dfl_sup(L, TS) ).

% label: body OP head   (label optional)
mm_dfl_rule(L, Op, Kind, TS, GS, HS, SS) :-
    mm_split_once(L, Op, LeftS, RightS),
    mm_dfl_label_body(LeftS, Label, BodyS),
    mm_dfl_body(BodyS, Body),
    mm_dfl_lit(RightS, Head),
    mm_add_rule(TS, GS, HS, SS, Label, Kind, Body, Head).

% [label:] >> head
mm_dfl_fact(L, TS, GS, HS, SS) :-
    mm_split_once(L, ">>", _LeftS, RightS),
    mm_dfl_lit(RightS, Lit), ground(Lit),
    mm_gensym(f, Label),
    mm_add_rule(TS, GS, HS, SS, Label, fact, [], Lit).

% r1 > r2  (superiority)
mm_dfl_sup(L, TS) :-
    mm_split_once(L, ">", LeftS, RightS),
    normalize_space(atom(W), LeftS), normalize_space(atom(Lo), RightS),
    add_sexp(TS, [sup, W, Lo]).

% split "LABEL: BODY" -> Label (gensym if absent), BodyString
mm_dfl_label_body(S, Label, Body) :-
    ( sub_string(S, _, _, _, ":")
      -> mm_split_once(S, ":", LabS, Body), normalize_space(atom(Label), LabS)
      ;  mm_gensym(r, Label), Body = S ).

% comma-separated body literals
mm_dfl_body(S, Lits) :-
    split_string(S, ",", " ", Parts0),
    exclude(==(""), Parts0, Parts),
    maplist(mm_dfl_lit, Parts, Lits).

% a DFL literal: name | -name | ¬name | pred(a, b) | -pred(a, b)
mm_dfl_lit(S0, Lit) :-
    normalize_space(string(S), S0),
    ( ( sub_string(S, 0, 1, _, "-") ; sub_string(S, 0, 1, _, "¬") )
      -> sub_string(S, 1, _, 0, Rest), mm_dfl_atom(Rest, [lit, P, none, none, F, A]),
         mm_flip(P, P2), Lit = [lit, P2, none, none, F, A]
      ;  mm_dfl_atom(S, Lit) ).

% pred(a, b) -> functor+args; flat name -> 0-arity
mm_dfl_atom(S0, [lit, pos, none, none, F, Args]) :-
    normalize_space(string(S), S0),
    ( split_string(S, "(", "", [FS, Rest]), string_concat(ArgsS, ")", Rest)
      -> normalize_space(atom(F), FS),
         split_string(ArgsS, ",", " ", AParts0), exclude(==(""), AParts0, AParts),
         maplist(mm_dfl_arg, AParts, Args)
      ;  atom_string(F, S), Args = [] ).

mm_dfl_arg(S, A) :- ( atom_number(S, N) -> A = N ; atom_string(A, S) ).

% split a string on the first occurrence of a separator substring
mm_split_once(S, Sep, Left, Right) :-
    sub_string(S, B, _, _, Sep), !,
    sub_string(S, 0, B, _, Left),
    string_length(Sep, SL), AfterB is B + SL,
    sub_string(S, AfterB, _, 0, Right).

%% Ingest a single already-parsed form (for REPL/assert paths).
mm_ingest(Form, TheorySp, GroundSp, HerbSp, StatSp, true) :-
    once(mm_ingest_form(TheorySp, GroundSp, HerbSp, StatSp, Form, 0, _)).

%% --at <ref>: drop temporal ground rules / herbrand atoms / universe literals
%% whose temporal interval is not active at the reference time (s =< t =< e).
%% Ref is millis (int) or an ISO-8601 string. Non-temporal entries are kept.
mm_at_filter(GroundSp, HerbSp, StatSp, Ref, true) :-
    once(( mm_ref_millis(Ref, T),
           mm_retract_inactive(GroundSp, [grule, _, _, _, H], H, T),
           mm_retract_inactive(GroundSp, [grule, _, _, B, _], B, T),
           mm_retract_inactive(HerbSp, [ha, H], H, T),
           mm_retract_inactive(StatSp, [ulit, H], H, T) )).

mm_ref_millis(Ref, T) :- ( number(Ref) -> T = Ref
                         ; ( atom(Ref) -> A = Ref ; atom_string(A, Ref) ),
                           parse_time(A, iso_8601, E) -> T is round(E * 1000)
                         ; atom_number(Ref, T) ).

%% Retract space atoms matching Pattern where the literal(s) at Sel are temporally
%% inactive at T. Sel is either a single [lit|...] or a body-list of them.
mm_retract_inactive(Space, Pattern, Sel, T) :-
    findall(Pattern,
            ( call_sexp_all(Space, Pattern), mm_sel_inactive(Sel, T) ),
            Dead),
    forall(member(P, Dead), ( P = [Rel|Args], G =.. [Space, Rel|Args], retract(G) )).

call_sexp_all(Space, [Rel|Args]) :- Term =.. [Space, Rel|Args], call(Term).

mm_sel_inactive([lit|L], T) :- !, mm_lit_inactive([lit|L], T).
mm_sel_inactive(Body, T) :- is_list(Body),
    member(Lit, Body), Lit = [lit|_], mm_lit_inactive(Lit, T), !.

mm_lit_inactive([lit, _, _, [iv, S, E], _, _], T) :-
    \+ ( mm_tp_le(S, T, true), mm_tp_le(T, E, true) ).

%% Add an INTERNAL literal as a fact with a unique hypothesis label
%% (used by the what-if and requires query operators when injecting hypotheses).
mm_add_fact(Lit, TheorySp, GroundSp, HerbSp, StatSp, Label) :-
    once(( mm_gensym('__hyp_', Label),
           mm_add_rule(TheorySp, GroundSp, HerbSp, StatSp, Label, fact, [], Lit) )).

mm_ingest_form(TS, GS, HS, SS, Form, N0, N) :-
    ( mm_ingest_form_(TS, GS, HS, SS, Form) -> N is N0 + 1
    ; mm_log(warn, ["skipped form", Form], _), N = N0 ).

mm_ingest_form_(TS, GS, HS, SS, [given, L]) :- !,
    mm_lit(L, Lit), ground(Lit),
    mm_gensym(f, Lbl),
    mm_add_rule(TS, GS, HS, SS, Lbl, fact, [], Lit).
% Deadline obligation (temporal modal defeasible logic — Governatori et al. 2007):
%   (deadline (must pay) achieve 0 30)            achievement: O pay by 30
%   (deadline (forbidden trespass) maintain 0 100) maintenance: keep ¬trespass in [0,100]
%   (deadline (must pay) achieve 0 30 fine)        + sanction "fine" on violation
% Asserts the deontic literal as an in-force obligation, and records deadline
% metadata for the time-aware compliance analysis (deontic.pl).
mm_ingest_form_(TS, GS, HS, SS, [deadline, M, Type | Rest]) :- !,
    mm_lit(M, [lit, Sg, Mode, _, F, A]),
    mm_gensym(f, Lbl),
    mm_add_rule(TS, GS, HS, SS, Lbl, fact, [], [lit, Sg, Mode, none, F, A]),
    mm_dl_times(Rest, S0, E0, Sanc),
    mm_tp(S0, St), mm_tp(E0, En),
    add_sexp(SS, [deadlineinfo, Sg, Mode, F, A, Type, St, En, Sanc]).
% Event-Calculus obligation lifecycle (oPIEC/Mantenoglou; Governatori init/term):
%   (happens invoice 5)   (initiates invoice (must pay))   (terminates pay (must pay))
% Events occur at time-points; an obligation fluent is in force from initiation
% until termination (inertia). Stored for the interval-based EC engine.
mm_ingest_form_(TS, _, _, _, [happens, E, T0]) :- !, mm_tp(T0, T), add_sexp(TS, [happens, E, T]).
mm_ingest_form_(TS, _, _, _, [initiates, E, M]) :- !, mm_lit(M, L), add_sexp(TS, [ec_init, E, L]).
mm_ingest_form_(TS, _, _, _, [terminates, E, M]) :- !, mm_lit(M, L), add_sexp(TS, [ec_term, E, L]).
mm_ingest_form_(TS, GS, HS, SS, [always | R])   :- !, mm_rule_form(TS, GS, HS, SS, strict, R).
mm_ingest_form_(TS, GS, HS, SS, [normally | R]) :- !, mm_rule_form(TS, GS, HS, SS, defeasible, R).
mm_ingest_form_(TS, GS, HS, SS, [except | R])   :- !, mm_rule_form(TS, GS, HS, SS, defeater, R).
mm_ingest_form_(TS, _, _, _, [prefer | Ls]) :- !,
    mm_sup_pairs(Ls, TS).
mm_ingest_form_(TS, _, _, _, [meta, Label | KVs]) :- !,
    add_sexp(TS, [metainfo, Label, KVs]).
mm_ingest_form_(TS, _, _, SS, [trusts, S, V]) :- !,
    add_sexp(TS, [trustinfo, [trusts, S, V]]),
    mm_decf(V, NV),
    ( call_sexp(SS, [trustval, S, _]) -> true ; add_sexp(SS, [trustval, S, NV]) ).
mm_ingest_form_(TS, _, _, _, [decays | R])    :- !, add_sexp(TS, [trustinfo, [decays | R]]).
mm_ingest_form_(TS, _, _, SS, [threshold, N, V]) :- !,
    add_sexp(TS, [trustinfo, [threshold, N, V]]),
    mm_decf(V, NV),
    add_sexp(SS, [threshval, N, NV]).
mm_ingest_form_(TS, GS, HS, SS, [claims, Source | R]) :- !,
    mm_claims_attrs(R, At, Note, Forms),
    add_sexp(TS, [claiminfo, Source, At, Note]),
    forall(member(F, Forms),
           ( ( mm_ingest_form_(TS, GS, HS, SS, F)
               -> mm_record_source(SS, Source, F) ; true ) )).
mm_ingest_form_(_, _, _, _, _) :- fail.

%% Attribute a claimed fact's literal to its source (for trust weighting).
mm_record_source(SS, Source, [given, L]) :- !,
    ( mm_lit(L, Lit), ground(Lit)
      -> ( call_sexp(SS, [src, Lit, Source]) -> true ; add_sexp(SS, [src, Lit, Source]) )
      ; true ).
mm_record_source(_, _, _).

mm_claims_attrs([':at', At | R], At2, Note, Forms) :- !,
    mm_claims_attrs(R, _, Note, Forms), At2 = At.
mm_claims_attrs([':note', Note | R], At, Note2, Forms) :- !,
    mm_claims_attrs(R, At, _, Forms), Note2 = Note.
mm_claims_attrs(Forms, "", "", Forms).

mm_sup_pairs([A, B | R], TS) :- !,
    add_sexp(TS, [sup, A, B]),
    mm_sup_pairs([B | R], TS).
mm_sup_pairs(_, _).

%% (always|normally|except) [Label] Body Head — label optional by arity.
mm_rule_form(TS, GS, HS, SS, Kind, [Label, B, H]) :- atom(Label), !,
    mm_rule_build(TS, GS, HS, SS, Kind, Label, B, H).
mm_rule_form(TS, GS, HS, SS, Kind, [B, H]) :- !,
    mm_gensym(r, Label),
    mm_rule_build(TS, GS, HS, SS, Kind, Label, B, H).

mm_rule_build(TS, GS, HS, SS, Kind, Label, B0, H0) :-
    mm_planvars([B0, H0], [B1, H1]),
    mm_body(B1, Body),
    ( H1 = [otherwise | Ds]
    -> mm_ctd_expand(TS, GS, HS, SS, Kind, Label, Body, Ds)   % ⊗-chain head
    ;  mm_lit(H1, Head),
       mm_add_rule(TS, GS, HS, SS, Label, Kind, Body, Head) ).

%%% Contrary-to-duty (CTD) reparation chains — Governatori's ⊗ operator.
%%% A head (otherwise D1 D2 ... Dn) means O(D1 ⊗ D2 ⊗ ... ⊗ Dn): D1 is the
%%% primary obligation; if D1 is VIOLATED its reparation D2 becomes obligatory;
%%% if D2 is then violated D3 activates; etc. Compiled to ordinary defeasible
%%% rules whose bodies accumulate the violation literals of the prior duties:
%%%   Label      : Body                          ⇒ D1
%%%   Label_rep1 : Body, viol(D1)                ⇒ D2
%%%   Label_rep2 : Body, viol(D1), viol(D2)      ⇒ D3
%%% so the normal DL(d) engine derives whichever reparation is currently active.
%%% viol(O p)=¬p ; viol(F p)=p (F p ≡ O¬p, ideal ¬p, violated by p). A permission
%%% terminates the chain (it cannot be violated).
mm_ctd_expand(TS, GS, HS, SS, Kind, Label, Body, Ds) :-
    maplist(mm_lit, Ds, Lits),
    mm_ctd_rules(TS, GS, HS, SS, Kind, Label, Body, Lits, 0, []).

mm_ctd_rules(_, _, _, _, _, _, _, [], _, _).
mm_ctd_rules(TS, GS, HS, SS, Kind, Label, Body, [D|Ds], I, Viols) :-
    append(Body, Viols, FullBody),
    ( I =:= 0 -> RLabel = Label
    ; atom_concat(Label, '_rep', L0), atom_concat(L0, I, RLabel) ),
    mm_add_rule(TS, GS, HS, SS, RLabel, Kind, FullBody, D),
    ( Ds == [] -> true
    ; mm_viol(D, V)
      -> append(Viols, [V], Viols1), I1 is I + 1,
         mm_ctd_rules(TS, GS, HS, SS, Kind, Label, Body, Ds, I1, Viols1)
      ; true ).   % D is a permission (no violation) -> chain ends here

% violation literal of a deontic literal (non-modal proposition that breaches it)
mm_viol([lit, S, 'O', T, F, A], [lit, S2, none, T, F, A]) :- mm_flip(S, S2).
mm_viol([lit, S, 'F', T, F, A], [lit, S,  none, T, F, A]).

%% Add a rule: ground rules are compiled straight into the ground space
%% (constants constraints folded); var rules go to the theory space for the
%% MeTTa grounding fixpoint. All ground literals are registered as ulits.
mm_add_rule(TS, GS, HS, SS, Label, Kind, Body, Head) :-
    add_sexp(TS, [rule, Label, Kind, Body, Head]),
    ( ground([Body, Head])
    -> mm_fold_constraints(Body, LogicBody, Ok),
       ( Ok == true -> FinalBody = LogicBody
       ; FinalBody = [[lit, pos, none, none, '%never%', []]] ),
       add_sexp(GS, [grule, Label, Kind, FinalBody, Head]),
       mm_herb_add(HS, Head),
       mm_ulit_add(SS, Head),
       forall(( member(L, FinalBody), L = [lit|_] ), mm_ulit_add(SS, L))
    ;  true ).   % var rules contribute to the universe ONLY via their actual
                 % ground instances (emitted by mm_ground) — pre-adding a ground
                 % head here would put literals like a never-firing rule's head
                 % into the universe, but grounding only admits literals that
                 % actually occur in some derivable instance.

%% Evaluate constant constraints; keep logic literals only.
mm_fold_constraints([], [], true).
mm_fold_constraints([[lit|L] | R], [[lit|L] | R1], Ok) :- !, mm_fold_constraints(R, R1, Ok).
mm_fold_constraints([[acmp, Op, L, Rx] | R], R1, Ok) :- !,
    ( mm_acmp(Op, L, Rx, true) -> mm_fold_constraints(R, R1, Ok) ; R1 = [], Ok = false ).
mm_fold_constraints([[tcmp, Op, L, Rx] | R], R1, Ok) :- !,
    ( mm_tcmp(Op, L, Rx, true) -> mm_fold_constraints(R, R1, Ok) ; R1 = [], Ok = false ).
mm_fold_constraints([[abind, V, Ax] | R], R1, Ok) :- !,
    ( mm_ax_eval(Ax, Val), V == Val -> mm_fold_constraints(R, R1, Ok)
    ; R1 = [], Ok = false ).
mm_fold_constraints([_ | R], R1, Ok) :- mm_fold_constraints(R, R1, Ok).

mm_herb_add(HS, L) :-
    ( call_sexp(HS, [ha, L]) -> true ; add_sexp(HS, [ha, L]) ).
mm_ulit_add(SS, L) :-
    ( call_sexp(SS, [ulit, L]) -> true ; add_sexp(SS, [ulit, L]) ).

call_sexp(Space, [Rel|Args]) :- Term =.. [Space, Rel | Args], catch(Term, _, fail), !.

%% Body normalization: (and a b c) -> items; single item -> [item].
mm_body([and | Items], Body) :- !, maplist(mm_body_item, Items, Body).
mm_body(X, [Item]) :- mm_body_item(X, Item).

mm_body_item([bind, V, Ax], [abind, V, Ax1]) :- var(V), !, mm_ax(Ax, Ax1).
mm_body_item([Op, L, R], [acmp, Op, L1, R1]) :- atom(Op), mm_cmp_op(Op, _), !,
    mm_ax(L, L1), mm_ax(R, R1).
mm_body_item([Rel, L, R], [tcmp, Rel, L, R]) :- atom(Rel), mm_allen(Rel), !.
mm_body_item(X, Lit) :- mm_lit(X, Lit).

%% Allen interval relation: L and R bind to interval handles [iv, S, E] (from
%% (during LIT ?T) body literals). Implements all 13 Allen interval relations.
%% Returns true/false (fail-free) so it gates grounding like a comparison.
mm_tcmp(Rel, L, R, Out) :-
    once(( ( mm_iallen(Rel, L, R) -> Out = true ; Out = false ) )).

% T = [iv,T1,T2], S = [iv,S1,S2]; mm_tp_lt strict, mm_tp_eq equality (inf-aware)
mm_iallen(before,         [iv,_,T2],  [iv,S1,_])  :- mm_tp_lt(T2, S1).
mm_iallen(after,          [iv,T1,_],  [iv,_,S2])  :- mm_tp_lt(S2, T1).
mm_iallen(meets,          [iv,_,T2],  [iv,S1,_])  :- mm_tp_eq(T2, S1).
mm_iallen('met-by',       [iv,T1,_],  [iv,_,S2])  :- mm_tp_eq(T1, S2).
mm_iallen(overlaps,       [iv,T1,T2], [iv,S1,S2]) :- mm_tp_lt(T1,S1), mm_tp_lt(S1,T2), mm_tp_lt(T2,S2).
mm_iallen('overlapped-by',[iv,T1,T2], [iv,S1,S2]) :- mm_tp_lt(S1,T1), mm_tp_lt(T1,S2), mm_tp_lt(S2,T2).
mm_iallen(starts,         [iv,T1,T2], [iv,S1,S2]) :- mm_tp_eq(T1,S1), mm_tp_lt(T2,S2).
mm_iallen('started-by',   [iv,T1,T2], [iv,S1,S2]) :- mm_tp_eq(T1,S1), mm_tp_lt(S2,T2).
mm_iallen(within,         [iv,T1,T2], [iv,S1,S2]) :- mm_tp_lt(S1,T1), mm_tp_lt(T2,S2).
mm_iallen(contains,       [iv,T1,T2], [iv,S1,S2]) :- mm_tp_lt(T1,S1), mm_tp_lt(S2,T2).
mm_iallen(finishes,       [iv,T1,T2], [iv,S1,S2]) :- mm_tp_eq(T2,S2), mm_tp_lt(S1,T1).
mm_iallen('finished-by',  [iv,T1,T2], [iv,S1,S2]) :- mm_tp_eq(T2,S2), mm_tp_lt(T1,S1).
mm_iallen(equals,         [iv,T1,T2], [iv,S1,S2]) :- mm_tp_eq(T1,S1), mm_tp_eq(T2,S2).

%% Timepoint order: ninf below, pinf above every moment.
mm_tp_le(ninf, _, true) :- !.
mm_tp_le(_, pinf, true) :- !.
mm_tp_le(pinf, X, R) :- !, ( X == pinf -> R = true ; R = false ).
mm_tp_le(X, ninf, R) :- !, ( X == ninf -> R = true ; R = false ).
mm_tp_le(A, B, R) :- number(A), number(B), ( A =< B -> R = true ; R = false ).

mm_tp_eq(A, B) :- mm_tp_le(A, B, true), mm_tp_le(B, A, true).
mm_tp_lt(A, B) :- mm_tp_le(A, B, true), \+ mm_tp_eq(A, B).

%% Arithmetic expression normalization -> [ax, Op, Args] tree.
mm_ax(X, X) :- ( var(X) ; number(X) ), !.
mm_ax([Op | Args], [ax, Op, Args1]) :- atom(Op), mm_ax_op(Op), !,
    maplist(mm_ax, Args, Args1).
mm_ax(X, X).

mm_ax_op('+'). mm_ax_op('-'). mm_ax_op('*'). mm_ax_op('/'). mm_ax_op(div).
mm_ax_op(rem). mm_ax_op('**'). mm_ax_op(abs). mm_ax_op(min). mm_ax_op(max).

%% Literal normalization to the 6-slot functor [lit, Sign, Mode, Temporal, Functor, Args]
%% — the canonical literal record (negation, deontic mode, temporal qualifier,
%% predicate name, argument list).
%%   Sign     : pos | neg               (classical negation)
%%   Mode     : none | 'O' | 'P' | 'F'  (deontic must/may/forbidden)
%%   Temporal : none | [iv, Start, End] (Start/End: ninf | pinf | int | var)
%% Modal and temporal wrappers compose; matching/identity then falls out of
%% the structure (two lits differing in any slot are distinct atoms).
mm_lit([not, L], [lit, S2, M, T, F, A]) :- !,
    mm_lit(L, [lit, S, M, T, F, A]), mm_flip(S, S2).
mm_lit([must, L], [lit, S, 'O', T, F, A]) :- !, mm_lit(L, [lit, S, _, T, F, A]).
mm_lit([may, L], [lit, S, 'P', T, F, A]) :- !, mm_lit(L, [lit, S, _, T, F, A]).
mm_lit([forbidden, L], [lit, S, 'F', T, F, A]) :- !, mm_lit(L, [lit, S, _, T, F, A]).
% (during LIT S E) — explicit interval bounds (the form facts use).
mm_lit([during, L, S0, E0], [lit, Sg, M, [iv, S1, E1], F, A]) :- !,
    mm_lit(L, [lit, Sg, M, _, F, A]),
    mm_tp(S0, S1), mm_tp(E0, E1).
% (during LIT ?T) — interval-variable form (rule bodies): the temporal slot is
% the interval handle ?T, which unifies with the matched fact's [iv,S,E] during
% grounding and is then read by the Allen relation. This is the interval-variable
% binding mechanism. The handle may also be an already-built [iv,S,E].
mm_lit([during, L, T], [lit, Sg, M, T, F, A]) :- !,
    mm_lit(L, [lit, Sg, M, _, F, A]).
mm_lit(X, [lit, pos, none, none, X, []]) :- atom(X), !.
mm_lit([F | Args], [lit, pos, none, none, F, Args]) :- atom(F), \+ mm_reserved(F), !.
mm_lit(_, _) :- fail.

mm_flip(pos, neg). mm_flip(neg, pos).

%% TimePoint normalization. inf/-inf are sentinels; (moment "RFC3339") -> millis.
mm_tp(V, V) :- var(V), !.
mm_tp(inf, pinf) :- !.
mm_tp('-inf', ninf) :- !.
mm_tp(N, N) :- number(N), !.
mm_tp([moment, S], Ms) :- !,
    ( atom(S) -> A = S ; atom_string(A, S) ),
    ( parse_time(A, iso_8601, Epoch) -> Ms is round(Epoch * 1000) ; Ms = A ).
mm_tp(X, X).

mm_reserved(F) :- mm_ax_op(F).
mm_reserved(F) :- mm_cmp_op(F, _).
mm_reserved(F) :- mm_allen(F).
mm_reserved(and). mm_reserved(not). mm_reserved(bind).
mm_reserved(must). mm_reserved(may). mm_reserved(forbidden). mm_reserved(during).
mm_reserved(given). mm_reserved(always). mm_reserved(normally).
mm_reserved(except). mm_reserved(prefer). mm_reserved(meta).
mm_reserved(otherwise). mm_reserved(deadline).
mm_reserved(happens). mm_reserved(initiates). mm_reserved(terminates).

% deadline times: (... S E) or (... S E Sanction)
mm_dl_times([S, E], S, E, none).
mm_dl_times([S, E, Sanc], S, E, Sanc).

%% The 13 Allen interval relations (body constraints over interval handles).
mm_allen(before). mm_allen(after). mm_allen(meets). mm_allen('met-by').
mm_allen(overlaps). mm_allen('overlapped-by'). mm_allen(starts). mm_allen('started-by').
mm_allen(within). mm_allen(contains). mm_allen(finishes). mm_allen('finished-by').
mm_allen(equals).

%% Convert MeTTa ?vars to fresh shared Prolog vars (one map per call).
mm_planvars(In, Out) :- once(mm_planv(In, Out, [], _)).
mm_planv(X, V, M0, M) :- atom(X), atom_concat('?', _, X), !,
    ( memberchk(X-V, M0) -> M = M0 ; M = [X-V | M0] ).
mm_planv(X, X, M, M) :- \+ is_list(X), !.
mm_planv([], [], M, M) :- !.
mm_planv([H|T], [H1|T1], M0, M) :- mm_planv(H, H1, M0, M1), mm_planv(T, T1, M1, M).

%%% ----------------------------------------------------------------------
%%% Output formatting
%%% ----------------------------------------------------------------------

%% [lit, Sign, Mode, Temporal, Functor, Args] -> canonical display string:
%%   "f", "~f", "f(a, b)", "[O]pay", "meeting[10,20]", "ev(a)[10,20]"
%% (the literal rendering used by the CLI and the golden tests).
mm_lit_str(Lit, Str) :- once(mm_lit_str_(Lit, Str)).
mm_lit_str_([lit, S, M, T, F, Args], Str) :-
    ( Args == [] -> Core = F
    ; maplist(mm_arg_str, Args, ArgStrs),
      atomic_list_concat(ArgStrs, ', ', Joined),
      format(atom(Core), "~w(~w)", [F, Joined]) ),
    mm_mode_str(M, MS),
    mm_temporal_str(T, TS),
    ( S == neg -> Neg = "~" ; Neg = "" ),
    % mode bracket precedes the proposition negation: [O]~p, not ~[O]p — the
    % deontic mode scopes over the negated proposition. For non-modal lits MS=""
    % so this is just ~p as before.
    format(string(Str), "~w~w~w~w", [MS, Neg, Core, TS]).

mm_mode_str(none, "") :- !.
mm_mode_str(M, S) :- format(string(S), "[~w]", [M]).

mm_temporal_str(none, "") :- !.
mm_temporal_str([iv, A, B], S) :- mm_tp_str(A, AS), mm_tp_str(B, BS),
                                  format(string(S), "[~w,~w]", [AS, BS]).
mm_tp_str(ninf, "-inf") :- !.
mm_tp_str(pinf, "inf") :- !.
mm_tp_str(X, X).

%% Nested args render as S-expressions; scalars verbatim; Decimals keep scale.
mm_arg_str([dec, M, Sc], S) :- !, mm_dec_str(M, Sc, S).
mm_arg_str(A, S) :- ( is_list(A) -> swrite(A, S) ; format(atom(S), "~w", [A]) ).

%% Render a (mantissa, scale) Decimal preserving trailing zeros, e.g.
%% 90/2 -> "0.90", 20/1 -> "2.0", 5/1 -> "0.5", 150/2 -> "1.50".
mm_dec_str(M, Sc, Str) :-
    ( M < 0 -> Sign = '-', Abs is -M ; Sign = '', Abs = M ),
    atom_number(AbsA, Abs), atom_length(AbsA, L0),
    MinLen is Sc + 1,
    ( L0 < MinLen -> PadN is MinLen - L0, mm_zeros(PadN, Z), atom_concat(Z, AbsA, Digs)
    ; Digs = AbsA ),
    atom_length(Digs, L), Ip is L - Sc,
    sub_atom(Digs, 0, Ip, _, IntPart),
    sub_atom(Digs, Ip, Sc, _, FracPart),
    atomic_list_concat([Sign, IntPart, '.', FracPart], Str).
mm_zeros(0, '') :- !.
mm_zeros(N, Z) :- N > 0, N1 is N - 1, mm_zeros(N1, Z1), atom_concat('0', Z1, Z).

mm_tag_str(pD, "+D"). mm_tag_str(nD, "-D"). mm_tag_str(pd, "+d"). mm_tag_str(nd, "-d").

%% [tconcl Tag Lit Trust Sources] -> "+D rain (trust: 0.90) [alice]"
%% (the trust-annotated conclusion line format; sources omitted when empty).
mm_trust_str([tconcl, Tag, Lit, Trust, Sources], Str) :-
    once(( mm_tag_str(Tag, TS), mm_lit_str(Lit, LS),
           T is float(Trust),
           ( Sources == [] -> SS = ""
           ; atomic_list_concat(Sources, ', ', SJoin),
             format(string(SS), " [~w]", [SJoin]) ),
           format(string(Str), "~w ~w (trust: ~2f)~w", [TS, LS, T, SS]) )).

%% [Tag, Lit] -> "  +D penguin" style line.
mm_concl_str([Tag, Lit], Str) :-
    once(( mm_tag_str(Tag, TS), mm_lit_str(Lit, LS),
           format(string(Str), "~w ~w", [TS, LS]) )).
