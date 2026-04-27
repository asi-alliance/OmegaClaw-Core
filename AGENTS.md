# AGENTS.md

## Project Mission

We are building Oma OmegaClaw: a packaged WebUI app for SingularityNET leadership, especially a CRO / Chief Ethics Officer role. The app should act as an AI Ethics & Risk Command Center for agentic AI systems.

Primary goals:
- Help a CRO / Chief Ethics Officer review AI systems, agents, model choices, incidents, and risk decisions.
- Support ISO/IEC 42001-style AI management workflows and NIST AI RMF-style Govern, Map, Measure, Manage workflows.
- Provide a clean UI built on this repo's existing WebUI patterns.
- Support model-agnostic routing across OpenAI-compatible APIs, Anthropic APIs, and local models.
- Preserve auditability, explainability, evidence capture, and human approval paths.

## Working Style

Before making changes:
1. Inspect the repo structure.
2. Read README, package files, config files, and existing WebUI architecture.
3. Identify the framework, package manager, backend, frontend, and test commands.
4. Propose a short implementation plan before editing major files.

Make small, reversible changes. Do not rewrite the architecture unless explicitly asked.

## Security Rules

Never hard-code API keys, tokens, secrets, URLs with embedded credentials, or private keys.

Use environment variables and provide a `.env.example` when adding new configuration.

Provider credentials should stay server-side unless the existing project architecture clearly supports secure client-side configuration.

Add or update `.gitignore` if needed to prevent secrets, local databases, logs, or model files from being committed.

## Model Provider Design

Implement model providers behind a clean abstraction.

Preferred interface:
- provider id
- model id
- display name
- capabilities
- health check
- invoke/chat method
- streaming support flag
- local/remote flag
- audit metadata

Required provider families:
- OpenAI-compatible API
- Anthropic API
- Local model endpoint

Do not scatter provider-specific logic throughout UI components. Keep it in adapter/provider modules.

Support graceful fallback:
1. selected provider
2. configured fallback provider
3. local provider, when suitable
4. clear human-readable failure state

## CRO / Ethics Features

Prioritize these product areas:
- Risk Radar dashboard
- Ethics Review Queue
- Model Switchboard
- Evidence Locker
- Executive Brief Generator
- Incident / near-miss review
- Human oversight recommendation
- AI system intake form
- Risk register entry generation

Every review should capture:
- timestamp
- user
- use case
- model provider
- model name
- prompt or task summary
- policy framework used
- evidence sources
- recommendation
- risk tier
- required human approval
- residual risk
- decision owner
- next review date

## UI Direction

The UI should feel like a calm executive cockpit:
- clean
- readable
- accessible
- dashboard-first
- low clutter
- strong status indicators
- clear escalation paths

Suggested navigation:
Dashboard | Reviews | Risks | Incidents | Model Switchboard | Evidence | Reports | Settings

## Compliance and Governance Language

Use careful language. Avoid claiming the tool "certifies compliance." Prefer:
- supports evidence collection
- assists review
- maps controls
- generates draft artifacts
- supports governance workflows
- helps prepare audit evidence

## Testing and Validation

After changes:
- run the project's lint/typecheck/test commands if available
- report commands run and results
- do not hide failing tests
- explain any skipped tests

When adding logic:
- include unit tests where the repo already has a test pattern
- add lightweight validation for provider config
- add error handling for offline, timeout, invalid key, rate limit, and unavailable local model cases

## Output Expectations

When done, summarize:
- files changed
- what was added
- how to run it
- how to configure providers
- tests run
- known limitations
