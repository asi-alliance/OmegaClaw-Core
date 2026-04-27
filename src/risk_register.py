import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_RISK_PATH = os.path.join(REPO_ROOT, "memory", "risks.jsonl")
RISK_PATH = os.environ.get("OMEGACLAW_RISK_REGISTER", DEFAULT_RISK_PATH)

_VALID_STATUS = {"open", "monitoring", "treating", "accepted", "closed"}
_VALID_TIERS = {"low", "medium", "high", "critical"}

_DEMO_RISKS = [
    {
        "id": "DEMO-L1-NUNET-COMPUTE-SUPPLY",
        "title": "NuNet compute supply assurance for agent workloads",
        "description": "Line-1 NuNet telemetry agent reports uneven regional GPU availability for scheduled agentic AI evaluations. Risk is service degradation during governance-critical review windows.",
        "use_case": "Decentralized compute for model evaluation and agent execution",
        "model_provider": "Line 1 local GPU agents",
        "model_name": "Qwen / Gemma / GLM / DeepSeek local pool",
        "framework": "NIST IR 8286 Line 1 / NIST AI RMF Measure / ISO 42001 operations",
        "evidence_sources": ["NuNetOpsAgent capacity report", "scheduler latency sample", "node health summary"],
        "recommendation": "Define minimum reserve capacity for high-priority reviews; require failover to local or cloud fallback when governance SLAs are at risk.",
        "likelihood": 3,
        "impact": 4,
        "status": "treating",
        "required_human_approval": "CRO approval for fallback provider policy",
        "residual_risk": "Medium after reserve-capacity policy and failover testing",
        "decision_owner": "Line 1 compute operations owner",
        "next_review_date": "2026-05-15",
        "treatment": "Capacity guardrails and fallback runbook",
        "control_mapping": ["NIST AI RMF Measure", "ISO 42001 operations monitoring"],
    },
    {
        "id": "DEMO-L1-HYPERON-TOOL-AUDIT",
        "title": "OpenCog Hyperon tool-call auditability",
        "description": "Line-1 Hyperon/MeTTa agent reports that experimental tool calls need stronger linkage from prompt, symbolic action, evidence, and final recommendation.",
        "use_case": "Neural-symbolic agent reasoning and MeTTa skill dispatch",
        "model_provider": "Line 1 local GPU agents",
        "model_name": "Qwen / Gemma / GLM / DeepSeek / Granite local pool",
        "framework": "NIST IR 8286 Line 1 / NIST AI RMF Govern-Measure / ISO 42001 evidence",
        "evidence_sources": ["HyperonAgent trace sample", "MeTTa dispatch log", "Oma history excerpt"],
        "recommendation": "Attach immutable review IDs to skill calls and retain a compact evidence bundle for each material recommendation.",
        "likelihood": 4,
        "impact": 4,
        "status": "open",
        "required_human_approval": "Chief Ethics Officer approval before production use",
        "residual_risk": "High until evidence bundles are complete",
        "decision_owner": "Agent platform owner",
        "next_review_date": "2026-05-08",
        "treatment": "Evidence locker integration",
        "control_mapping": ["NIST AI RMF Govern", "ISO 42001 documented information"],
    },
    {
        "id": "DEMO-L2-DEEPFUNDING-GRANT-GOV",
        "title": "Deep Funding project review consistency",
        "description": "Line-2 governance agent reports variance in evidence quality across decentralized project reviews and milestone assessments.",
        "use_case": "Community grant review and milestone governance",
        "model_provider": "Line 2 risk manager route",
        "model_name": "Current sample: ChatGPT 5.5 governance review route",
        "framework": "NIST IR 8286 Line 2 / NIST AI RMF Govern-Map / ISO 42001 impact assessment",
        "evidence_sources": ["DeepFundingGovAgent review sample", "proposal rubric extract", "milestone evidence checklist"],
        "recommendation": "Normalize review rubrics and require evidence completeness checks before risk acceptance or funding-stage movement.",
        "likelihood": 3,
        "impact": 3,
        "status": "monitoring",
        "required_human_approval": "Governance council review for rubric changes",
        "residual_risk": "Medium with standardized rubric",
        "decision_owner": "Line 2 governance function",
        "next_review_date": "2026-05-22",
        "treatment": "Standardized review pack",
        "control_mapping": ["NIST AI RMF Govern", "ISO 42001 impact assessment"],
    },
    {
        "id": "DEMO-L2-REJUVE-HEALTH-DATA",
        "title": "Rejuve.AI health-data ethics and consent posture",
        "description": "Line-2 ethics agent flags sensitive health-data use as requiring stronger consent evidence and residual-risk documentation for AI-driven longevity insights.",
        "use_case": "Longevity research insights from participant data",
        "model_provider": "Line 2 risk manager route",
        "model_name": "Current sample: ChatGPT 5.5 ethics review route",
        "framework": "NIST IR 8286 Line 2 / NIST AI RMF Map-Manage / ISO 42001 impact assessment",
        "evidence_sources": ["EthicsReviewAgent DPIA checklist", "consent-flow sample", "data minimization review"],
        "recommendation": "Require explicit consent evidence, data minimization review, and human approval for high-impact participant-facing claims.",
        "likelihood": 3,
        "impact": 5,
        "status": "open",
        "required_human_approval": "Chief Ethics Officer approval",
        "residual_risk": "High until consent evidence is attached",
        "decision_owner": "Ethics and privacy owner",
        "next_review_date": "2026-05-10",
        "treatment": "Consent evidence locker and claim review workflow",
        "control_mapping": ["NIST AI RMF Map", "ISO 42001 AI impact assessment"],
    },
    {
        "id": "DEMO-L3-SOPHIAVERSE-HUMANOID-CLAIMS",
        "title": "SophiaVerse humanoid-sentience claims oversight",
        "description": "Line-3 audit agent identifies reputational and ethics risk around public-facing humanoid sentience language and user expectations.",
        "use_case": "Public AI experience, embodied agents, and metaverse interaction",
        "model_provider": "Line 3 internal audit route",
        "model_name": "Current sample: Claude Opus 4.7 audit review route",
        "framework": "NIST IR 8286 Line 3 / NIST AI RMF Manage / ISO 42001 communication controls",
        "evidence_sources": ["AuditAgent public-claims sample", "marketing review checklist", "user expectation log"],
        "recommendation": "Maintain human review for public sentience claims and require evidence-backed language for user-facing agent capabilities.",
        "likelihood": 2,
        "impact": 4,
        "status": "monitoring",
        "required_human_approval": "Audit committee review for external claims policy",
        "residual_risk": "Medium with review gate",
        "decision_owner": "Line 3 audit liaison",
        "next_review_date": "2026-06-01",
        "treatment": "External-claims review gate",
        "control_mapping": ["NIST AI RMF Manage", "ISO 42001 communication"],
    },
    {
        "id": "DEMO-L3-ASI-ALLIANCE-MODEL-ROUTING",
        "title": "ASI Alliance model-routing and fallback accountability",
        "description": "Line-3 audit agent reports that model routing across local, OpenAI-compatible, and Anthropic endpoints needs explicit decision-owner and fallback evidence.",
        "use_case": "Model switchboard for executive governance workflows",
        "model_provider": "Mixed provider routing",
        "model_name": "Dynamic model routing; current examples: ChatGPT 5.5 primary, Claude Opus 4.7 fallback, local IBM Granite for ISO/IEC 42001 support",
        "framework": "NIST IR 8286 Line 3 / NIST AI RMF Govern-Manage / ISO 42001 supplier and operations controls",
        "evidence_sources": ["AuditAgent routing sample", "provider health log", "fallback decision record"],
        "recommendation": "Log selected provider, fallback reason, prompt summary, and accountable owner for every material governance artifact.",
        "likelihood": 4,
        "impact": 5,
        "status": "open",
        "required_human_approval": "Board-risk committee approval for provider fallback policy",
        "residual_risk": "Critical until fallback accountability is consistently captured",
        "decision_owner": "CRO / Chief Ethics Officer",
        "next_review_date": "2026-05-03",
        "treatment": "Model switchboard audit metadata",
        "control_mapping": ["NIST AI RMF Govern", "ISO 42001 supplier management"],
    },
]


