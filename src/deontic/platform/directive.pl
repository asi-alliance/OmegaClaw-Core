%%% Task-coordination kernel: literal-name conventions, version scanning, and
%%% chain-cancellation block generation ('-' separator format) for the
%%% claim/unclaim/block/unblock/complete lifecycle.
%%% All exported predicates are deterministic (once/1).

%% ---- name helpers ----

% strip leading task- / task_ if present
dir_strip_task(Raw, Task) :-
    once(( ( atom_concat('task-', T, Raw) ; atom_concat('task_', T, Raw) )
           -> Task = T ; Task = Raw )).

% compose PREFIX-TASK
dir_lit(Prefix, Task, Lit) :- once(atomic_list_concat([Prefix, '-', Task], Lit)).

% decompose NAME into Prefix-Task (accepts - or _ separator); fails cleanly -> 'nil
dir_prefix_task(Name, Prefix, Task) :-
    once(( ( atom_concat(Prefix, Rest, Name),
             ( atom_concat('-', T, Rest) ; atom_concat('_', T, Rest) ) )
           -> Task = T ; Task = nil )).

% parse an assignment name with context: returns [Task, Agent] or nil
dir_parse_assignment(Name, KnownTasks, Out) :-
    once(dir_parse_assignment_(Name, KnownTasks, Out)).
dir_parse_assignment_(Name, Known, Out) :-
    ( atom_concat('assignTo_', Rest, Name)
      -> atomic_list_concat(Segs, '_', Rest),
         ( Segs = [_,_|_] -> append(TaskSegs, [Agent], Segs),
                             atomic_list_concat(TaskSegs, '_', Task),
                             Out = [Task, Agent]
         ; Segs = [T] -> Out = [T, '']
         ; Out = nil )
    ; atom_concat('assign-to-', Rest, Name) -> dir_kebab_assignment(Rest, Known, Out)
    ; atom_concat('assign-', Rest, Name)    -> dir_kebab_assignment(Rest, Known, Out)
    ; Out = nil ).

dir_kebab_assignment(Rest, Known, Out) :-
    ( is_list(Known), Known \= [],
      findall(L-T, ( member(T, Known), atom(T),
                     atom_concat(T, Suffix, Rest), atom_concat('-', _, Suffix),
                     atom_length(T, L) ), Cands0),
      sort(0, @>=, Cands0, [_-Task|_])
      -> atom_concat(Task, Suffix1, Rest), atom_concat('-', Agent, Suffix1),
         Agent \= '', Out = [Task, Agent]
    ;  atomic_list_concat(Segs, '-', Rest),
       ( Segs = [_,_|_] -> append(TaskSegs, [Agent], Segs),
                           atomic_list_concat(TaskSegs, '-', Task),
                           Out = [Task, Agent]
       ; Segs = [T] -> Out = [T, '']
       ; Out = nil ) ).

%% ---- version scanning (find_versions) ----
%% Names: list of positive literal-name atoms.
%% Out = [MaxVer, Last, MaxActionVer, MaxCounterVer]; Last in {action, counter, none}
dir_find_versions(Names, Action, Counter, Task, Out) :-
    once(( findall(V, ( member(N, Names), dir_ver_of(N, Action, Task, V) ), AVs),
           findall(V, ( member(N, Names), dir_ver_of(N, Counter, Task, V) ), CVs),
           max_list([0|AVs], MA), max_list([0|CVs], MC),
           MaxVer is max(MA, MC),
           ( MaxVer =:= 0 -> Last = none
           ; MA >= MC -> Last = action
           ; Last = counter ),
           Out = [MaxVer, Last, MA, MC] )).

% NAME =?= ACTION-vN-TASK
dir_ver_of(Name, Action, Task, V) :-
    atom_concat(Action, Rest0, Name),
    atom_concat('-v', Rest1, Rest0),
    atom_concat(VA, Rest2, Rest1),
    atom_concat('-', Task, Rest2),
    atom_number(VA, V), integer(V), V >= 0.

%% ---- chain-cancellation block generation ----

dir_label_prefix(claim, 'cl-'). dir_label_prefix(unclaim, 'ucl-').
dir_label_prefix(block, 'bl-'). dir_label_prefix(unblock, 'ubl-').
dir_label_prefix(_, '').

