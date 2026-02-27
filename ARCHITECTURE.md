# CulturalGuard — Single-Agent Architecture

## Overview

**Purpose**: AI Agent that detects cultural risks in social media content across Korea, Japan, and US markets.

**Hackathon Track**: Reasoning Agents with Microsoft Foundry

**Key Differentiators**:
1. **Diagnosis-First** — Not word substitution, but causal understanding
2. **Human-in-the-Loop** — Slack webhook for strategic input, Resend for escalation
3. **Full Transparency** — Show reasoning + tools trace in UI

---

## System Architecture (Single-Agent, Local-First)

```mermaid
flowchart TB
    subgraph "Client Layer"
        UI[Streamlit App<br/>app.py]
    end
    
    subgraph "Agent Layer (Single-Agent Core)"
        Agent[CulturalGuard Agent<br/>agent.py]
        
        subgraph "Reasoning Patterns"
            ReAct[ReAct<br/>Observe → Think → Act]
            CoT[Chain-of-Thought<br/>6-step analysis]
            SelfRef[Self-Reflection<br/>Verify own work]
        end
        
        subgraph "Tool Layer"
            Safety[Safety Tools<br/>• check_prompt_injection<br/>• check_pii_patterns]
            KB[Knowledge Tools<br/>• load_analysis_context<br/>• load_knowledge_base<br/>• get_kb_governance_status]
            Action[Action Tools<br/>• save_report<br/>• save_eval_report]
            MCPClient[MCP Client (optional)<br/>• email/slack]
        end
    end
    
    subgraph "MCP Layer (Optional)"
        Slack[Slack Webhook]
        Resend[Resend Email]
        FS[MCP: Filesystem<br/>Knowledge Base]
    end
    
    subgraph "Knowledge Layer"
        Risk[Risk KB<br/>7 categories]
        Norms[Platform Norms<br/>5 markets]
        Trend[Cultural Trends<br/>Time-sensitive]
    end
    
    UI <--> Agent
    Agent <--> Safety
    Agent <--> KB
    Agent <--> Action
    Agent <--> MCPClient
    MCPClient <--> Slack
    MCPClient <--> Resend
    KB <--> FS
    KB --> Risk
    KB --> Norms
    KB --> Trend
```

---

## Phase-Based Tool Execution

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1: SAFETY (always first)                                     │
├─────────────────────────────────────────────────────────────────────┤
│  check_prompt_injection(content) → {detected: bool, patterns: []}   │
│  check_pii_patterns(content) → {found: bool, matches: []}          │
│                                                                      │
│  If injection detected → BLOCK (no analysis)                        │
│  If PII found → REDACT → continue analysis                         │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 2: KNOWLEDGE (grounding)                                    │
├─────────────────────────────────────────────────────────────────────┤
│  load_analysis_context(platform, market) → compressed KB (<8KB)    │
│  get_current_datetime() → UTC timestamp for TTL checks             │
│  get_kb_governance_status() → {total_files, categories}            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 3: REASONING (multi-step)                                   │
├─────────────────────────────────────────────────────────────────────┤
│  Step 1: Parse — language, tone, key phrases                        │
│  Step 2: Match — scan KB risk patterns                             │
│  Step 3: Context — platform norms + market multipliers              │
│  Step 4: Attribute — cite source_id for every finding              │
│  Step 5: Expiry — check cultural term TTL                         │
│  Step 6: Score — (db×0.4 + llm×0.6) + penalties                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 4: ACTION (execution)                                        │
├─────────────────────────────────────────────────────────────────────┤
│  save_report(result) → reports/YYYY-MM-DD.json                     │
│                                                                      │
│  If ESCALATE_TO_HUMAN:                                             │
│    → MCPClient.escalate_to_human_sync(...) (Email/Slack)           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 5: VERIFICATION (self-check)                                 │
├─────────────────────────────────────────────────────────────────────┤
│  • All 7 risk categories checked?                                  │
│  • Every finding has source_id attribution?                        │
│  • Rewrites avoid diagnosed risks?                                 │
│  • Assign confidence 1-10                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## MCP Integration (Optional)

### MCP Servers Configuration

