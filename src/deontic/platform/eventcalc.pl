% Event-Calculus support primitives. The EC engine (interval amalgamation,
% holdsAt, violation) now lives in idiomatic MeTTa — src/deontic/eventcalc.metta.
% Prolog provides only: parsing a deontic-literal s-expr to the 6-slot lit, and
% the timeline table formatter (MeTTa builds the structured rows).

% parse a deontic-literal s-expr (e.g. (must pay)) to the 6-slot lit (mm_lit in io.pl)
mm_dlit(M, Lit) :- once(mm_lit(M, Lit)).

% Render the obligation timeline. Rows = [[LitStr, Intervals, StatusSym], ...]
% with Intervals = [[S,E], ...] (E may be the atom inf) and Status active|inactive.
mm_print_timeline2(Now, Rows, true) :-
    once(( with_output_to(string(O), (
             format("Obligation Timeline (now=~w)~n", [Now]),
             format("===========================~n", []),
             ( Rows == [] -> format("  (no event-driven obligations)~n", [])
             ; forall(member([L, Ints, St], Rows),
                 ( mm_ec_ivs(Ints, IvS), mm_ec_stat(St, StS),
                   format("  ~w: ~w  [~w]~n", [L, IvS, StS]) )) ) )),
           write(O) )).

mm_ec_ivs([], "never in force").
mm_ec_ivs([I|Is], S) :- maplist(mm_ec_iv, [I|Is], Ss), atomic_list_concat(Ss, ", ", S).
mm_ec_iv([Sa, inf], A) :- !, format(atom(A), "[~w,inf)", [Sa]).
mm_ec_iv([Sa, E], A) :- format(atom(A), "[~w,~w)", [Sa, E]).

mm_ec_stat(active, "in force (undischarged)") :- !.
mm_ec_stat(_, "discharged/inactive").