_DEMO_REPORTS = [
    {
        "id": "RPT-L1-NUNET-001",
        "line": 1,
        "agent": "Line1LocalGPUAgent",
        "source": "NuNet",
        "summary": "Local Qwen/Gemma/GLM/DeepSeek agent reports regional compute capacity variance for high-priority review windows.",
        "mapped_risk": "DEMO-L1-NUNET-COMPUTE-SUPPLY",
        "confidence": 0.74,
    },
    {
        "id": "RPT-L1-HYPERON-002",
        "line": 1,
        "agent": "Line1TraceAgent",
        "source": "OpenCog Hyperon / MeTTa",
        "summary": "Local Granite/Qwen trace agent reports that tool-call traces need stronger evidence bundle IDs for executive artifacts.",
        "mapped_risk": "DEMO-L1-HYPERON-TOOL-AUDIT",
        "confidence": 0.82,
    },
    {
        "id": "RPT-L2-DEEPFUNDING-003",
        "line": 2,
        "agent": "Line2RiskManagerAgent",
        "source": "Deep Funding",
        "summary": "Line-2 risk manager agent reports variance in milestone evidence quality; rubric normalization recommended. Current sample route: ChatGPT 5.5.",
        "mapped_risk": "DEMO-L2-DEEPFUNDING-GRANT-GOV",
        "confidence": 0.69,
    },
    {
        "id": "RPT-L2-ETHICS-004",
        "line": 2,
        "agent": "Line2EthicsRiskAgent",
        "source": "Rejuve.AI",
        "summary": "Line-2 ethics risk agent reports that sensitive health-data use needs consent evidence and high-impact claim review. Current sample route: ChatGPT 5.5.",
        "mapped_risk": "DEMO-L2-REJUVE-HEALTH-DATA",
        "confidence": 0.78,
    },
    {
        "id": "RPT-L3-AUDIT-005",
        "line": 3,
        "agent": "Line3ClaimsAuditAgent",
        "source": "SophiaVerse",
        "summary": "Line-3 internal audit agent reports that public-facing humanoid-sentience language should pass an evidence-backed claims gate. Current sample route: Claude Opus 4.7.",
        "mapped_risk": "DEMO-L3-SOPHIAVERSE-HUMANOID-CLAIMS",
        "confidence": 0.71,
    },
    {
        "id": "RPT-L3-ROUTING-006",
        "line": 3,
        "agent": "Line3RouteAuditAgent",
        "source": "ASI Alliance model switchboard",
        "summary": "Line-3 internal audit agent reports that dynamic routing decisions across API and local models need auditable owner metadata. Current examples include ChatGPT, Claude, and local Granite.",
        "mapped_risk": "DEMO-L3-ASI-ALLIANCE-MODEL-ROUTING",
        "confidence": 0.85,
    },
]


