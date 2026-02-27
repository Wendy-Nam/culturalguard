"""
CulturalGuard — CLI entry point for quick testing.
Usage: python main.py
"""

import json
import sys
from agent import CulturalGuardAgent


# ── Test content ─────────────────────────────────────────────────
TEST_CONTENT = (
    "SeoaFlow crushed the competition this quarter! "
    "We're the undisputed market leader 🔥"
)
TEST_PLATFORM = "linkedin"
TEST_MARKET = "kr"


def main():
    print("=" * 60)
    print("  CulturalGuard — Cultural Intelligence Agent")
    print("=" * 60)
    print(f"  Content : {TEST_CONTENT}")
    print(f"  Platform: {TEST_PLATFORM}")
    print(f"  Market  : {TEST_MARKET}")
    print("-" * 60)

    agent = CulturalGuardAgent()

    try:
        print("\n▶ Running analysis…\n")
        result = agent.analyze(TEST_CONTENT, TEST_PLATFORM, TEST_MARKET)

        # ── Pretty-print key fields ────────────────────────────
        print("\n" + "=" * 60)
        print("  RESULT")
        print("=" * 60)

        if "error" in result and "risk_score" not in result:
            print(f"  ❌ Error: {result['error']}")
            if "raw" in result:
                print(f"  Raw (first 300 chars): {result['raw'][:300]}")
            return 1

        print(f"  Risk Score : {result.get('risk_score', '?')}")
        print(f"  Risk Level : {result.get('risk_level', '?')}")
        print(f"  Decision   : {result.get('decision', '?')}")

        # Chain of Thought
        cot = result.get("chain_of_thought", [])
        if cot:
            print(f"\n  Chain of Thought ({len(cot)} steps):")
            for i, step in enumerate(cot, 1):
                print(f"    {i}. {step[:120]}")

        # Risk Factors
        rfs = result.get("risk_factors", [])
        if rfs:
            print(f"\n  Risk Factors ({len(rfs)}):")
            for rf in rfs:
                print(f"    • [{rf.get('category')}] \"{rf.get('phrase')}\" "
                      f"(conf={rf.get('confidence', '?')})")

        # Diagnosis
        diag = result.get("diagnosis", [])
        if diag:
            print(f"\n  Diagnosis ({len(diag)}):")
            for d in diag:
                print(f"    • \"{d.get('phrase')}\" → {d.get('why', '')[:100]}")

        # Rewrites
        rws = result.get("rewrites", [])
        if rws:
            print(f"\n  Rewrites ({len(rws)}):")
            for rw in rws:
                print(f"    v{rw.get('version', '?')}: {rw.get('text', '')[:120]}")
                axes = rw.get("axes", {})
                if axes:
                    print(f"         axes: {json.dumps(axes)}")
                ws = rw.get("why_safe", "")
                if ws:
                    print(f"         why_safe: {ws[:100]}")

        # Self-Reflection
        sr = result.get("self_reflection", {})
        if sr:
            print(f"\n  Self-Reflection: confidence={sr.get('confidence', '?')}")

        # Trace
        trace = result.get("_trace", {})
        if trace:
            print(f"\n  Trace: {trace.get('function_calls', 0)} tool calls, "
                  f"{trace.get('total_ms', 0)}ms total")
            for entry in trace.get("log", []):
                print(f"    [{entry['timestamp'][:19]}] {entry['function']} "
                      f"({entry['duration_ms']}ms)")

        print("\n" + "=" * 60)
        print("  ✓ Analysis complete")
        print("=" * 60)
        return 0

    except KeyboardInterrupt:
        print("\n  Interrupted.")
        return 130
    except Exception as exc:
        print(f"\n  ❌ Error: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        agent.cleanup()


if __name__ == "__main__":
    sys.exit(main())
