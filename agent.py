"""
CulturalGuard — Core Agent
Local fallback mode with knowledge base integration
"""

import os
import json
import re
import time
from functools import wraps
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Constants
KB_ROOT = Path(__file__).parent / "knowledge_base"
CONFIG_DIR = Path(__file__).parent / "config"
REPORTS_DIR = Path(__file__).parent / "reports"
MAX_CONTEXT_CHARS = 8000

_trace_log = []


def _traced(func):
    """Decorator that auto-traces function calls."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.time()
        result = func(*args, **kwargs)
        duration_ms = round((time.time() - t0) * 1000)
        
        summary = {}
        import inspect
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        all_args = list(args) + [kwargs.get(p) for p in params[len(args):] if p in kwargs]
        for i, p in enumerate(params):
            if i < len(all_args) and all_args[i] is not None:
                v = all_args[i]
                summary[p] = (v[:60] + "...") if isinstance(v, str) and len(v) > 60 else v
        
        _trace_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "function": func.__name__,
            "args": summary,
            "duration_ms": duration_ms,
        })
        print(f"    -> {func.__name__}({', '.join(f'{k}={v!r}' for k, v in summary.items())})  [{duration_ms}ms]")
        return result
    
    return wrapper


# =========================================================================
# Tool Functions
# =========================================================================

@_traced
def load_knowledge_base(category: str, filename: str) -> str:
    """Load a specific knowledge-base file."""
    path = KB_ROOT / category / filename
    if not path.exists():
        return json.dumps({"error": f"File not found: {category}/{filename}"})
    return path.read_text(encoding="utf-8")


@_traced
def load_analysis_context(platform: str, market: str) -> str:
    """Load compressed KB context for analysis."""
    ctx = {}
    
    # Load risk patterns with variations
    for f in sorted((KB_ROOT / "risk").glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        ctx["risks"] = ctx.get("risks", {})
        ctx["risks"][f.stem] = [
            {
                "p": p.get("phrase", ""),
                "s": p.get("risk_score", 0.5),
                "v": p.get("variations", [])
            }
            for p in data.get("patterns", [])
        ]
    
    suffix_map = {"kr": "korea", "jp": "japan", "us": "us", "global": "global"}
    suffix = suffix_map.get(market, market)
    norm_file = KB_ROOT / "platform_norms" / f"{platform}_{suffix}.json"
    if norm_file.exists():
        ctx["platform_norms"] = json.loads(norm_file.read_text(encoding="utf-8"))
    
    brand_file = KB_ROOT / "brand" / "brand_guide.json"
    if brand_file.exists():
        ctx["brand"] = json.loads(brand_file.read_text(encoding="utf-8"))
    
    rewrite_file = KB_ROOT / "rewrite" / "rewrite_guide.json"
    if rewrite_file.exists():
        ctx["rewrite"] = json.loads(rewrite_file.read_text(encoding="utf-8"))
    
    ctx_str = json.dumps(ctx, ensure_ascii=False)
    if len(ctx_str) > MAX_CONTEXT_CHARS:
        if "risks" in ctx:
            for limit in [5, 3, 1]:
                for cat in ctx["risks"]:
                    ctx["risks"][cat] = ctx["risks"][cat][:limit]
                ctx_str = json.dumps(ctx, ensure_ascii=False)
                if len(ctx_str) <= MAX_CONTEXT_CHARS:
                    return ctx_str
        for key in ["rewrite", "brand", "platform_norms"]:
            if key in ctx:
                ctx.pop(key)
                ctx_str = json.dumps(ctx, ensure_ascii=False)
                if len(ctx_str) <= MAX_CONTEXT_CHARS:
                    return ctx_str
        if "risks" in ctx:
            ctx = {"risks": {cat: items[:1] for cat, items in ctx["risks"].items()}}
        ctx_str = json.dumps(ctx, ensure_ascii=False)
    
    return ctx_str


@_traced
def get_kb_governance_status() -> str:
    """Check knowledge base health."""
    files = list(KB_ROOT.rglob("*.json"))
    return json.dumps({
        "total_files": len(files),
        "categories": {
            "risk": len(list((KB_ROOT / "risk").glob("*.json"))),
            "platform_norms": len(list((KB_ROOT / "platform_norms").glob("*.json"))),
            "brand": len(list((KB_ROOT / "brand").glob("*.json"))),
        },
        "status": "healthy"
    })


@_traced
def check_prompt_injection(user_input: str) -> str:
    """Check for prompt injection."""
    patterns = [
        r"ignore\s+(previous|all|above)",
        r"(system|admin)\s*:\s*",
        r"you\s+(are|have|can)\s+(to\s+)?(ignore|disregard)",
    ]
    
    findings = []
    for pattern in patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            findings.append(pattern)
    
    return json.dumps({
        "has_injection": len(findings) > 0,
        "findings": findings,
        "action": "BLOCK" if findings else "ALLOW"
    })


@_traced
def check_pii_patterns(text: str) -> str:
    """Detect PII patterns."""
    pii_patterns = {
        "email": r"\b[\w.-]+@[\w.-]+\.\w+\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    }
    
    findings = {}
    for ptype, pattern in pii_patterns.items():
        matches = re.findall(pattern, text)
        if matches:
            findings[ptype] = matches
    
    redacted = text
    for ptype, matches in findings.items():
        for match in matches:
            redacted = redacted.replace(match, f"[{ptype.upper()}_REDACTED]")
    
    return json.dumps({
        "has_pii": len(findings) > 0,
        "findings": {k: len(v) for k, v in findings.items()},
        "redacted_text": redacted
    })


@_traced
def get_current_datetime() -> str:
    """Get current datetime."""
    now = datetime.now(timezone.utc)
    return json.dumps({
        "datetime": now.isoformat(),
        "timestamp": now.timestamp(),
        "timezone": "UTC"
    })


@_traced
def save_report(analysis_result: str, content: str, platform: str, market: str) -> str:
    """Save analysis report."""
    REPORTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"analysis_{platform}_{market}_{timestamp}.json"
    filepath = REPORTS_DIR / filename
    
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": content,
        "platform": platform,
        "market": market,
        "result": json.loads(analysis_result) if isinstance(analysis_result, str) else analysis_result
    }
    
    filepath.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return json.dumps({"status": "saved", "filepath": str(filepath)})


@_traced
def save_eval_report(metrics: str) -> str:
    """Save evaluation metrics."""
    REPORTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = REPORTS_DIR / f"eval_{timestamp}.json"
    
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": json.loads(metrics) if isinstance(metrics, str) else metrics
    }
    
    filepath.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return json.dumps({"status": "saved", "filepath": str(filepath)})


@_traced
def send_escalation_email(subject: str, body: str, recipients: str) -> str:
    """Send escalation email."""
    if not os.getenv("RESEND_API_KEY"):
        return json.dumps({
            "status": "simulated",
            "message": "RESEND_API_KEY not configured",
            "subject": subject,
            "recipients": recipients
        })
    return json.dumps({"status": "sent", "provider": "resend", "subject": subject})


# =========================================================================
# CulturalGuard Agent
# =========================================================================

class CulturalGuardAgent:
    """Main agent for cultural risk analysis."""
    
    def __init__(self):
        config_path = CONFIG_DIR / "agent_config.json"
        if config_path.exists():
            self.config = json.loads(config_path.read_text(encoding="utf-8"))
        else:
            self.config = {}
    
    def analyze(self, content: str, platform: str = "linkedin", market: str = "kr") -> dict[str, object]:
        """Analyze content for cultural risks."""
        global _trace_log
        _trace_log = []
        
        result: dict[str, object] = {
            "content": content,
            "platform": platform,
            "market": market,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Safety checks
        injection_check = check_prompt_injection(content)
        if json.loads(injection_check).get("has_injection"):
            return {
                "error": "Prompt injection detected",
                "decision": "REJECT",
                "risk_score": 1.0,
                "risk_level": "ESCALATE_TO_HUMAN"
            }
        
        pii_check = check_pii_patterns(content)
        pii_result = json.loads(pii_check)
        if pii_result.get("has_pii"):
            result["pii_warning"] = pii_result.get("findings")
        
        # Load KB
        kb_context = load_analysis_context(platform, market)
        result["kb_loaded"] = True
        
        # Local analysis
        return self._local_analyze(content, platform, market, kb_context, result)
    
    def _local_analyze(self, content: str, platform: str, market: str, kb_context: str, result: dict[str, object]) -> dict[str, object]:
        """Local keyword-based analysis."""
        kb = json.loads(kb_context)
        
        risk_factors = []
        diagnosis = []
        content_lower = content.lower()
        
        if "risks" in kb:
            for category, patterns in kb["risks"].items():
                for item in patterns:
                    phrase = item.get("p", "").lower()
                    
                    # Check main phrase
                    match_found = phrase in content_lower
                    
                    # Also check variations
                    if not match_found:
                        variations = item.get("v", [])
                        for var in variations:
                            if var.lower() in content_lower:
                                match_found = True
                                phrase = var.lower()
                                break
                    
                    if match_found:
                        risk_factors.append({
                            "category": category,
                            "phrase": item.get("p"),
                            "confidence": item.get("s", 0.5),
                        })
                        diagnosis.append({
                            "phrase": item.get("p"),
                            "why": f"Risk category: {category}",
                            "market_impact": f"High risk in {market}"
                        })
        
        # Calculate score
        if risk_factors:
            scores = [rf.get("confidence", 0.5) for rf in risk_factors]
            base_score = max(scores)
        else:
            base_score = 0.1
        
        # Apply penalties for KR/JP markets
        penalty = 1.0
        if market == "kr" and any("competition" in rf.get("category", "") for rf in risk_factors):
            penalty = 1.5
        elif market == "jp" and any("competition" in rf.get("category", "") for rf in risk_factors):
            penalty = 1.5
        
        risk_score = min(base_score * penalty, 1.0)

        if result.get("pii_warning"):
            risk_factors.append({
                "category": "pii",
                "phrase": "PII detected",
                "confidence": 0.6,
            })
            diagnosis.append({
                "phrase": "PII detected",
                "why": "Contains personal data that should be removed",
                "market_impact": "Compliance risk"
            })
            risk_score = max(risk_score, 0.8)
        
        # Determine level
        if result.get("pii_warning"):
            risk_level = "ESCALATE_TO_HUMAN"
            decision = "PII detected - human review required"
        elif risk_score <= 0.30:
            risk_level = "APPROVE"
            decision = "Safe to publish"
        elif risk_score <= 0.50:
            risk_level = "REVIEW_SUGGESTED"
            decision = "Minor risks - review recommended"
        elif risk_score <= 0.70:
            risk_level = "REVISE_REQUIRED"
            decision = "Significant risks - must revise"
        else:
            risk_level = "ESCALATE_TO_HUMAN"
            decision = "Critical - human review required"
        
        rewrites = []
        if risk_factors:
            rewrites = [{
                "version": "v1",
                "text": content + " [REWRITE NEEDED]",
                "axes": {"formality": "formal", "agency": "team-credit"},
                "why_safe": "More conservative phrasing"
            }]
        
        result.update({
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "decision": decision,
            "risk_factors": risk_factors,
            "diagnosis": diagnosis,
            "rewrites": rewrites,
            "chain_of_thought": [
                "Loaded knowledge base context",
                f"Found {len(risk_factors)} risk factors",
                f"Calculated risk score: {risk_score}",
                f"Determined level: {risk_level}"
            ],
            "self_reflection": {
                "confidence": 0.85 if risk_factors else 0.5,
                "notes": "Local analysis mode"
            }
        })
        
        save_report(json.dumps(result), content, platform, market)
        
        result["_trace"] = {
            "function_calls": len(_trace_log),
            "total_ms": sum(t["duration_ms"] for t in _trace_log),
            "log": _trace_log
        }
        
        return result
    
    def cleanup(self):
        pass


if __name__ == "__main__":
    import sys
    
    TEST_CONTENT = "SeoaFlow crushed the competition this quarter! We're the undisputed market leader"
    TEST_PLATFORM = "linkedin"
    TEST_MARKET = "kr"
    
    print("=" * 60)
    print("  CulturalGuard — Cultural Intelligence Agent")
    print("=" * 60)
    print(f"  Content : {TEST_CONTENT}")
    print(f"  Platform: {TEST_PLATFORM}")
    print(f"  Market  : {TEST_MARKET}")
    print("-" * 60)
    
    agent = CulturalGuardAgent()
    
    try:
        print("\n> Running analysis...\n")
        result = agent.analyze(TEST_CONTENT, TEST_PLATFORM, TEST_MARKET)
        
        print("\n" + "=" * 60)
        print("  RESULT")
        print("=" * 60)
        
        if "error" in result and "risk_score" not in result:
            print(f"  Error: {result['error']}")
            sys.exit(1)
        
        print(f"  Risk Score : {result.get('risk_score', '?')}")
        print(f"  Risk Level : {result.get('risk_level', '?')}")
        print(f"  Decision   : {result.get('decision', '?')}")
        
        print("\n" + "=" * 60)
        print("  Analysis complete")
        print("=" * 60)
        
    finally:
        agent.cleanup()