_ECOSYSTEM_NODES = [
    {"id": "oma", "label": "Nexi", "group": "command", "line": 0, "tier": "command",
     "role": "Esther's CRO-facing model-agnostic AI agent", "owner": "Esther Galfalvi / CRO",
     "summary": "Nexi works directly with Esther as a calm, careful governance companion: receiving assurance reports, organizing evidence, surfacing risk posture, and preparing draft executive artifacts for human judgment. AgentGriff can provide independent InterNetwork Defense CRO challenge and third-party advice to Nexi and Esther.",
     "models": ["Dynamic routing protocol", "Current primary: ChatGPT 5.5", "Fallback: Claude Opus 4.7", "ISO route: local IBM Granite"],
     "controls": ["Human approval path", "Model-agnostic routing", "Risk register synthesis", "Executive evidence pack", "AgentGriff independent challenge"],
     "actions": ["Review top risks with Esther", "Request AgentGriff challenge", "Switch model route", "Generate executive brief", "Escalate residual-risk acceptance"]},
    {"id": "line1-local", "label": "Line 1 Risk Owner Agents", "group": "line1", "line": 1, "tier": "assurance",
     "role": "Risk owner agents", "owner": "System and sub-org operators",
     "summary": "Model-agnostic first-line agents that gather operational evidence, incident signals, and control-owner reports.",
     "models": ["Current: local GPU mix", "Qwen / Gemma / GLM / DeepSeek / Granite"],
     "controls": ["Telemetry intake", "Incident detection", "Control evidence capture"],
     "actions": ["Review local GPU reports", "Attach operational evidence", "Escalate exception to Nexi"]},
    {"id": "line2-chatgpt", "label": "Line 2 Risk Manager Agents", "group": "line2", "line": 2, "tier": "assurance",
     "role": "Risk manager agents", "owner": "Risk management function",
     "summary": "Model-agnostic second-line agents that synthesize Line-1 inputs into risk entries, evidence gaps, control mappings, and treatment recommendations.",
     "models": ["Current: larger local models + API", "Sample API: ChatGPT 5.5"],
     "controls": ["Risk scoring", "Policy mapping", "Treatment recommendation", "Evidence completeness review"],
     "actions": ["Run governance review", "Draft treatment plan", "Map control evidence"]},
    {"id": "line3-claude", "label": "AgentGriff · InterNetwork Defense CRO Agent", "group": "line3", "line": 3, "tier": "assurance",
     "role": "Independent CRO advisor / third-party assurance agent", "owner": "InterNetwork Defense / board-risk oversight",
     "summary": "AgentGriff provides model-agnostic third-party CRO advice to Nexi and Esther: independently reviewing model routing, claims language, audit packs, board-facing risk summaries, and residual-risk acceptance.",
     "models": ["Current: Claude Opus 4.7", "Can route to other models for challenge review"],
     "controls": ["Independent CRO advice", "Board memo challenge", "Claims audit", "Residual-risk acceptance review"],
     "actions": ["Run AgentGriff challenge", "Prepare board note", "Review residual risk"]},
    {"id": "nunet", "label": "NuNet", "group": "domain", "line": 0, "tier": "domain",
     "role": "Ecosystem domain with Line 1 and Line 2 agent coverage", "owner": "Compute operations + risk function",
     "summary": "Line-1 agents monitor compute supply, while Line-2 risk manager agents synthesize availability and fallback risks for Nexi using the best available route.",
     "models": ["Line 1 current: local GPU mix", "Line 2 current sample: ChatGPT 5.5"],
     "controls": ["Capacity monitoring", "Fallback runbook", "Service availability evidence"],
     "actions": ["Review capacity trend", "Test fallback route", "Attach node-health evidence"]},
    {"id": "hyperon", "label": "OpenCog Hyperon", "group": "domain", "line": 0, "tier": "domain",
     "role": "Ecosystem domain with Line 1 and Line 2 agent coverage", "owner": "Agent platform + risk function",
     "summary": "Line-1 agents inspect MeTTa traces; Line-2 risk manager agents convert trace gaps into governance-ready evidence requirements using the best available route.",
     "models": ["Line 1 current: local Granite/Qwen", "Line 2 current sample: ChatGPT 5.5"],
     "controls": ["Tool-call traceability", "Evidence bundle IDs", "Reasoning trace review"],
     "actions": ["Open evidence locker", "Inspect MeTTa trace", "Assign trace owner"]},
    {"id": "deepfunding", "label": "Deep Funding", "group": "domain", "line": 0, "tier": "domain",
     "role": "Ecosystem domain with Line 1 and Line 2 agent coverage", "owner": "Grant operations + governance risk",
     "summary": "Line-1 agents capture proposal and milestone evidence; Line-2 risk manager agents normalize review quality and governance exceptions using the best available route.",
     "models": ["Line 1 current: local model mix", "Line 2 current sample: ChatGPT 5.5"],
     "controls": ["Rubric completeness", "Milestone evidence checks", "Review consistency sampling"],
     "actions": ["Normalize rubric", "Review milestone pack", "Escalate governance exception"]},
    {"id": "rejuve", "label": "Rejuve.AI", "group": "domain", "line": 0, "tier": "domain",
     "role": "Ecosystem domain with Line 1 and Line 2 agent coverage", "owner": "Health-data operations + ethics risk",
     "summary": "Line-1 agents capture operational data-handling evidence; Line-2 risk manager agents review consent, minimization, and participant-facing claim risks using the best available route.",
     "models": ["Line 1 current: local model mix", "Line 2 current sample: ChatGPT 5.5"],
     "controls": ["Consent evidence", "Data minimization", "High-impact claim review"],
     "actions": ["Open consent evidence", "Request privacy review", "Schedule ethics approval"]},
    {"id": "sophiaverse", "label": "SophiaVerse", "group": "domain", "line": 0, "tier": "domain",
     "role": "Ecosystem domain with Line 1, Line 2, and Line 3 agent coverage", "owner": "Experience operations + risk + audit",
     "summary": "Line-1 agents capture public experience signals; Line-2 risk manager agents review ethics posture; Line-3 internal audit agents challenge claims language and audit evidence.",
     "models": ["Line 1 current: local model mix", "Line 2 current sample: ChatGPT 5.5", "Line 3 current sample: Claude Opus 4.7"],
     "controls": ["External-claims review gate", "User expectation monitoring", "Evidence-backed capability language"],
     "actions": ["Review claims policy", "Open audit sample", "Prepare board note"]},
    {"id": "asi", "label": "ASI Alliance", "group": "domain", "line": 0, "tier": "domain",
     "role": "Ecosystem domain with model-routing oversight", "owner": "CRO / Chief Ethics Officer",
     "summary": "Nexi coordinates dynamic routing across API and local models; Line-3 internal audit agents review fallback accountability.",
     "models": ["Dynamic routing protocol", "Current primary: ChatGPT 5.5", "Fallback: Claude Opus 4.7", "ISO route: IBM Granite local"],
     "controls": ["Provider fallback log", "Supplier accountability", "Material artifact audit metadata"],
     "actions": ["Review fallback decision", "Approve provider policy", "Check model health"]},
    {"id": "community", "label": "Community Governance", "group": "domain", "line": 0, "tier": "domain",
     "role": "Ecosystem domain with Line 1 and Line 2 agent coverage", "owner": "Governance facilitation + risk function",
     "summary": "Line-1 agents capture community signals and escalation requests; Line-2 risk manager agents prepare governance-ready decision records using the best available route.",
     "models": ["Line 1 current: local model mix", "Line 2 current sample: ChatGPT 5.5"],
     "controls": ["Community signal triage", "Escalation logging", "Transparent decision records"],
     "actions": ["Review escalation queue", "Attach community evidence", "Draft response note"]},
]

