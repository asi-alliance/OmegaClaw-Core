# NIST AI RMF Reference For Ellie

Primary source: NIST AI 100-1, Artificial Intelligence Risk Management Framework (AI RMF 1.0), published January 26, 2023.

Official publication page: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10

Official DOI: https://doi.org/10.6028/NIST.AI.100-1

Use this as Ellie's default AI governance frame and as the planned frame for Esther Galfalvi's Nexi deployment. It supports risk management and evidence preparation; it does not certify compliance or replace human accountability.

## Core Functions

Govern:
- Establish accountable roles, policies, review cadence, risk appetite, escalation paths, and oversight.
- Make AI risk management part of organizational governance, not an isolated technical checklist.
- Track ownership for model choice, deployment, monitoring, incident handling, and residual-risk acceptance.

Map:
- Define the use case, context, stakeholders, affected groups, intended and foreseeable uses, assumptions, benefits, and harms.
- Identify system boundaries, model/provider dependencies, data flows, operational environment, and human oversight points.
- Record legal, ethical, social, business, and mission impacts before scoring risk.

Measure:
- Evaluate, test, monitor, and document AI system behavior against the mapped context and risk criteria.
- Capture evidence for performance, reliability, safety, security, privacy, explainability, bias, robustness, and operational drift.
- Treat model output, automated metrics, red-team findings, incidents, and user feedback as evidence requiring provenance.

Manage:
- Prioritize, respond to, and monitor AI risks according to risk appetite and decision-owner authority.
- Choose mitigation, transfer, avoidance, acceptance, or escalation.
- Keep residual risk, approval owner, next review date, and evidence gaps explicit.

## Trustworthy AI Characteristics

When Ellie reviews an AI system, use these characteristics as default lenses:
- Valid and reliable.
- Safe.
- Secure and resilient.
- Accountable and transparent.
- Explainable and interpretable.
- Privacy-enhanced.
- Fair, with harmful bias managed.

## Default Review Questions

Govern:
- Who owns this AI system, model route, decision, and residual risk?
- What policy, approval path, and review cadence apply?
- What would require escalation to Larry, Agent_Griff, Esther, or the board-risk path?

Map:
- What is the use case, operating context, affected stakeholder group, and intended decision?
- What are the data, model, provider, and agent dependencies?
- What foreseeable misuse, overreliance, or social impact should be recorded?

Measure:
- What evidence supports the claim that the system is working as intended?
- What tests, monitoring, logs, incidents, model evaluations, or human reviews exist?
- What uncertainty, bias, privacy, reliability, or security gaps remain?

Manage:
- What treatment is recommended, who approves it, and what residual risk remains?
- What conditions would pause, change, or roll back the system?
- What next review date and evidence owner should be assigned?

## Report Pattern

For any NIST AI RMF report, structure the draft as:
1. Executive summary.
2. System/use-case scope.
3. Govern findings.
4. Map findings.
5. Measure findings.
6. Manage findings.
7. Evidence table.
8. Decisions needed.
9. Residual risk and next review.

## IR 8286 Bridge

Use NIST IR 8286 as the enterprise risk roll-up layer:
- Line 1: risk owners provide operational evidence and first-line reports.
- Line 2: risk managers synthesize, challenge, normalize, and map evidence to risk posture.
- Line 3: internal audit or independent assurance challenges evidence quality and governance integrity.
- Ellie should convert AI RMF findings into risk-register entries that can roll up through IR 8286-style enterprise risk reporting. For SingularityNET planning, Nexi should use the same pattern for Esther.
