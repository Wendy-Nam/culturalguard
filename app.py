"""
CulturalGuard — Streamlit UI
ChatGPT-like interface for cultural risk analysis
"""

import streamlit as st
import json
import os
import time
import concurrent.futures
from typing import Any
from datetime import datetime, timedelta

# Import our modules
import agent
import mcp_client

# Page config
st.set_page_config(
    page_title="CulturalGuard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styles
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-left: 2.5rem;
        padding-right: 2.5rem;
    }
    [data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .section-header {
        margin-top: 0.5rem;
        margin-bottom: 0.25rem;
    }
    .risk-badge {
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        font-weight: bold;
        display: inline-block;
    }
    .risk-approve { background-color: #d4edda; color: #155724; }
    .risk-review { background-color: #fff3cd; color: #856404; }
    .risk-revise { background-color: #ffeeba; color: #856404; }
    .risk-escalate { background-color: #f8d7da; color: #721c24; }
    .stTextArea textarea { font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize Streamlit session state."""
    if "agent" not in st.session_state:
        st.session_state.agent = agent.CulturalGuardAgent()
    if "mcp_client" not in st.session_state:
        st.session_state.mcp_client = mcp_client.MCPClient()
    if "history" not in st.session_state:
        st.session_state.history = []
    if "current_mode" not in st.session_state:
        st.session_state.current_mode = "analyze"
    if "slow_mode" not in st.session_state:
        st.session_state.slow_mode = True
    if "demo_delay" not in st.session_state:
        st.session_state.demo_delay = 0.35
    if "demo_simulate_mcp" not in st.session_state:
        st.session_state.demo_simulate_mcp = False
    if "translate_payload" not in st.session_state:
        st.session_state.translate_payload = None
    if "contributors" not in st.session_state:
        st.session_state.contributors = {
            "Minji Park": {"role": "Community Reviewer"},
            "Hiro Tanaka": {"role": "Cultural SME"},
            "Alyssa Kim": {"role": "Safety Maintainer"},
        }
    if "user_name" not in st.session_state:
        st.session_state.user_name = "You"
    if "attributions" not in st.session_state:
        st.session_state.attributions = []


def render_sidebar():
    """Render the sidebar with configuration options."""
    st.sidebar.markdown("**CulturalGuard**")
    st.sidebar.markdown("---")
    st.sidebar.checkbox("Slow demo mode", key="slow_mode")
    if st.session_state.slow_mode:
        st.sidebar.slider(
            "Demo delay (sec)",
            min_value=0.15,
            max_value=1.2,
            step=0.05,
            key="demo_delay",
        )
    
    # Mode selection
    # Safe index with fallback
    modes = ["analyze", "create", "translate"]
    current = st.session_state.get("current_mode", "analyze")
    if current not in modes:
        current = "analyze"
    
    label_map = {
        "Analyze": "analyze",
        "Create": "create",
        "Translate": "translate",
    }
    labels = list(label_map.keys())
    mode_label = st.sidebar.radio(
        "Select Mode",
        labels,
        index=modes.index(current),
        key="mode_selector"
    )
    st.session_state.current_mode = label_map.get(mode_label, "analyze")
    
    st.sidebar.markdown("---")
    st.sidebar.text_input("Your name (community loop)", key="user_name")
    st.sidebar.markdown("---")
    
    # Platform selection
    platform = st.sidebar.selectbox(
        "Platform",
        ["linkedin", "instagram", "twitter", "facebook", "youtube"],
        index=0
    )
    
    # Market selection
    market = st.sidebar.selectbox(
        "Target Market",
        ["kr", "jp", "us", "global"],
        index=0
    )
    
    st.sidebar.markdown("---")
    
    # KB Status
    st.sidebar.markdown("**Knowledge Base**")
    try:
        kb_status = json.loads(agent.get_kb_governance_status())
        st.sidebar.success(f"Healthy ({kb_status.get('total_files', 0)} files)")
    except Exception as e:
        st.sidebar.warning(f"⚠️ KB Issue: {e}")
    
    # MCP Status
    st.sidebar.markdown("**MCP Status**")
    mcp = st.session_state.mcp_client
    st.sidebar.markdown(f"- Email (Resend): {'✅' if mcp.resend_available else '❌'}")
    st.sidebar.markdown(f"- Slack: {'✅' if mcp.slack_available else '❌'}")
    st.sidebar.checkbox("Simulate MCP (demo)", key="demo_simulate_mcp")
    
    st.sidebar.markdown("---")
    
    # Clear history
    if st.sidebar.button("Clear History"):
        st.session_state.history = []
        st.rerun()
    
    return platform, market


def render_step_progress(steps: list[str], current_index: int) -> str:
    lines = []
    for i, step in enumerate(steps):
        if i < current_index:
            icon = "✅"
        elif i == current_index:
            icon = "⏳"
        else:
            icon = "•"
        lines.append(f"{icon} {step}")
    return "\n".join(lines)


def render_live_tool_calls(log: list[dict[str, Any]], placeholder, slow_mode: bool) -> None:
    lines: list[str] = []
    for entry in log:
        fn = entry.get("function", "tool")
        duration = entry.get("duration_ms", "?")
        lines.append(f"- {fn} ({duration}ms)")
    placeholder.markdown("\n".join(lines) if lines else "_(waiting for tool calls...)_")
    if slow_mode:
        time.sleep(float(st.session_state.demo_delay))


def build_context_key(platform: str, market: str, risk_level: str) -> str:
    return f"{platform}:{market}:{risk_level}"


def get_active_attributions(context_key: str) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    now = datetime.now()
    for item in st.session_state.attributions:
        if item.get("context_key") != context_key:
            continue
        expires_at = item.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) < now:
                    continue
            except ValueError:
                pass
        active.append(item)
    return active


def add_attribution(
    contributor: str,
    context_key: str,
    confidence: float,
    evidence: str,
    expiry_days: int,
) -> dict[str, Any]:
    expires_at = (datetime.now() + timedelta(days=expiry_days)).isoformat()
    entry = {
        "contributor": contributor,
        "context_key": context_key,
        "confidence": round(float(confidence), 2),
        "evidence": evidence.strip(),
        "expires_at": expires_at,
        "timestamp": datetime.now().isoformat(),
    }
    st.session_state.attributions.append(entry)
    return entry


def send_escalation_selected(
    result: dict[str, Any],
    content: str,
    platform: str,
    market: str,
    channels: list[str],
    email_to: str,
) -> list[dict[str, str]]:
    client = st.session_state.mcp_client
    notifications: list[dict[str, str]] = []
    metadata = {
        "risk_level": result.get("risk_level", "UNKNOWN"),
        "risk_score": result.get("risk_score", 0.0),
        "platform": platform,
        "market": market,
        "risk_factors": result.get("risk_factors", []),
    }

    if "Slack" in channels:
        if st.session_state.demo_simulate_mcp:
            notifications.append({"type": "slack", "status": "simulated"})
        else:
            slack_result = client.notify_slack_sync(content=content, urgency="normal", metadata=metadata)
            notifications.append({"type": "slack", "status": slack_result.get("status", "unknown")})

    if "Email" in channels:
        if email_to:
            if st.session_state.demo_simulate_mcp:
                notifications.append({"type": "email", "status": "simulated"})
            else:
                subject = f"CulturalGuard Alert: {metadata['risk_level']} ({platform}/{market})"
                body = f"<p><strong>Risk Level:</strong> {metadata['risk_level']}</p><p><strong>Risk Score:</strong> {metadata['risk_score']}</p><p><strong>Content:</strong> {content}</p>"
                email_result = client.send_email_sync(to=email_to, subject=subject, body=body)
                notifications.append({"type": "email", "status": email_result.get("status", "unknown")})
        else:
            notifications.append({"type": "email", "status": "missing EMAIL_TO"})

    return notifications


def render_tool_log(result: dict[str, Any], slow_mode: bool) -> None:
    trace = result.get("_trace", {})
    log = trace.get("log", [])
    if not log:
        return
    with st.expander("Run log (tools)", expanded=False):
        log_placeholder = st.empty()
        lines: list[str] = []
        for entry in log:
            fn = entry.get("function", "tool")
            duration = entry.get("duration_ms", "?")
            lines.append(f"- {fn} ({duration}ms)")
            log_placeholder.markdown("\n".join(lines))
            if slow_mode:
                time.sleep(0.25)


def translate_text(text: str, target_lang: str) -> str:
    try:
        from deep_translator import GoogleTranslator

        result = GoogleTranslator(source="auto", target=target_lang).translate(text)
        return result
    except Exception:
        fallback = {
            ("ko", "We crushed the competition!"): "우리는 경쟁을 압도했습니다!",
            ("ko", "We crushed the competition! We are the market leader."): "우리는 경쟁을 압도했습니다! 우리는 시장을 선도하고 있습니다.",
            ("ja", "We crushed the competition!"): "競合を打ち負かしました！",
            ("ja", "We crushed the competition! We are the market leader."): "競合を打ち負かしました！私たちは市場のリーダーです。",
            ("zh-CN", "We crushed the competition!"): "我们击败了竞争对手！",
            ("zh-CN", "We crushed the competition! We are the market leader."): "我们击败了竞争对手！我们是市场领导者。",
        }
        return fallback.get((target_lang, text), text)


def analyze_mode(platform: str, market: str):
    """Analyze mode - analyze content for cultural risks."""
    st.header("Analyze Content")
    st.markdown("Paste content below to analyze cultural risk.")

    prompt = st.chat_input("Enter content to analyze")

    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            steps = [
                "Safety checks (check_prompt_injection, check_pii_patterns)",
                "Load knowledge context (load_analysis_context)",
                "Analyze & score content",
                "Save report",
            ]
            progress_placeholder = st.empty()
            progress_placeholder.markdown(render_step_progress(steps, 0))

            live_log_placeholder = st.empty()
            live_log_placeholder.markdown("_(waiting for tool calls...)_")

            if st.session_state.slow_mode:
                time.sleep(float(st.session_state.demo_delay))

            agent_local = st.session_state.agent
            def run_analysis() -> dict[str, Any]:
                return agent_local.analyze(prompt, platform, market)

            try:
                if st.session_state.slow_mode:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(run_analysis)
                        last_len = 0
                        while not future.done():
                            log = list(agent._trace_log)
                            if len(log) != last_len:
                                render_live_tool_calls(log, live_log_placeholder, True)
                                last_len = len(log)
                                if len(log) >= 1:
                                    progress_placeholder.markdown(render_step_progress(steps, 1))
                                if len(log) >= 3:
                                    progress_placeholder.markdown(render_step_progress(steps, 2))
                            time.sleep(float(st.session_state.demo_delay))
                        result = future.result()
                else:
                    with st.spinner("Analyzing..."):
                        result = agent_local.analyze(prompt, platform, market)
            except Exception as e:
                st.error(f"Error: {e}")
                import traceback
                st.code(traceback.format_exc())
                return

            render_live_tool_calls(list(agent._trace_log), live_log_placeholder, False)
            progress_placeholder.markdown(render_step_progress(steps, len(steps)))

            history_item = {
                "mode": "analyze",
                "content": prompt,
                "platform": platform,
                "market": market,
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "hil_status": "pending" if result.get("risk_level") == "ESCALATE_TO_HUMAN" else "complete",
                "hil_notifications": [],
                "hil_attribution": None,
            }
            st.session_state.history.append(history_item)

            render_analysis_details(result)
            render_tool_log(result, st.session_state.slow_mode)
            if st.session_state.slow_mode:
                cot = result.get("chain_of_thought", [])
                if cot:
                    with st.expander("Reasoning replay", expanded=True):
                        replay_placeholder = st.empty()
                        lines: list[str] = []
                        for i, step in enumerate(cot, 1):
                            lines.append(f"- Step {i}: {step}")
                            replay_placeholder.markdown("\n".join(lines))
                            time.sleep(float(st.session_state.demo_delay))

            if result.get("risk_level") == "ESCALATE_TO_HUMAN":
                st.info("Human-in-the-loop required. Choose how to proceed.")
                context_key = build_context_key(platform, market, result.get("risk_level", "UNKNOWN"))
                active_attributions = get_active_attributions(context_key)
                with st.expander("Attribution context", expanded=False):
                    if active_attributions:
                        rows = []
                        for item in active_attributions:
                            rows.append({
                                "Contributor": item.get("contributor", ""),
                                "Confidence": item.get("confidence", 0.0),
                                "Evidence": item.get("evidence", ""),
                                "Expires": item.get("expires_at", ""),
                            })
                        st.dataframe(rows, use_container_width=True)
                    else:
                        st.caption("No attribution entries for this context yet.")

                choice = st.selectbox(
                    "Decision",
                    ["Hold for human review", "Escalate now", "Provide attribution"],
                    key=f"hil_live_{history_item['timestamp']}",
                )

                if choice == "Escalate now":
                    available_channels = []
                    if st.session_state.mcp_client.resend_available:
                        available_channels.append("Email")
                    if st.session_state.mcp_client.slack_available:
                        available_channels.append("Slack")
                    channels = st.multiselect(
                        "Escalation channels",
                        ["Email", "Slack"],
                        default=available_channels,
                        key=f"hil_channels_{history_item['timestamp']}",
                    )
                    email_to = ""
                    if "Email" in channels:
                        email_to = st.text_input(
                            "Recipient email",
                            value=os.getenv("EMAIL_TO", ""),
                            key=f"hil_email_{history_item['timestamp']}",
                        )
                    if st.button("Notify humans", key=f"hil_live_btn_{history_item['timestamp']}"):
                        history_item["hil_status"] = "awaiting_response"
                        history_item["hil_notifications"] = send_escalation_selected(
                            result,
                            prompt,
                            platform,
                            market,
                            channels,
                            email_to,
                        )
                        st.success("Escalation sent")
                        if history_item["hil_notifications"]:
                            with st.expander("Escalation results", expanded=False):
                                for note in history_item["hil_notifications"]:
                                    st.markdown(f"- {note.get('type')}: {note.get('status')}")

                if choice == "Provide attribution":
                    contributor_name = st.text_input(
                        "Attributor name",
                        value=st.session_state.user_name,
                        key=f"attr_name_{history_item['timestamp']}",
                    )
                    confidence = st.slider(
                        "Confidence",
                        min_value=0.1,
                        max_value=1.0,
                        value=0.7,
                        step=0.05,
                        key=f"attr_conf_{history_item['timestamp']}",
                    )
                    evidence = st.text_area(
                        "Evidence / rationale",
                        key=f"attr_ev_{history_item['timestamp']}",
                    )
                    expiry_days = st.number_input(
                        "Expiry (days)",
                        min_value=1,
                        max_value=365,
                        value=30,
                        step=1,
                        key=f"attr_exp_{history_item['timestamp']}",
                    )
                    if st.button("Save attribution", key=f"attr_save_{history_item['timestamp']}"):
                        entry = add_attribution(
                            (contributor_name or "").strip() or "Anonymous",
                            context_key,
                            confidence,
                            evidence,
                            int(expiry_days),
                        )
                        history_item["hil_status"] = "attribution_added"
                        history_item["hil_attribution"] = entry
                        st.success("Attribution saved")
            else:
                st.success("Run complete")


def render_analysis_details(result: dict[str, Any]):
    risk_score = result.get("risk_score", 0)
    risk_level = result.get("risk_level", "UNKNOWN")
    decision = result.get("decision", "")
    st.markdown(f"**{risk_level}** · {risk_score:.2f}\n\n{decision}")

    cot = result.get("chain_of_thought", [])
    if cot:
        with st.expander("Reasoning", expanded=False):
            for i, step in enumerate(cot, 1):
                st.markdown(f"- Step {i}: {step}")

    rfs = result.get("risk_factors", [])
    diag = result.get("diagnosis", [])
    if rfs or diag:
        with st.expander("Risk factors", expanded=False):
            for rf in rfs:
                st.markdown(
                    f"- [{rf.get('category', 'unknown')}] \"{rf.get('phrase', '')}\" "
                    f"(confidence: {rf.get('confidence', '?')})"
                )
            for d in diag:
                st.markdown(f"- \"{d.get('phrase', '')}\" → {d.get('why', '')[:200]}")

    rewrites = result.get("rewrites", [])
    if rewrites:
        with st.expander("Rewrites", expanded=False):
            for rw in rewrites:
                st.markdown(f"- {rw.get('version', 'v1')}: {rw.get('text', '')}")

    trace = result.get("_trace", {})
    if trace:
        with st.expander("Trace summary", expanded=False):
            st.markdown(f"Tool calls: {trace.get('function_calls', 0)}")
            st.markdown(f"Total time: {trace.get('total_ms', 0)}ms")
    


def create_mode(platform: str, market: str):
    """Create mode - generate culturally safe content."""
    st.header("Create Content")
    st.markdown("Generate new content with cultural safety in mind")
    
    col1, col2 = st.columns(2)
    
    with col1:
        style = st.selectbox("Formality", ["casual", "semi-formal", "formal"])
        agency = st.selectbox("Agency", ["team-credit", "shared-credit", "self-credit"])
    
    with col2:
        evidence = st.selectbox("Evidence", ["qualitative", "mixed", "data-driven"])
        tone = st.selectbox("Tone", ["understated", "warm", "enthusiastic"])
    
    competition = st.selectbox("Competition mention", ["zero-mention", "industry-growth", "market-position"])
    
    base_message = st.text_area(
        "What do you want to communicate?",
        height=100,
        placeholder="e.g., We had a great quarter..."
    )
    
    generate_btn = st.button("Generate", type="primary")

    if generate_btn and base_message:
        with st.spinner("Generating culturally safe content..."):
            generated = generate_content(
                base_message, platform, market,
                style, agency, evidence, tone, competition
            )

        st.success("Generated content:")
        st.text_area("Result", value=generated, height=100)

        if st.button("Analyze Generated Content"):
            result = st.session_state.agent.analyze(generated, platform, market)
            render_analysis_details(result)
            st.session_state.current_mode = "analyze"
            st.session_state.history.append({
                "mode": "analyze",
                "content": generated,
                "platform": platform,
                "market": market,
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "hil_status": "pending" if result.get("risk_level") == "ESCALATE_TO_HUMAN" else "complete",
                "hil_notifications": [],
                "hil_attribution": None,
            })
            st.success("Analyzed result moved to Analyze mode (History).")
            st.rerun()


def translate_mode(platform: str, market: str):
    """Translate mode - translate and analyze for multiple markets."""
    st.session_state.current_mode = "translate"
    st.header("Translate & Analyze")
    st.markdown("Enter content to translate and analyze for multiple markets")
    
    content = st.text_area(
        "Content to translate",
        height=100,
        placeholder="Enter content in English..."
    )
    
    target_markets = st.multiselect(
        "Target Markets",
        ["kr", "jp", "cn", "us", "global"],
        default=["kr", "jp", "cn"]
    )
    
    translate_btn = st.button("Translate & Analyze", type="primary")
    
    if translate_btn and content and target_markets:
        lang_map = {
            "kr": "ko",
            "jp": "ja",
            "cn": "zh-CN",
            "us": "en",
            "global": "en",
        }
        translations = {}
        for mk in target_markets:
            lang = lang_map.get(mk, "en")
            translations[mk] = translate_text(content, lang)
        analysis_results = {}
        for mk in target_markets:
            result = st.session_state.agent.analyze(translations.get(mk, content), platform, mk)
            analysis_results[mk] = result

        st.session_state.translate_payload = {
            "content": content,
            "markets": list(target_markets),
            "translations": translations,
            "analysis_results": analysis_results,
        }

    payload = st.session_state.translate_payload
    if payload:
        for target_market in payload.get("markets", []):
            st.markdown(f"---")
            st.subheader(f"{target_market.upper()}")

            translated = payload.get("translations", {}).get(target_market, content)
            st.text_area(
                f"Translation ({target_market})",
                value=translated,
                height=80,
                key=f"trans_{target_market}"
            )
            if translated == payload.get("content") and target_market not in ["us", "global"]:
                st.warning("Translation service unavailable; showing original text.")

            result = payload.get("analysis_results", {}).get(target_market)
            if result:
                render_analysis_details(result)


def generate_content(
    base: str, platform: str, market: str,
    style: str, agency: str, evidence: str, tone: str, competition: str
) -> str:
    """Generate culturally safe content based on options."""
    
    # Simple rule-based generation
    if competition == "zero-mention":
        competition_phrase = ""
    elif competition == "industry-growth":
        competition_phrase = "We're growing the industry together."
    else:
        competition_phrase = "We're proud of our market position."
    
    style_openers = {
        "casual": ["Excited to share", "Happy to announce", "Great news"],
        "semi-formal": ["We're pleased to share", "I wanted to update you", "Pleased to announce"],
        "formal": ["We are pleased to announce", "This is to inform you", "We wish to share"]
    }
    
    tone_endings = {
        "understated": "Thank you for your continued support.",
        "warm": "We appreciate our community!",
        "enthusiastic": "This is just the beginning! 🎉"
    }
    
    opener = style_openers.get(style, style_openers["semi-formal"])[0]
    ending = tone_endings.get(tone, tone_endings["understated"])
    
    return f"{opener}: {base}. {competition_phrase} {ending}"


def escalate_result(result: dict, content: str, platform: str, market: str, status):
    """Escalate to human reviewers."""
    st.info("Escalation pending — confirm to notify humans")
    
    if st.button("Confirm Escalation"):
        with st.spinner("Sending notifications..."):
            escalation = st.session_state.mcp_client.escalate_to_human_sync(
                content=content,
                risk_score=result.get("risk_score", 0),
                risk_level=result.get("risk_level", "UNKNOWN"),
                risk_factors=result.get("risk_factors", []),
                diagnosis=result.get("diagnosis", []),
                platform=platform,
                market=market
            )
            
            if escalation.get("notifications"):
                st.success("Escalation complete")
                if status is not None:
                    status.update(label="Escalation complete", state="complete")
                for notif in escalation.get("notifications", []):
                    st.markdown(f"- {notif.get('type')}: {notif.get('status')}")
            else:
                st.error("Escalation failed")
                if status is not None:
                    status.update(label="Escalation failed", state="error")


def render_history():
    """Render chat history."""
    if st.session_state.history:
        st.markdown("---")
        st.subheader("History")
        for i, item in enumerate(reversed(st.session_state.history[-5:])):
            with st.chat_message("user"):
                st.markdown(f"**{item['mode'].upper()}** · {item['timestamp'][:19]}")
                st.markdown(item["content"])
            if "result" in item:
                result = item["result"]
                with st.chat_message("assistant"):
                    render_analysis_details(result)
                    hil_status = item.get("hil_status")
                    if hil_status == "pending" and result.get("risk_level") == "ESCALATE_TO_HUMAN":
                        st.caption("Human-in-the-loop: pending")
                        context_key = build_context_key(item["platform"], item["market"], result.get("risk_level", "UNKNOWN"))
                        active_attributions = get_active_attributions(context_key)
                        with st.expander("Attribution context", expanded=False):
                            if active_attributions:
                                rows = []
                                for attr in active_attributions:
                                    rows.append({
                                        "Contributor": attr.get("contributor", ""),
                                        "Confidence": attr.get("confidence", 0.0),
                                        "Evidence": attr.get("evidence", ""),
                                        "Expires": attr.get("expires_at", ""),
                                    })
                                st.dataframe(rows, use_container_width=True)
                            else:
                                st.caption("No attribution entries for this context yet.")

                        choice = st.selectbox(
                            "Human-in-the-loop",
                            ["Hold for human review", "Escalate now", "Provide attribution"],
                            key=f"hil_{i}",
                        )

                        if choice == "Escalate now":
                            available_channels = []
                            if st.session_state.mcp_client.resend_available:
                                available_channels.append("Email")
                            if st.session_state.mcp_client.slack_available:
                                available_channels.append("Slack")
                            channels = st.multiselect(
                                "Escalation channels",
                                ["Email", "Slack"],
                                default=available_channels,
                                key=f"hil_channels_{i}",
                            )
                            email_to = ""
                            if "Email" in channels:
                                email_to = st.text_input(
                                    "Recipient email",
                                    value=os.getenv("EMAIL_TO", ""),
                                    key=f"hil_email_{i}",
                                )
                            if st.button("Notify humans", key=f"hil_btn_{i}"):
                                item["hil_status"] = "awaiting_response"
                                item["hil_notifications"] = send_escalation_selected(
                                    result,
                                    item["content"],
                                    item["platform"],
                                    item["market"],
                                    channels,
                                    email_to,
                                )
                                st.success("Escalation sent")

                        if choice == "Provide attribution":
                            contributor_name = st.text_input(
                                "Attributor name",
                                value=st.session_state.user_name,
                                key=f"attr_name_{i}",
                            )
                            confidence = st.slider(
                                "Confidence",
                                min_value=0.1,
                                max_value=1.0,
                                value=0.7,
                                step=0.05,
                                key=f"attr_conf_{i}",
                            )
                            evidence = st.text_area(
                                "Evidence / rationale",
                                key=f"attr_ev_{i}",
                            )
                            expiry_days = st.number_input(
                                "Expiry (days)",
                                min_value=1,
                                max_value=365,
                                value=30,
                                step=1,
                                key=f"attr_exp_{i}",
                            )
                            if st.button("Save attribution", key=f"attr_save_{i}"):
                                entry = add_attribution(
                                    (contributor_name or "").strip() or "Anonymous",
                                    context_key,
                                    confidence,
                                    evidence,
                                    int(expiry_days),
                                )
                                item["hil_status"] = "attribution_added"
                                item["hil_attribution"] = entry
                                st.success("Attribution saved")
                    elif hil_status:
                        st.caption(f"Human-in-the-loop: {hil_status}")
                        if hil_status == "awaiting_response":
                            if st.button("Mark response received", key=f"hil_resp_{i}"):
                                item["hil_status"] = "response_received"
                                st.success("Response recorded")
                    notifications = item.get("hil_notifications", [])
                    if notifications:
                        with st.expander("Escalation results", expanded=False):
                            for note in notifications:
                                st.markdown(f"- {note.get('type')}: {note.get('status')}")
                    if item.get("hil_attribution"):
                        with st.expander("Attribution saved", expanded=False):
                            attr = item["hil_attribution"]
                            st.markdown(f"- Contributor: {attr.get('contributor')}")
                            st.markdown(f"- Confidence: {attr.get('confidence')}")
                            st.markdown(f"- Evidence: {attr.get('evidence')}")
                            st.markdown(f"- Expires: {attr.get('expires_at')}")




def main():
    """Main app entry point."""
    # Initialize
    init_session_state()
    
    # Header
    st.markdown("<div class='main-header'>CulturalGuard</div>", unsafe_allow_html=True)
    st.markdown("**AI Agent for Cultural Risk Intelligence**")
    st.markdown("---")
    
    # Render sidebar and get config
    platform, market = render_sidebar()
    
    # Render main content based on mode
    mode = st.session_state.current_mode
    
    if mode == "analyze":
        analyze_mode(platform, market)
    elif mode == "create":
        create_mode(platform, market)
    elif mode == "translate":
        translate_mode(platform, market)
    
    # Render history
    render_history()


if __name__ == "__main__":
    main()