_ECOSYSTEM_EDGES = [
    {"from": "line1-local", "to": "oma", "label": "Line 1 local GPU operational reports"},
    {"from": "line2-chatgpt", "to": "oma", "label": "Line 2 risk manager synthesis"},
    {"from": "line3-claude", "to": "oma", "label": "Line 3 internal audit challenge"},
    {"from": "nunet", "to": "line1-local", "label": "compute telemetry"},
    {"from": "hyperon", "to": "line1-local", "label": "tool trace telemetry"},
    {"from": "deepfunding", "to": "line2-chatgpt", "label": "governance review"},
    {"from": "rejuve", "to": "line2-chatgpt", "label": "ethics review"},
    {"from": "sophiaverse", "to": "line2-chatgpt", "label": "ethics review"},
    {"from": "sophiaverse", "to": "line3-claude", "label": "claims audit"},
    {"from": "asi", "to": "line3-claude", "label": "model-route audit"},
    {"from": "community", "to": "line2-chatgpt", "label": "governance signal"},
]


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_store():
    os.makedirs(os.path.dirname(RISK_PATH), exist_ok=True)
    if not os.path.exists(RISK_PATH):
        with open(RISK_PATH, "w", encoding="utf-8"):
            pass


def _slug(text):
    text = (text or "risk").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text or "risk")[:36]