```json
{
  "servers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./culturalguard"],
      "description": "Access knowledge base files"
    },
    
    "resend-email": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@skanda-yutori/mcp-send-email"],
      "env": { "RESEND_API_KEY": "${env:RESEND_API_KEY}" },
      "description": "Send escalation emails when human review required"
    },
    
    "microsoft-docs": {
      "type": "http",
      "url": "https://learn.microsoft.com/api/mcp",
      "description": "Reference documentation lookup"
    }
  }
}
```

### MCP Tool Mapping

| Channel | Trigger | Purpose |
|---------|---------|---------|
| **Resend Email** | `risk_level == ESCALATE_TO_HUMAN` | Email human reviewer |
| **Slack Webhook** | `risk_level == ESCALATE_TO_HUMAN` | Human review alert |
| **Filesystem MCP** | Knowledge access | Read KB files |

---

## Human-in-the-Loop Workflows

### 1. Escalation Email Flow

```
Agent decides ESCALATE
        ↓
send_escalation_email()
        ↓
MCP → Resend API
        ↓
Email sent to: EMAIL_TO env var
        ↓
Subject: [CulturalGuard] ESCALATION: {risk_level} — {platform}/{market}
Body: Risk score + diagnosis + link to full report
```

### 2. Strategic Human Input Flow (Optional)

```
Agent confidence < 5 (future extension)
        ↓
Human review requested via Slack
        ↓
Feedback returned to the team for manual decisions
```

### 3. Community Validation Flow (Optional)

```
Optional community feedback loop using Slack threads
        ↓
Captured in the demo as a future extension
```

---

## Streamlit UI Architecture

```python
# app.py structure
import streamlit as st
from agent import CulturalGuardAgent

# ── Layout ─────────────────────────────────────────────────────
st.set_page_config(page_title="CulturalGuard", layout="wide")

# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎯 CulturalGuard")
    
    # Platform/Market selector
    platform = st.selectbox("Platform", ["linkedin", "instagram"])
    market = st.selectbox("Market", ["kr", "jp", "us", "global"])
    
    # KB Status
    st.divider()
    st.subheader("📚 Knowledge Base")
    if st.button("🔄 Refresh"):
        status = agent.get_kb_governance_status()
        st.json(status)
    
    # Escalation Status
    st.divider()
    st.subheader("🔔 Escalations")
    escalation_placeholder = st.container()

# ── Main Chat Area ───────────────────────────────────────────
st.title("💬 Cultural Risk Analyzer")

# Chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User input
if prompt := st.chat_input("Enter content to analyze..."):
    # Process and display results
    result = agent.analyze(prompt, platform, market)
    
    # Expanders for details
    with st.expander("📊 Risk Analysis"):
        # Risk score, level, factors
    with st.expander("🧠 Reasoning"):
        # Chain of thought steps
    with st.expander("🔧 Tools Trace"):
        # Function calls with timing
    with st.expander("✍️ Rewrites"):
        # Suggested rewrites
```

---

## Scoring Engine

### Formula

```
db_score  = max(matched_pattern.risk_score)
llm_score = LLM contextual judgment (0.0 – 1.0)

penalty_sum = sum(triggered penalties), capped at 1.0

final_score = (db_score × 0.4) + (llm_score × 0.6) + penalty_sum
final_score = min(final_score, 1.0)
```

### Decision Thresholds

| Decision | Score Range | Action |
|----------|-------------|--------|
| **APPROVE** | 0.0 – 0.30 | Safe to publish |
| **REVIEW_SUGGESTED** | 0.31 – 0.50 | Minor risks |
| **REVISE_REQUIRED** | 0.51 – 0.70 | Must revise |
| **ESCALATE_TO_HUMAN** | 0.71 – 1.00 | Human review required |

### Multi-Violation Rules

- 3+ different risk categories → minimum **REVISE_REQUIRED**
- tone_deaf + aggressive_competition → immediate **ESCALATE_TO_HUMAN**
- PII detected → immediate **ESCALATE_TO_HUMAN**

---

## Knowledge Base Structure

