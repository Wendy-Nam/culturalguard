# CulturalGuard

**AI Agent for Cross-Cultural Content Risk Intelligence**

CulturalGuard analyzes social media and marketing content for cultural risks, compliance violations, and brand safety — then generates culturally-safe rewrites with full attribution.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What It Does

| Feature | Description |
|---------|-------------|
| **Risk Analysis** | Detects cultural taboos, PII leaks, violent metaphors, competitor mentions, political/religious content |
| **Multi-Market** | Korea (face culture), Japan (Wa/Kenson), US (DEI), Global baselines |
| **Multi-Platform** | LinkedIn, Instagram, Twitter, Facebook, YouTube norm awareness |
| **Smart Rewriting** | Generates 3-5 alternative versions classified on 5 axes (formality, agency, evidence, competition, tone) |
| **Human-in-the-Loop** | High-risk content escalates to Slack/Email for human review |
| **Attribution** | Every finding cites its knowledge base source with trust scores |

---

## Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/culturalguard.git
cd culturalguard
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required:
| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | LLM API access (or use Azure AI Foundry) |
| `RESEND_API_KEY` | Email escalation (optional) |
| `SLACK_WEBHOOK_URL` | Slack escalation (optional) |

### 3. Populate Knowledge Base

The knowledge base ships with **placeholder examples** (`*.example.json`).
Real data files (`*.json`) are **gitignored** for safety.

```bash
# Copy each example to create your real data file:
cd knowledge_base

# For each category:
for dir in attribution brand cultural platform_norms rewrite risk safety scoring; do
  for f in $dir/*.example.json; do
    cp "$f" "${f%.example.json}.json"
  done
done
```

Then edit each `.json` file with your actual brand data, cultural rules, and risk patterns.

**Knowledge Base Structure:**

```
knowledge_base/
├── attribution/       # Source references — trust scores, verification dates
├── brand/             # Brand identity, tone, naming rules
├── cultural/          # Banned words, outdated terms, trending phrases
├── platform_norms/    # Per-platform per-market posting norms
├── rewrite/           # 5-axis rewrite classification guide
├── risk/              # Risk patterns (competition, PII, political, religious, etc.)
├── safety/            # Prompt injection, harmful content, PII redaction rules
└── scoring/           # Risk scoring formula, penalties, thresholds
```

### 4. Run

**CLI (quick test):**
```bash
python main.py
```

**Streamlit UI:**
```bash
streamlit run app.py
```

**Local unit tests:**
```bash
python test_local.py
```

---

## Architecture

```
┌──────────────────────────────────────────────┐
│              Streamlit UI (app.py)            │
│   Analyze · Create · Translate modes         │
└──────────────┬───────────────────────────────┘
               │
┌──────────────▼───────────────────────────────┐
│           CulturalGuardAgent (agent.py)       │
│                                               │
│  1. Safety Gate                               │
│     check_prompt_injection()                  │
│     check_pii_patterns()                      │
│                                               │
│  2. Knowledge Base Loading                    │
│     load_analysis_context(platform, market)   │
│                                               │
│  3. Risk Analysis                             │
│     Pattern matching + LLM contextual scoring │
│     Score fusion: (db×0.4)+(llm×0.6)+penalty  │
│                                               │
│  4. Decision + Rewrite                        │
│     APPROVE / REVIEW / REVISE / ESCALATE      │
│     Generate 3-5 culturally safe rewrites     │
│                                               │
│  5. Report & Escalation                       │
│     save_report() → reports/                  │
│     MCP → Slack / Email / Discord             │
└──────────────┬───────────────────────────────┘
               │
┌──────────────▼───────────────────────────────┐
│         MCP Integration (mcp_client.py)       │
│   Resend Email · Slack Webhook · Discord Bot  │
└──────────────────────────────────────────────┘
```

### Reasoning Pipeline

CulturalGuard uses three reasoning patterns simultaneously:

1. **ReAct** — Observe (load KB) → Think (analyze) → Act (rewrite/escalate)
2. **Chain-of-Thought** — Step-by-step: parse → match risks → cultural context → score → decide
3. **Self-Reflection** — Post-analysis confidence check: all categories covered? attributions cited?

### Scoring Engine

```
final_score = (db_score × 0.4) + (llm_score × 0.6) + Σ penalties

Market adjustments:
  KR: aggressive_competition × 1.5 (face culture)
  JP: aggressive_competition × 2.0, self_praise × 1.5 (Wa + Kenson)
  US: tone_deaf × 1.3 (DEI sensitivity)

Decision thresholds:
  0.0–0.3  → APPROVE (safe to publish)
  0.3–0.5  → REVIEW_SUGGESTED
  0.5–0.7  → REVISE_REQUIRED
  0.7–1.0  → ESCALATE_TO_HUMAN
```

---

## UI Modes

| Mode | Description |
|------|-------------|
| **Analyze** | Paste content → get risk score, diagnosis, rewrites |
| **Create** | Set 5-axis parameters → generate safe content |
| **Translate** | Translate to multiple markets → auto-analyze each |

---

## File Structure

```
culturalguard/
├── agent.py              # Core analysis agent + tool functions
├── app.py                # Streamlit UI
├── main.py               # CLI entry point
├── mcp_client.py         # MCP integration (Email, Slack, Discord)
├── test_local.py         # Local unit tests
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
├── .gitignore            # Ignores real KB data, .env, reports
├── config/
│   ├── agent_config.json          # Agent configuration
│   └── system_prompt_compact.md   # System prompt
├── knowledge_base/
│   ├── **/*.example.json  # Schema examples (tracked in git)
│   └── **/*.json          # Real data (gitignored)
├── reports/               # Analysis reports (gitignored)
└── ARCHITECTURE.md        # Detailed architecture docs
```

---

## MCP Integration

| Service | Provider | Trigger |
|---------|----------|---------|
| Email | Resend | ESCALATE_TO_HUMAN |
| Slack | Webhook | ESCALATE_TO_HUMAN |
| Discord | Bot API | Human-in-the-Loop |

All MCP channels are optional — the agent works fully in local/offline mode.

---

## Demo

```bash
# Quick CLI demo
python main.py

# Full UI demo
streamlit run app.py
```

**Example input:**
> "Our product crushed the competition this quarter! We're the undisputed market leader 🔥"

**Example output:**
- **Risk Score:** 0.85 (ESCALATE_TO_HUMAN)
- **Risk Factors:** violent_metaphor, aggressive_competition, self_praise
- **Diagnosis:** "crushed the competition" → violent metaphor + competitor comparison violates Korean face culture
- **Rewrites:** 3 culturally-safe alternatives with 5-axis classification

---

## Security

- **No PII committed** — PII patterns are detected and redacted
- **Knowledge base gitignored** — real cultural data stays local
- **Prompt injection detection** — blocks malicious inputs
- **No secrets in code** — all credentials via `.env`

---

## License

MIT License

---

## Acknowledgments

Built with GitHub Copilot during the [Agents League](https://github.com/microsoft/agentsleague) challenge.

- Azure AI Foundry SDK
- Streamlit
- MCP (Model Context Protocol)