def _coerce_int(value, default=0):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(value, 5))


def _risk_tier(priority):
    if priority >= 20:
        return "critical"
    if priority >= 12:
        return "high"
    if priority >= 6:
        return "medium"
    return "low"


def _load():
    _ensure_store()
    rows = []
    with open(RISK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _write(rows):
    _ensure_store()
    fd, tmp = tempfile.mkstemp(prefix=".risks.", suffix=".jsonl", dir=os.path.dirname(RISK_PATH))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp, RISK_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _parse_payload(payload):
    if isinstance(payload, dict):
        return dict(payload)
    if payload is None:
        return {}
    text = str(payload).strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"title": text, "description": text}


def _normalize(entry, existing=None):
    base = dict(existing or {})
    base.update({k: v for k, v in entry.items() if v is not None})

    title = str(base.get("title") or base.get("use_case") or "Untitled risk").strip()
    likelihood = _coerce_int(base.get("likelihood"), 0)
    impact = _coerce_int(base.get("impact"), 0)
    priority = likelihood * impact if likelihood and impact else _coerce_int(base.get("priority"), 0)
    tier = str(base.get("risk_tier") or base.get("tier") or _risk_tier(priority)).lower()
    status = str(base.get("status") or "open").lower()

    if tier not in _VALID_TIERS:
        tier = _risk_tier(priority)
    if status not in _VALID_STATUS:
        status = "open"

    now = _now()
    risk_id = base.get("id") or base.get("risk_id")
    if not risk_id:
        risk_id = f"RISK-{int(time.time())}-{_slug(title)}"

    return {
        "id": str(risk_id),
        "title": title,
        "description": str(base.get("description") or "").strip(),
        "use_case": str(base.get("use_case") or "").strip(),
        "model_provider": str(base.get("model_provider") or "").strip(),
        "model_name": str(base.get("model_name") or "").strip(),
        "framework": str(base.get("framework") or "NIST AI RMF / ISO 42001 / NIST IR 8286").strip(),
        "evidence_sources": base.get("evidence_sources") or [],
        "recommendation": str(base.get("recommendation") or "").strip(),
        "likelihood": likelihood,
        "impact": impact,
        "priority": priority,
        "risk_tier": tier,
        "status": status,
        "required_human_approval": str(base.get("required_human_approval") or "").strip(),
        "residual_risk": str(base.get("residual_risk") or "").strip(),
        "decision_owner": str(base.get("decision_owner") or base.get("owner") or "").strip(),
        "next_review_date": str(base.get("next_review_date") or "").strip(),
        "treatment": str(base.get("treatment") or "").strip(),
        "control_mapping": base.get("control_mapping") or [],
        "created_at": base.get("created_at") or now,
        "updated_at": now,
    }


