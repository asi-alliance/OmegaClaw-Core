; lib_telos_goals -- optional goal-graph module for Omega. Not loaded by lib_omega.metta.
; Load with:  !(import! &self (library Omega lib_telos_goals))
; Reference:  docs/reference-lib-telos-goals.md
;
; Omega does not infer or assert goal atoms by itself. The LLM layer asserts them through
; the `metta` skill (metta (add-atom &self (goal ...))) and reads them back through the
; lenses below; (telos-enable) installs a prompt extension that tells the LLM how.
;
; Schema (all relations read src -> dst):
;   (goal <id> <scope> <owner> <status>)   scope:  individual | collective
;                                          status: active | proposed | achieved | abandoned
;   (rel supports   <src> <dst>)           achieving src advances dst
;   (rel conflicts  <src> <dst>)           src and dst cannot both be achieved (assert once)
;   (rel subsumes   <parent> <child>)      parent is the broader goal, child is a sub-goal of it
;   (rel depends-on <src> <dst>)           src cannot progress until dst is achieved

; ---- Zero-arity lenses: every one of these is included in (telos-reading) ----

; All conflict pairs the agent must surface (across ALL goals).
(= (telos-conflicts)
   (match &self (rel conflicts $a $b) (conflict-between $a $b)))

; Every collective goal (what the commons wants).
(= (telos-collective-goals)
   (match &self (goal $g collective $owner $status) (collective-goal $g $owner)))

; Every achieved goal, any scope, any owner.
(= (telos-achieved-goals)
   (match &self (goal $g $scope $owner achieved) (achieved-goal $g $owner)))

; Every abandoned goal. Surfacing these stops the agent chasing a goal its owner dropped.
(= (telos-abandoned-goals)
   (match &self (goal $g $scope $owner abandoned) (abandoned-goal $g $owner)))

; Sub-goal structure: (rel subsumes <parent> <child>) yields (subgoal <child> of <parent>).
(= (telos-subgoals)
   (match &self (rel subsumes $parent $child) (subgoal $child of $parent)))

; BLOCKED: a goal that depends-on another goal that is not yet achieved.
; An abandoned dependency still blocks: it will never become achieved.
(= (telos-blocked)
   (match &self (rel depends-on $g $dep)
      (match &self (goal $dep $s2 $o2 $st2)
         (if (== $st2 achieved) (empty) (blocked $g on $dep)))))

; Cross-level ALIGNMENT: an individual goal that SUPPORTS a collective goal.
(= (telos-aligned)
   (match &self (rel supports $i $c)
      (match &self (goal $i individual $o1 $s1)
         (match &self (goal $c collective $o2 $s2)
            (aligns $i with $c)))))

; The full goal reading: the superposition of every zero-arity lens above.
; The parameterised probes below (telos-goals-of, telos-achieved) take an owner or a goal
; id, so they are queried on their own rather than folded into the reading.
(= (telos-reading)
   (superpose ((telos-conflicts)
               (telos-collective-goals)
               (telos-achieved-goals)
               (telos-abandoned-goals)
               (telos-subgoals)
               (telos-blocked)
               (telos-aligned))))

; ---- Parameterised probes: not part of (telos-reading) ----

; Goals owned by ANY given stakeholder (individual goal understanding).
(= (telos-goals-of $owner)
   (match &self (goal $g individual $owner $status) (goal-of $owner $g)))

; A goal is ACHIEVED when its status atom says so.
(= (telos-achieved $g)
   (match &self (goal $g $scope $owner achieved) True))

; ---- Agent integration (opt-in; nothing here runs at import) ----

; Teach the LLM the schema and the metta-skill calls that populate and read the graph.
; Uses the core prompt-extension hook from src/skills.metta; no effect until called.
(= (telos-enable)
   (add-prompt-extension telos-goals
     "GOAL GRAPH: when a message reveals what someone wants, record it as atoms and reason over them symbolically instead of guessing. Assert a goal with: metta (add-atom &self (goal <id> <individual or collective> <owner> <active or proposed or achieved or abandoned>)). Assert a relation with: metta (add-atom &self (rel <supports or conflicts or subsumes or depends-on> <src> <dst>)); subsumes reads parent then child, depends-on reads goal then prerequisite. Read the graph with: metta (telos-reading) for every lens, or metta (telos-conflicts), metta (telos-blocked), metta (telos-aligned), metta (telos-goals-of <owner>). Tell the user about every conflict-between and blocked result before acting on a goal."))

; Remove the extension again.
(= (telos-disable)
   (remove-prompt-extension telos-goals))