% generate_action_block; PrevCounterVer = -1 when none.
dir_action_block(Agent, Ts, Task, NewVer, PrevCounterVer,
              Action, State, CounterState, CounterAction, Block) :-
    once(( dir_label_prefix(Action, P), dir_label_prefix(CounterAction, CP),
           format(string(Hdr), "~n(claims agent:~w~n  :at \"~w\"", [Agent, Ts]),
           format(string(L1), "~n  (given ~w-v~w-~w)", [Action, NewVer, Task]),
           format(string(L2), "~n  (normally r-~wstate-v~w-~w ~w-v~w-~w state-~w-v~w-~w)",
                  [P, NewVer, Task, Action, NewVer, Task, State, NewVer, Task]),
           format(string(L3), "~n  (normally r-~wchain-v~w-~w state-~w-v~w-~w ~w-~w)",
                  [P, NewVer, Task, State, NewVer, Task, State, Task]),
           ( PrevCounterVer >= 0
             -> format(string(L4), "~n  (normally r-~wcancel-v~w-~w ~w-v~w-~w (not state-~w-v~w-~w))",
                       [P, PrevCounterVer, Task, Action, NewVer, Task, CounterState, PrevCounterVer, Task]),
                format(string(L5), "~n  (prefer r-~wcancel-v~w-~w r-~wstate-v~w-~w)",
                       [P, PrevCounterVer, Task, CP, PrevCounterVer, Task]),
                format(string(L6), "~n  (prefer r-~wchain-v~w-~w r-~w~w-v~w-~w)",
                       [P, NewVer, Task, CP, CounterState, PrevCounterVer, Task]),
                Tail = [L4, L5, L6]
             ;  Tail = [] ),
           append([[Hdr, L1, L2, L3], Tail, [")\n"]], Parts),
           atomics_to_string(Parts, Block) )).

% generate_counter_block; PrevActionVer = -1 when none.
dir_counter_block(Agent, Ts, Task, NewVer, PrevActionVer,
               Counter, CounterState, ActionState, NegLit, Action, Block) :-
    once(( dir_label_prefix(Counter, CP), dir_label_prefix(Action, P),
           format(string(Hdr), "~n(claims agent:~w~n  :at \"~w\"", [Agent, Ts]),
           format(string(L1), "~n  (given ~w-v~w-~w)", [Counter, NewVer, Task]),
           format(string(L2), "~n  (normally r-~wstate-v~w-~w ~w-v~w-~w state-~w-v~w-~w)",
                  [CP, NewVer, Task, Counter, NewVer, Task, CounterState, NewVer, Task]),
           ( PrevActionVer >= 0
             -> format(string(L3), "~n  (normally r-~wcancel-v~w-~w ~w-v~w-~w (not state-~w-v~w-~w))",
                       [CP, PrevActionVer, Task, Counter, NewVer, Task, ActionState, PrevActionVer, Task]),
                format(string(L4), "~n  (prefer r-~wcancel-v~w-~w r-~wstate-v~w-~w)",
                       [CP, PrevActionVer, Task, P, PrevActionVer, Task]),
                Mid = [L3, L4]
             ;  Mid = [] ),
           format(string(L5), "~n  (normally r-~w~w-v~w-~w ~w-v~w-~w (not ~w-~w))",
                  [CP, CounterState, NewVer, Task, Counter, NewVer, Task, NegLit, Task]),
           ( PrevActionVer >= 0
             -> format(string(L6), "~n  (prefer r-~w~w-v~w-~w r-~wchain-v~w-~w)",
                       [CP, CounterState, NewVer, Task, P, PrevActionVer, Task]),
                Tail = [L6]
             ;  Tail = [] ),
           append([[Hdr, L1, L2], Mid, [L5], Tail, [")\n"]], Parts),
           atomics_to_string(Parts, Block) )).

% completion claims block
dir_complete_block(Agent, Ts, Task, Block) :-
    once(format(string(Block),
        "~n(claims agent:~w~n  :at \"~w\"~n  (given completed-~w))~n",
        [Agent, Ts, Task])).

% wrap MeTTa text in an attributed claims block
dir_assert_block(Agent, Ts, FormText, Block) :-
    once(format(string(Block),
        "~n(claims agent:~w~n  :at \"~w\"~n  ~w)~n",
        [Agent, Ts, FormText])).

%% ---- failure propagation (generate_propagation_rules) ----
%% Scans the theory space for readiness rules:
%%   (rule _ _ Body [lit,pos,ready-T,_]) with [lit,pos,completed-D,_] in Body
%% reverse map: D -> dependents Ts. Emits one block of propagation rules so that
%% a failure in an upstream task blocks its downstream dependents (transitively).