def _public_rows(rows):
    return sorted(rows, key=lambda r: (r.get("status") == "closed", -int(r.get("priority") or 0), r.get("title", "")))


def append_risk(payload):
    rows = _load()
    entry = _normalize(_parse_payload(payload))
    rows.append(entry)
    _write(rows)
    return json.dumps({"ok": True, "action": "append", "risk": entry}, ensure_ascii=False)


def list_risks(filter_text=""):
    rows = _public_rows(_load())
    filt = str(filter_text or "").strip().lower()
    if filt:
        rows = [r for r in rows if filt in json.dumps(r, ensure_ascii=False).lower()]
    return json.dumps({"ok": True, "count": len(rows), "risks": rows}, ensure_ascii=False)


def get_risk(risk_id):
    risk_id = str(risk_id or "").strip()
    for row in _load():
        if row.get("id") == risk_id:
            return json.dumps({"ok": True, "risk": row}, ensure_ascii=False)
    return json.dumps({"ok": False, "err": f"risk not found: {risk_id}"}, ensure_ascii=False)


def update_risk(risk_id, payload):
    risk_id = str(risk_id or "").strip()
    rows = _load()
    patch = _parse_payload(payload)
    for idx, row in enumerate(rows):
        if row.get("id") == risk_id:
            rows[idx] = _normalize(patch, existing=row)
            _write(rows)
            return json.dumps({"ok": True, "action": "update", "risk": rows[idx]}, ensure_ascii=False)
    return json.dumps({"ok": False, "err": f"risk not found: {risk_id}"}, ensure_ascii=False)


