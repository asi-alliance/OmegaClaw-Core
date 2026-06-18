;; =============================================================================
;; TRUST POLICY TEST PLAN (MeTTa format)
;; =============================================================================
;; Tests trust-weighted reasoning features.
;; Defines trust values for different agent sources and action thresholds.

;; -----------------------------------------------------------------------------
;; Trust Values: How much we trust each source (0.0 to 1.0)
;; -----------------------------------------------------------------------------

;; Security agent has highest trust
(given (trusts "agent:security" 0.95))

;; System policies are fully trusted
(given (trusts "system:policy" 1.0))

;; Architect is well-trusted
(given (trusts "agent:architect" 0.85))

;; QA team has good trust
(given (trusts "agent:qa" 0.80))

;; Developer trust is moderate
(given (trusts "agent:coder" 0.70))

;; External sources have lower trust
(given (trusts "external:api" 0.50))

;; Unknown sources have minimal trust
(given (trusts "unknown" 0.30))

;; -----------------------------------------------------------------------------
;; Action Thresholds: Minimum trust required for each action
;; -----------------------------------------------------------------------------

;; Deployment requires very high confidence (0.90)
(given (threshold "deploy" 0.90))

;; Merge to main requires high confidence (0.80)
(given (threshold "merge" 0.80))

;; Code review approval needs moderate confidence (0.70)
(given (threshold "approve" 0.70))

;; Creating alerts requires minimal confidence (0.50)
(given (threshold "alert" 0.50))

;; Logging requires lowest confidence (0.30)
(given (threshold "log" 0.30))

;; -----------------------------------------------------------------------------
;; Trust Decay (optional): How trust diminishes over time
;; -----------------------------------------------------------------------------

;; External API trust decays faster (exponential model)
(given (decays "external:api" "exponential"))

;; Agent trust decays linearly over time
(given (decays "agent:coder" "linear"))