```
knowledge_base/                      (876 lines)
│
├── attribution/
│   └── sources.json                (5 trusted sources)
│
├── risk/                           (7 risk categories)
│   ├── aggressive_competition.json (4 patterns)
│   ├── violent_metaphor.json       (3 patterns)
│   ├── self_praise.json            (3 patterns)
│   ├── tone_deaf.json              (4 patterns)
│   ├── political_content.json      (3 patterns)
│   ├── religious_content.json      (2 patterns)
│   └── pii_patterns.json           (4 regex patterns)
│
├── platform_norms/                 (5 platform×market)
│   ├── linkedin_korea.json         (Face culture)
│   ├── linkedin_japan.json          (Wa, Kenson)
│   ├── linkedin_us.json            (DEI sensitivity)
│   ├── instagram_korea.json        (Visual-first)
│   └── global.json                 (Baseline)
│
├── brand/
│   └── brand_guide.json            (SeoaFlow tone)
│
├── cultural/                       (Time-sensitive)
│   ├── trending_kr_2026q1.json     (Active terms)
│   ├── outdated_terms.json        (Expired terms)
│   └── banned_words.json           (Prohibited terms)
│
├── rewrite/
│   └── rewrite_guide.json          (5 axes classification)
│
├── scoring/
│   └── risk_calculation.json       (Formula + thresholds)
│
└── safety/
    └── safety_rules.json           (Injection + harmful + PII)
```

---

## File Structure

```
culturalguard/
│
├── app.py                      # NEW: Streamlit UI (ChatGPT-style)
├── agent.py                    # Core agent with 9 tools
├── main.py                     # CLI entry point
├── demo.py                     # Demo script
│
├── docs/                       # Demo + technical docs
│   ├── DEMO_5MIN_SCRIPT.md
│   ├── TECHNICAL_GUIDE.md
│   ├── QNA.md
│   └── LEARNING_NOTES.md
│
├── scripts/
│   └── demo_run.sh             # Demo automation
│
├── config/
│   ├── system_prompt_compact.md    # Agent instructions
│   └── agent_config.json           # Thresholds, weights, MCP config
│
├── knowledge_base/                 # 20 files · 876 lines
│   ├── attribution/
│   ├── risk/                      # 7 categories
│   ├── platform_norms/            # 5 markets
│   ├── brand/
│   ├── cultural/                  # Time-sensitive
│   ├── rewrite/
│   ├── scoring/
│   └── safety/
│
├── reports/                       # Generated analysis reports
│
├── .env.example                   # Environment template
├── requirements.txt               # Dependencies
│
└── .vscode/
    └── mcp.json                   # MCP servers config
```

---

## Hackathon Requirements Mapping

| Requirement | Implementation | Evidence |
|-------------|----------------|----------|
| **Azure AI Foundry** | Config-ready (future backend) | config/agent_config.json |
| **Reasoning Patterns** | ReAct + CoT + Self-Reflection | agent.py + system_prompt |
| **Knowledge Grounding** | 20 KB files with attribution | knowledge_base/ |
| **MCP Integration** | Email/Slack/Filesystem (optional) | mcp_client.py + .vscode/mcp.json |
| **Safety Layer** | Prompt injection, PII | agent.py:128-172 |
| **Evaluation** | Precision, recall, latency (report-ready) | README + config |
| **Monitoring** | Trace log with timing | agent.py:23-49 |
| **UI (Bonus)** | Streamlit chat interface | app.py |
| **Human-in-Loop (Bonus)** | Slack/Email escalation | mcp_client.py |

---

## Evaluation Criteria Alignment

| Criteria | Weight | CulturalGuard | Score Impact |
|----------|--------|--------------|--------------|
| Accuracy & Relevance | 20% | KB grounding, 7 risk categories | HIGH |
| Reasoning & Multi-step | 20% | ReAct + CoT + Self-Reflection | HIGH |
| Creativity & Originality | 15% | Diagnosis-first rewrite | HIGH |
| User Experience | 15% | Streamlit UI + expanders | MEDIUM |
| Reliability & Safety | 20% | Safety filters + MCP | HIGH |
| Community Vote | 10% | Community sharing | MEDIUM |

---

## Demo Flow

1. **Open Streamlit**: `streamlit run app.py`
2. **Enter content**: "We crushed the competition!"
3. **Select**: LinkedIn + Korea
4. **Show**:
   - Risk score + level
   - Risk factors with confidence
   - Chain of reasoning (6 steps)
   - Tools called with timing
   - Suggested rewrites
5. **Create Mode**: generate culturally safe content and re‑analyze
6. **Translate Mode**: compare KR/JP/US risks side‑by‑side
7. **Demonstrate escalation** (if score > 0.7):
   - Show email/Slack (optional)