def dashboard_data():
    rows = _public_rows(_load())
    open_rows = [r for r in rows if r.get("status") != "closed"]
    by_tier = {tier: 0 for tier in ("low", "medium", "high", "critical")}
    heatmap = [[0 for _ in range(5)] for _ in range(5)]
    attention = []
    for row in open_rows:
        tier = row.get("risk_tier") or "low"
        by_tier[tier] = by_tier.get(tier, 0) + 1
        likelihood = _coerce_int(row.get("likelihood"), 0)
        impact = _coerce_int(row.get("impact"), 0)
        if likelihood and impact:
            heatmap[impact - 1][likelihood - 1] += 1
        missing = []
        for field in ("evidence_sources", "decision_owner", "treatment", "next_review_date"):
            if not row.get(field):
                missing.append(field)
        if missing or row.get("risk_tier") in ("high", "critical"):
            copy = dict(row)
            copy["attention_reasons"] = missing
            attention.append(copy)
    return json.dumps({
        "ok": True,
        "path": RISK_PATH,
        "total": len(rows),
        "open": len(open_rows),
        "by_tier": by_tier,
        "top_risks": open_rows[:10],
        "attention": attention[:10],
        "heatmap": heatmap,
        "updated_at": _now(),
    }, ensure_ascii=False)


def seed_demo_data():
    rows = _load()
    by_id = {row.get("id"): idx for idx, row in enumerate(rows)}
    changed = False
    inserted = 0
    refreshed = 0
    for demo in _DEMO_RISKS:
        if demo["id"] in by_id:
            existing = rows[by_id[demo["id"]]]
            rows[by_id[demo["id"]]] = _normalize(demo, existing={"created_at": existing.get("created_at"), "id": demo["id"]})
            refreshed += 1
            changed = True
        else:
            rows.append(_normalize(demo))
            inserted += 1
            changed = True
    if changed:
        _write(rows)
    return json.dumps({
        "ok": True,
        "inserted": inserted,
        "refreshed": refreshed,
        "total": len(_load()),
        "demo": True,
    }, ensure_ascii=False)


def ecosystem_data():
    dashboard = json.loads(dashboard_data())
    return json.dumps({
        "ok": True,
        "demo": True,
        "description": "Synthetic SingularityNET ecosystem demo mapped to NIST IR 8286 three lines of defense.",
        "nodes": _ECOSYSTEM_NODES,
        "edges": _ECOSYSTEM_EDGES,
        "reports": _DEMO_REPORTS,
        "dashboard": dashboard,
    }, ensure_ascii=False)


def org_data(org_id):
    org_id = str(org_id or "").strip().lower()
    nodes = {node["id"]: node for node in _ECOSYSTEM_NODES}
    node = nodes.get(org_id)
    if not node:
        return json.dumps({"ok": False, "err": f"unknown org: {org_id}"}, ensure_ascii=False)
    label = node["label"].lower()
    risks = []
    for risk in _load():
        text = " ".join([
            str(risk.get("id", "")),
            str(risk.get("title", "")),
            str(risk.get("description", "")),
            str(risk.get("use_case", "")),
            str(risk.get("framework", "")),
        ]).lower()
        if org_id in text or label in text:
            risks.append(risk)
    reports = [
        report for report in _DEMO_REPORTS
        if report.get("source", "").lower().startswith(label)
        or org_id in report.get("mapped_risk", "").lower()
        or label in report.get("summary", "").lower()
    ]
    incoming = [edge for edge in _ECOSYSTEM_EDGES if edge.get("to") == org_id]
    outgoing = [edge for edge in _ECOSYSTEM_EDGES if edge.get("from") == org_id]
    return json.dumps({
        "ok": True,
        "demo": True,
        "org": node,
        "risks": _public_rows(risks),
        "reports": reports,
        "incoming": incoming,
        "outgoing": outgoing,
    }, ensure_ascii=False)


def risk_register(action, payload=""):
    action = str(action or "list").strip().lower()
    if action in ("append", "add", "create"):
        return append_risk(payload)
    if action in ("list", "query", "search"):
        return list_risks(payload)
    if action in ("get", "read"):
        return get_risk(payload)
    if action in ("dashboard", "summary", "summarize"):
        return dashboard_data()
    if action in ("seed-demo", "demo"):
        return seed_demo_data()
    if action in ("ecosystem", "ecosystem-demo"):
        return ecosystem_data()
    return json.dumps({
        "ok": False,
        "err": f"unknown risk-register action: {action}",
        "valid_actions": ["append", "list", "get", "update", "dashboard"],
    }, ensure_ascii=False)


