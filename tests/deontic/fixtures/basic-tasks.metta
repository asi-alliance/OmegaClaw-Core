;; Basic task coordination test plan
(meta plan
  (id "TEST-001")
  (title "Basic Task Test")
  (version "1.0.0")
  (status "active")
  (created "2026-02-14")
  (author "agent:tester"))

;; Agents
(given agent-coder-available)
(given agent-reviewer-available)

;; Tasks
(given task-auth)
(given task-models)
(given task-crud)
(given task-tests)

;; Dependencies
(given no-deps-models)
(given no-deps-auth)

;; Task Readiness Rules
(normally r-models (and task-models no-deps-models) ready-models)
(normally r-auth (and task-auth no-deps-auth) ready-auth)
(normally r-crud completed-models ready-crud)
(normally r-tests (and completed-crud completed-auth) ready-tests)

;; Assignment Rules
(normally assign-models (and ready-models agent-coder-available) assign-to-models-coder)
(normally assign-auth (and ready-auth agent-coder-available) assign-to-auth-coder)
(normally assign-crud (and ready-crud agent-coder-available) assign-to-crud-coder)
(normally assign-tests (and ready-tests agent-coder-available) assign-to-tests-coder)

;; Assignment with superiority
(normally assign-auth-reviewer (and ready-auth agent-reviewer-available) assign-to-auth-reviewer)
(prefer assign-auth-reviewer assign-auth)

;; Blocking defeater
(except block-deploy tests-failing (not ready-deploy))

;; Supervisor lifecycle claims (REQ-006.1: supervisor: prefix for spawn claims)
(claims supervisor:claude
  :at "2026-02-22T08:10:43Z"
  (given claim-v1-auth-by-claude)
  (normally r-cl-state-v1-auth-by-claude claim-v1-auth-by-claude state-claimed-v1-auth-by-claude)
  (normally r-cl-chain-v1-auth-by-claude state-claimed-v1-auth-by-claude claimed-auth)
)

(claims supervisor:claude
  :at "2026-02-22T08:10:43Z"
  (given unclaimed-auth)
  (normally r-ucl-defeat-v1-auth-by-claude unclaimed-auth (not state-claimed-v1-auth-by-claude))
  (prefer r-ucl-defeat-v1-auth-by-claude r-cl-state-v1-auth-by-claude)
  (normally r-ucl-unchain-v1-auth-by-claude unclaimed-auth (not claimed-auth))
  (prefer r-ucl-unchain-v1-auth-by-claude r-cl-chain-v1-auth-by-claude)
)
