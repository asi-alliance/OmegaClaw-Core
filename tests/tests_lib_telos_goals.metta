!(import! &self ./tests/lib/utils)
!(import! &self ../src/helper.py)
!(import! &self ./src/utils)
!(import! &self ./src/skills)
!(import! &self ./src/loop)
!(import! &self ./lib_telos_goals)

; Fixture: the atoms an agent would assert through the metta skill.
(goal alice-train     individual alice active)
(goal bob-share       individual bob   active)
(goal old-rust        individual alice abandoned)
(goal grant           individual alice achieved)
(goal dao-fair-access collective dao   active)
(goal gpu-quota       collective dao   proposed)
(rel conflicts  alice-train bob-share)
(rel supports   bob-share   dao-fair-access)
(rel depends-on dao-fair-access gpu-quota)
(rel subsumes   dao-fair-access gpu-quota)

; ---- Zero-arity lenses ----

!(test (expression-count-item (collapse (telos-conflicts)) (conflict-between alice-train bob-share)) 1)
!(test (expression-count-item (collapse (telos-conflicts)) (conflict-between bob-share alice-train)) 0)

!(test (expression-count-item (collapse (telos-collective-goals)) (collective-goal dao-fair-access dao)) 1)
!(test (expression-count-item (collapse (telos-collective-goals)) (collective-goal gpu-quota dao)) 1)
!(test (expression-count-item (collapse (telos-collective-goals)) (collective-goal alice-train alice)) 0)

!(test (expression-count-item (collapse (telos-achieved-goals)) (achieved-goal grant alice)) 1)
!(test (expression-count-item (collapse (telos-achieved-goals)) (achieved-goal alice-train alice)) 0)

!(test (expression-count-item (collapse (telos-abandoned-goals)) (abandoned-goal old-rust alice)) 1)
!(test (expression-count-item (collapse (telos-abandoned-goals)) (abandoned-goal grant alice)) 0)

; (rel subsumes <parent> <child>) reads parent then child.
!(test (expression-count-item (collapse (telos-subgoals)) (subgoal gpu-quota of dao-fair-access)) 1)
!(test (expression-count-item (collapse (telos-subgoals)) (subgoal dao-fair-access of gpu-quota)) 0)

; dao-fair-access depends on gpu-quota, which is only proposed, so it is blocked.
!(test (expression-count-item (collapse (telos-blocked)) (blocked dao-fair-access on gpu-quota)) 1)

!(test (expression-count-item (collapse (telos-aligned)) (aligns bob-share with dao-fair-access)) 1)
!(test (expression-count-item (collapse (telos-aligned)) (aligns alice-train with dao-fair-access)) 0)

; ---- Parameterised probes ----

!(test (expression-count-item (collapse (telos-goals-of alice)) (goal-of alice alice-train)) 1)
!(test (expression-count-item (collapse (telos-goals-of alice)) (goal-of alice old-rust)) 1)
!(test (expression-count-item (collapse (telos-goals-of alice)) (goal-of alice bob-share)) 0)
!(test (expression-count-item (collapse (telos-goals-of dao)) (goal-of dao dao-fair-access)) 0)

!(test (telos-achieved grant) True)
!(test (collapse (telos-achieved alice-train)) ())

; ---- The full reading includes every zero-arity lens ----

!(test (expression-count-item (collapse (telos-reading)) (conflict-between alice-train bob-share)) 1)
!(test (expression-count-item (collapse (telos-reading)) (collective-goal dao-fair-access dao)) 1)
!(test (expression-count-item (collapse (telos-reading)) (achieved-goal grant alice)) 1)
!(test (expression-count-item (collapse (telos-reading)) (abandoned-goal old-rust alice)) 1)
!(test (expression-count-item (collapse (telos-reading)) (subgoal gpu-quota of dao-fair-access)) 1)
!(test (expression-count-item (collapse (telos-reading)) (blocked dao-fair-access on gpu-quota)) 1)
!(test (expression-count-item (collapse (telos-reading)) (aligns bob-share with dao-fair-access)) 1)

; ---- Prompt extension round trip (the agent-integration hook) ----

!(test (progn
         (telos-enable)
         (contains-text (getPromptExtensions) "GOAL GRAPH"))
       True)

!(test (progn
         (telos-disable)
         (contains-text (getPromptExtensions) "GOAL GRAPH"))
       False)
