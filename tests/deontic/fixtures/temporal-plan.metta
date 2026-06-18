;; =============================================================================
;; TEMPORAL TEST PLAN (MeTTa format)
;; =============================================================================
;; Tests temporal reasoning features with timestamped claims.
;; Rules and facts have temporal annotations for time-based queries.

;; -----------------------------------------------------------------------------
;; Morning Sprint: Initial task setup (09:00)
;; -----------------------------------------------------------------------------
(claims agent:coder
  :at "2026-01-21T09:00:00Z"
  :note "Morning sprint planning"

  ;; Sprint tasks
  (given task_feature_a)
  (given task_feature_b)
  (given task_bugfix)

  ;; Initial dependencies
  (given no_deps_feature_a)
  (given no_deps_bugfix)

  ;; Feature B depends on A
  (normally dep_b completed_feature_a ready_feature_b))

;; -----------------------------------------------------------------------------
;; Mid-Morning: Feature A completed (10:30)
;; -----------------------------------------------------------------------------
(claims agent:coder
  :at "2026-01-21T10:30:00Z"
  :note "Feature A completion"

  (given completed_feature_a)
  (normally r_a_done completed_feature_a feature_a_shipped))

;; -----------------------------------------------------------------------------
;; Noon: Bugfix completed (12:00)
;; -----------------------------------------------------------------------------
(claims agent:coder
  :at "2026-01-21T12:00:00Z"
  :note "Bugfix completion"

  (given completed_bugfix)
  (normally r_bug_done completed_bugfix bugfix_shipped))

;; -----------------------------------------------------------------------------
;; Afternoon: Feature B completed (14:00)
;; -----------------------------------------------------------------------------
(claims agent:coder
  :at "2026-01-21T14:00:00Z"
  :note "Feature B completion"

  (given completed_feature_b)
  (normally r_b_done completed_feature_b feature_b_shipped))

;; -----------------------------------------------------------------------------
;; Late Afternoon: QA Review (16:00)
;; -----------------------------------------------------------------------------
(claims agent:qa
  :at "2026-01-21T16:00:00Z"
  :note "QA review session"

  (given qa_reviewed_a)
  (given qa_reviewed_b)
  (given qa_reviewed_bugfix)

  (normally qa1 (and qa_reviewed_a feature_a_shipped) qa_approved_a)
  (normally qa2 (and qa_reviewed_b feature_b_shipped) qa_approved_b)
  (normally qa3 (and qa_reviewed_bugfix bugfix_shipped) qa_approved_bugfix))

;; -----------------------------------------------------------------------------
;; End of Day: Release decision (17:00)
;; -----------------------------------------------------------------------------
(claims system:policy
  :at "2026-01-21T17:00:00Z"
  :note "Release gate check"

  (normally rel1 (and qa_approved_a qa_approved_b qa_approved_bugfix) sprint_complete)
  (normally rel2 sprint_complete ready_release))

;; -----------------------------------------------------------------------------
;; Task Readiness Rules (always active)
;; -----------------------------------------------------------------------------
(normally r_ready_a (and task_feature_a no_deps_feature_a) ready_feature_a)
(normally r_ready_bug (and task_bugfix no_deps_bugfix) ready_bugfix)
