;; =============================================================================
;; TRUST CLAIMS TEST PLAN (MeTTa format)
;; =============================================================================
;; Tests trust-weighted reasoning with claims from multiple agents.
;; Each agent contributes facts and rules with source attribution.

;; -----------------------------------------------------------------------------
;; Security Agent Claims: Reports security findings
;; -----------------------------------------------------------------------------
(claims agent:security
  :at "2026-01-21T09:00:00Z"
  :note "Security scan results"

  ;; Security findings
  (given scan_complete)
  (given no_critical_vulns)

  ;; Rules for security approval
  (normally sec1 scan_complete scanned)
  (normally sec2 no_critical_vulns security_clear)
  (normally sec3 (and scanned security_clear) security_approved))

;; -----------------------------------------------------------------------------
;; Coder Agent Claims: Reports test and build status
;; -----------------------------------------------------------------------------
(claims agent:coder
  :at "2026-01-21T09:30:00Z"
  :note "CI/CD pipeline results"

  ;; Build and test facts
  (given build_passed)
  (given tests_passed)
  (given coverage_met)

  ;; Rules for code readiness
  (normally dev1 build_passed builds_ok)
  (normally dev2 tests_passed tests_ok)
  (normally dev3 coverage_met coverage_ok)
  (normally dev4 (and builds_ok tests_ok) code_quality_ok))

;; -----------------------------------------------------------------------------
;; QA Agent Claims: Reports manual testing
;; -----------------------------------------------------------------------------
(claims agent:qa
  :at "2026-01-21T10:00:00Z"
  :note "QA sign-off"

  ;; QA findings
  (given staging_tested)
  (given uat_approved)

  ;; Rules for QA approval
  (normally qa1 staging_tested staging_ok)
  (normally qa2 uat_approved uat_ok)
  (normally qa3 (and staging_ok uat_ok) qa_approved))

;; -----------------------------------------------------------------------------
;; Architect Agent Claims: Reviews design
;; -----------------------------------------------------------------------------
(claims agent:architect
  :at "2026-01-21T10:30:00Z"
  :note "Architecture review"

  ;; Architecture review findings
  (given design_reviewed)
  (given backward_compatible)

  ;; Rules for architecture approval
  (normally arch1 design_reviewed design_ok)
  (normally arch2 backward_compatible api_stable)
  (normally arch3 (and design_ok api_stable) arch_approved))

;; -----------------------------------------------------------------------------
;; System Policy: Combines signals into deployment decision
;; -----------------------------------------------------------------------------
(claims system:policy
  ;; Approval chain rules
  (normally pol1 (and code_quality_ok qa_approved) dev_approved)
  (normally pol2 (and dev_approved arch_approved) reviewed)
  (normally pol3 (and reviewed security_approved) ready_deploy)

  ;; Security blocks deployment (defeater)
  (except pol4 (not security_approved) (not ready_deploy)))

;; Security override takes precedence
(prefer pol4 pol3)