dir_reverse_deps(TheorySp, Reverse) :-
    findall(Dep-T,
            ( call_sexp_h(TheorySp, [rule, _, Kind, Body, [lit, pos, _, _, Head, _]]),
              Kind \= fact,
              dir_prefix_task(Head, ready, T), T \= nil,
              member([lit, pos, _, _, BL, _], Body),
              dir_prefix_task(BL, completed, Dep), Dep \= nil ),
            Pairs0),
    sort(Pairs0, Pairs),
    findall(D-Ts, ( member(D-_, Pairs), \+ (member(D2-_, Pairs), D2 == D, fail),
                    findall(T, member(D-T, Pairs), Ts0), sort(Ts0, Ts) ), Rev0),
    sort(Rev0, Reverse).

call_sexp_h(Space, [Rel|Args]) :- Term =.. [Space, Rel|Args], catch(Term, _, fail).

dir_existing_labels(TheorySp, Labels) :-
    findall(L, call_sexp_h(TheorySp, [rule, L, _, _, _]), Ls),
    sort(Ls, Labels).

dir_propagation_block(TheorySp, Task, Ver, Block) :-
    once(( dir_reverse_deps(TheorySp, Reverse),
           ( member(Task-Dependents, Reverse)
             -> dir_existing_labels(TheorySp, Existing),
                format(string(Hd), "~n;; Propagation rules: failures in '~w' block downstream tasks~n", [Task]),
                findall(S, ( member(Dep, Dependents),
                             dir_prop_lines(Task, Dep, Ver, Existing, S) ), Per),
                dir_transitive_lines(Reverse, Task, Dependents, Existing, TransLines),
                append([[Hd], Per, TransLines], Parts),
                atomics_to_string(Parts, Block)
             ;  Block = "" ) )).

dir_prop_lines(Task, Dep, Ver, Existing, S) :-
    format(atom(L1l), "r-propagate-~w-from-~w-failed", [Dep, Task]),
    ( memberchk(L1l, Existing) -> S1 = ""
    ; format(string(S1), "(normally ~w failed-~w upstream-blocked-~w)~n", [L1l, Task, Dep]) ),
    format(atom(L2l), "r-propagate-~w-from-~w-permanently-failed", [Dep, Task]),
    ( memberchk(L2l, Existing) -> S2 = ""
    ; format(string(S2), "(normally ~w permanently-failed-~w upstream-blocked-~w)~n", [L2l, Task, Dep]) ),
    format(string(S3), "(normally r-propagate-~w-from-~w-stale-v~w stale-v~w-~w upstream-blocked-~w)~n",
           [Dep, Task, Ver, Ver, Task, Dep]),
    format(string(S4), "(normally r-propagate-~w-from-~w-timeout-v~w timeout-v~w-~w upstream-blocked-~w)~n",
           [Dep, Task, Ver, Ver, Task, Dep]),
    format(atom(L5l), "r-propagate-~w-from-~w-blocked", [Dep, Task]),
    ( memberchk(L5l, Existing) -> S5 = ""
    ; format(string(S5), "(normally ~w upstream-blocked-~w upstream-blocked-~w)~n", [L5l, Task, Dep]) ),
    atomics_to_string([S1, S2, S3, S4, S5], S).

dir_transitive_lines(Reverse, Task, Direct, Existing, Lines) :-
    dir_bfs(Reverse, Direct, [Task|Direct], Existing, [], Lines0),
    ( Lines0 == [] -> Lines = []
    ; format(string(THdr), "~n;; Transitive propagation: upstream-blocked cascades through dependency chain~n", []),
      Lines = [THdr | Lines0] ).

dir_bfs(_, [], _, _, Acc, Lines) :- reverse(Acc, Lines).
dir_bfs(Reverse, [Cur|Queue], Visited, Existing, Acc, Lines) :-
    ( member(Cur-NextDeps, Reverse) -> true ; NextDeps = [] ),
    foldl(dir_bfs_edge(Cur, Existing), NextDeps, Acc-Queue-Visited, Acc1-Queue1-Visited1),
    dir_bfs(Reverse, Queue1, Visited1, Existing, Acc1, Lines).

dir_bfs_edge(Cur, Existing, Next, Acc-Q-V, Acc1-Q1-V1) :-
    format(atom(Lbl), "r-propagate-~w-from-~w-blocked", [Next, Cur]),
    ( memberchk(Lbl, Existing)
      -> Acc1 = Acc
      ;  format(string(S), "(normally ~w upstream-blocked-~w upstream-blocked-~w)~n", [Lbl, Cur, Next]),
         Acc1 = [S|Acc] ),
    ( memberchk(Next, V) -> Q1 = Q, V1 = V ; append(Q, [Next], Q1), V1 = [Next|V] ).
