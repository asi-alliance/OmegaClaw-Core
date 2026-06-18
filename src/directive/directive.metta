; Task-coordination core: extraction, next-actions, status/board/summary, and
; the claim/unclaim/block/unblock/complete lifecycle. Commands return structured
; result tuples; the CLI layer formats them. Plan mutations are append-only
; blocks of claims (facts + defeasible rules); a later re-reason resolves them,
; so state transitions are monotone appends with non-monotonic effect (the block
; generators live in the task-coordination kernel, platform/directive.pl).

; --- positive plain (no mode/temporal) 0-arity literal names from the state ---
(= (directive-pos-names)
   (collapse (let $q (ulit-gen)
     (let (lit $s $m $t $f $a) $q
       (if (and (== (pos? $q) True)
                (and (== $s pos) (and (== $m none) (== $t none))))
           $f (empty))))))

; --- prefix extraction (strip a known prefix off a literal name) ---
(= (tasks-with $prefix $names)
   (filter-atom (map-atom $names $n (dir_prefix_task $n $prefix)) $t (not (== $t nil))))

(= (directive-tasks $names)     (unique-atom (tasks-with task $names)))
(= (directive-ready $names)     (unique-atom (tasks-with ready $names)))
(= (directive-completed $names) (unique-atom (tasks-with completed $names)))
(= (directive-claimed $names)   (unique-atom (tasks-with claimed $names)))
(= (directive-blocked $names)   (unique-atom (tasks-with blocked $names)))
(= (directive-upstream $names)  (unique-atom (tasks-with upstream-blocked $names)))
(= (directive-decomposed $names) (unique-atom (tasks-with decomposed $names)))

; --- assignments (extract + parse assignTo-/assign-to- literal names) ---
; $names are pre-filtered to parseable assignment names by directive-assignments
(= (assignments-of $names $known)
   (map-atom $names $n
     (let ($t $a) (dir_parse_assignment $n $known) (assign $t $a $n))))

(= (directive-assignments $names)
   (assignments-of (filter-atom $names $n (== (is-assign-name $n) True))
                   (directive-tasks $names)))

(= (is-assign-name $n)
   (not (== (dir_parse_assignment $n ()) nil)))

; --- next actions ---
; An assignment is actionable iff its task's computed state is `ready` (the
; state-precedence classifier already excludes completed/blocked/upstream/
; decomposed/in-progress), so this reuses directive-task-state instead of
; repeating the five exclusion checks. If nothing is ready, fall back to all
; assignments.
(= (directive-next-actions $names)
   (let $assigns (directive-assignments $names)
     (if (== (directive-ready $names) ())
         $assigns
         (filter-atom $assigns $a
           (let (assign $t $ag $l) $a (== (directive-task-state $t $names) ready))))))

(= (directive-next $path)
   (let* (($_ (dl-run $path))
          ($names (directive-pos-names)))
     (next-actions (sort-atom (directive-next-actions $names)))))

; --- status / board (tasks grouped by lifecycle state) ---
(= (directive-status $path)
   (let* (($_ (dl-run $path))
          ($names (directive-pos-names)))
     (status (tasks (sort-atom (directive-tasks $names)))
             (ready (sort-atom (directive-ready $names)))
             (claimed (sort-atom (directive-claimed $names)))
             (blocked (sort-atom (directive-blocked $names)))
             (upstream-blocked (sort-atom (directive-upstream $names)))
             (completed (sort-atom (directive-completed $names))))))

; --- task state classification (state precedence) ---
;   done > blocked > upstream-blocked > decomposed > in-progress > ready > backlog
(= (directive-task-state $t $names)
   (if (== (is-member $t (directive-completed $names)) True) done
   (if (== (is-member $t (directive-blocked $names)) True) blocked
   (if (== (is-member $t (directive-upstream $names)) True) upstream-blocked
   (if (== (is-member $t (directive-decomposed $names)) True) decomposed
   (if (== (is-member $t (directive-claimed $names)) True) in-progress
   (if (== (is-member $t (directive-ready $names)) True) ready
       backlog)))))))

(= (tasks-in-state $tasks $names $state)
   (sort-atom (filter-atom $tasks $t (== (directive-task-state $t $names) $state))))

; --- board (tasks grouped by state) ---
(= (directive-board $path)
   (let* (($_ (dl-run $path))
          ($names (directive-pos-names))
          ($tasks (directive-tasks $names)))
     (board (backlog (tasks-in-state $tasks $names backlog))
            (ready (tasks-in-state $tasks $names ready))
            (in-progress (tasks-in-state $tasks $names in-progress))
            (blocked (union-atom (tasks-in-state $tasks $names blocked)
                                 (tasks-in-state $tasks $names upstream-blocked)))
            (done (tasks-in-state $tasks $names done)))))

; --- summary (per-state counts + progress %) ---
(= (directive-summary $path)
   (let* (($_ (dl-run $path))
          ($names (directive-pos-names))
          ($tasks (directive-tasks $names))
          ($total (size-atom $tasks))
          ($done (size-atom (tasks-in-state $tasks $names done))))
     (summary (total $total)
              (backlog (size-atom (tasks-in-state $tasks $names backlog)))
              (ready (size-atom (tasks-in-state $tasks $names ready)))
              (in-progress (size-atom (tasks-in-state $tasks $names in-progress)))
              (blocked (+ (size-atom (tasks-in-state $tasks $names blocked))
                          (size-atom (tasks-in-state $tasks $names upstream-blocked))))
              (done $done)
              (progress-pct (mm_pct $done $total)))))

; --- info (extract (meta plan ...) properties) ---
(= (meta-get $kvs $key)
   (case (collapse (let ($k $v) (superpose $kvs) (if (== $k $key) $v (empty))))
     ((($v) $v) (() none))))