def risk_register_update(risk_id, payload):
    return update_risk(risk_id, payload)


def _recent_history_anchors(limit=6):
    path = os.path.join(REPO_ROOT, "memory", "history.metta")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()[-60000:]
    except OSError:
        return []
    anchors = []
    for m in re.finditer(r"HUMAN_MESSAGE:\s*(.*?)(?:_newline_|\n|\)\s*\n)", text, re.S):
        msg = re.sub(r"\s+", " ", m.group(1)).strip()
        msg = msg.replace("_quote_", '"').replace("_apostrophe_", "'").replace("_newline_", " ")
        if msg and msg not in anchors:
            anchors.append(msg[:240])
    if not anchors:
        for m in re.finditer(r"\(send\s+\(text\s+_quote_(.*?)_quote_\)\)", text, re.S):
            msg = m.group(1).replace("_newline_", " ").replace("_apostrophe_", "'")
            msg = re.sub(r"\s+", " ", msg).strip()
            if msg and msg not in anchors:
                anchors.append(msg[:240])
    return anchors[-limit:]


def context_snapshot():
    """Small deterministic continuity layer included before raw history.

    This survives provider/model switches and gives small/local models a stable
    map of identity, governance posture, and recent anchors without requiring
    them to parse the entire historical tail.
    """
    rows = _load()
    top = sorted(rows, key=lambda r: int(r.get("priority") or 0), reverse=True)[:5]
    tiers = {}
    for row in rows:
        if row.get("status", "open") != "closed":
            tiers[row.get("risk_tier", "low")] = tiers.get(row.get("risk_tier", "low"), 0) + 1
    risk_lines = [
        f"{r.get('id')}: {r.get('title')} [{str(r.get('risk_tier', 'low')).upper()} P{r.get('priority', 0)} owner={r.get('decision_owner', 'unassigned')}]"
        for r in top
    ]
    anchors = _recent_history_anchors()
    parts = [
        "Identity: Ellie is Captain Larry's active local Oma agent and Chief Ethics Officer for InterNetwork Defense; Agent_Griff is Larry's OpenClaw assistant and CRO/security copilot.",
        "Deployment distinction: Esther Galfalvi is the CRO at SingularityNET, and Nexi is her planned Oma agent; do not confuse Nexi with Ellie.",
        "Mission: support AI ethics, risk, and compliance workflows for InterNetwork Defense and SingularityNET-related planning; assist review and evidence collection; never claim certification or replace human approval.",
        "Voice rule: do not volunteer disclaimers about feelings, consciousness, inner experience, or pretending; keep the focus on ethics, evidence, accountability, and the work.",
        "Primary framework: NIST AI RMF 1.0 (NIST AI 100-1) with Govern, Map, Measure, Manage as the default AI risk review structure.",
        "RMF lenses: valid/reliable, safe, secure/resilient, accountable/transparent, explainable/interpretable, privacy-enhanced, and harmful-bias-managed.",
        "Framework bridge: NIST IR 8286 supplies enterprise risk roll-up and three-lines reporting; ISO/IEC 42001 supplies AI management system evidence.",
        "Model routing: dynamic and model-agnostic across OpenAI, Anthropic, and local models; preserve audit metadata and human approval paths during switches.",
        "Open risk posture: " + (", ".join(f"{k}={v}" for k, v in sorted(tiers.items())) or "none"),
        "Top risks: " + (" | ".join(risk_lines) if risk_lines else "none captured"),
        "Recent anchors: " + (" | ".join(anchors) if anchors else "none"),
    ]
    return "\n".join(parts)


def prompt_file():
    configured = os.environ.get("OMEGACLAW_PROMPT_FILE", "").strip()
    if not configured:
        configured = "prompt.txt"
    if os.path.isabs(configured):
        return configured
    return os.path.join(REPO_ROOT, "memory", configured)