(= (plan-meta-kvs)
   (case (once (match &theory (metainfo plan $kvs) $kvs))
     (($kvs $kvs) (Empty ()))))

(= (directive-info $path)
   (let* (($_ (dl-run $path))
          ($kvs (plan-meta-kvs)))
     (if (== $kvs ())
         (info none)
         (info $kvs))))

; --- describe (rule/fact/literal definitions + metadata) ---
(= (describe-one $label)
   (case (once (match &theory (rule $label $kind $body $head) (rule $label $kind $body $head)))
     (((rule $l $k $b $h)
       (described $l (kind $k) (body $b) (head $h) (meta (meta-get-rule $l))))
      (Empty
       (case (once (match &theory (metainfo $label $kvs) $kvs))
         (($kvs (described $label (meta $kvs)))
          (Empty (described $label not-found))))))))

(= (meta-get-rule $label)
   (case (once (match &theory (metainfo $label $kvs) $kvs))
     (($kvs $kvs) (Empty ()))))

(= (directive-describe $path $labels)
   (let $_ (dl-run $path)
     (described-all (map-atom $labels $l (describe-one $l)))))

; --- lifecycle mutations (claim/unclaim/block/unblock/complete/assert) ---

(= (directive-claim $path $task-raw $agent $force)
   (let* (($_ (dl-run $path))
          ($task (dir_strip_task $task-raw))
          ($names (directive-pos-names)))
     (if (== (is-member (dir_lit task $task) $names) False)
         (err task-not-found $task (available (sort-atom (directive-tasks $names))))
         (if (and (== $force False)
                  (== (is-member (dir_lit ready $task) $names) False))
             (err not-ready $task)
             (let ($maxv $last $ma $mc) (dir_find_versions $names claim unclaim $task)
               (if (== $last action)
                   (already-claimed $task $maxv)
                   (let* (($nv (+ $maxv 1))
                          ($prevc (if (> $mc 0) $mc -1))
                          ($ts (mm_now_iso))
                          ($block (dir_action_block $agent $ts $task $nv $prevc
                                               claim claimed unclaimed unclaim))
                          ($prop (dir_propagation_block &theory $task $nv))
                          ($_1 (mm_append_file $path $block))
                          ($_2 (if (== $prop "") ()
                                   (let $__ (mm_append_file $path $prop) ()))))
                     (claimed $task $nv))))))))

(= (directive-unclaim $path $task-raw $agent)
   (let* (($_ (dl-run $path))
          ($task (dir_strip_task $task-raw))
          ($names (directive-pos-names)))
     (let ($maxv $last $ma $mc) (dir_find_versions $names claim unclaim $task)
       (if (not (== $last action))
           (err not-claimed $task)
           (let* (($nv (+ $maxv 1))
                  ($preva (if (> $ma 0) $ma -1))
                  ($ts (mm_now_iso))
                  ($block (dir_counter_block $agent $ts $task $nv $preva
                                        unclaim unclaimed claimed claimed claim))
                  ($_1 (mm_append_file $path $block)))
             (unclaimed $task $nv))))))

(= (directive-block $path $task-raw $agent)
   (let* (($_ (dl-run $path))
          ($task (dir_strip_task $task-raw))
          ($names (directive-pos-names)))
     (if (== (is-member (dir_lit completed $task) $names) True)
         (err already-completed $task)
         (let ($maxv $last $ma $mc) (dir_find_versions $names block unblock $task)
           (if (== $last action)
               (already-blocked $task $maxv)
               (let* (($nv (+ $maxv 1))
                      ($prevc (if (> $mc 0) $mc -1))
                      ($ts (mm_now_iso))
                      ($block (dir_action_block $agent $ts $task $nv $prevc
                                           block blocked unblocked unblock))
                      ($_1 (mm_append_file $path $block)))
                 (blocked $task $nv)))))))

(= (directive-unblock $path $task-raw $agent)
   (let* (($_ (dl-run $path))
          ($task (dir_strip_task $task-raw))
          ($names (directive-pos-names)))
     (let ($maxv $last $ma $mc) (dir_find_versions $names block unblock $task)
       (if (not (== $last action))
           (err not-blocked $task)
           (let* (($nv (+ $maxv 1))
                  ($preva (if (> $ma 0) $ma -1))
                  ($ts (mm_now_iso))
                  ($block (dir_counter_block $agent $ts $task $nv $preva
                                        unblock unblocked blocked blocked block))
                  ($_1 (mm_append_file $path $block)))
             (unblocked $task $nv))))))

(= (directive-complete $path $task-raw $agent)
   (let* (($_ (dl-run $path))
          ($task (dir_strip_task $task-raw))
          ($names (directive-pos-names)))
     (if (== (is-member (dir_lit task $task) $names) False)
         (err task-not-found $task (available (sort-atom (directive-tasks $names))))
         (if (== (is-member (dir_lit completed $task) $names) True)
             (already-completed $task)
             (let* (($ts (mm_now_iso))
                    ($block (dir_complete_block $agent $ts $task))
                    ($_1 (mm_append_file $path $block))
                    ($_2 (dl-run $path))
                    ($names2 (directive-pos-names))
                    ($all (directive-tasks $names2))
                    ($done (directive-completed $names2)))
               (if (== (subtraction-atom $all $done) ())
                   (completed $task plan-complete)
                   (completed $task)))))))

(= (directive-assert $path $agent $form-text)
   (let* (($ts (mm_now_iso))
          ($block (dir_assert_block $agent $ts $form-text))
          ($_1 (mm_append_file $path $block)))
     (asserted $form-text)))
