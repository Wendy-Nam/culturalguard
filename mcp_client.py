"""
CulturalGuard — MCP Integration Module
Handles communication with MCP servers (Resend, Discord, Slack, Filesystem)
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Try to import MCP, handle if not available
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class MCPClient:
    """MCP Client for CulturalGuard - handles email, Discord, Slack, and filesystem."""
    
    def __init__(self):
        self.resend_available = False
        self.discord_available = False
        self.slack_available = False
        self._check_availability()
    
    def _check_availability(self):
        """Check which MCP servers are configured."""
        if os.getenv("RESEND_API_KEY"):
            self.resend_available = True
        if os.getenv("DISCORD_BOT_TOKEN") and os.getenv("DISCORD_CHANNEL_ID"):
            self.discord_available = True
        if os.getenv("SLACK_WEBHOOK_URL"):
            self.slack_available = True
    
    # =========================================================================
    # Email (Resend)
    # =========================================================================
    
    async def send_email(self, to: str, subject: str, body: str) -> dict:
        """Send email via Resend."""
        if not self.resend_available:
            return await self._send_email_direct(to, subject, body)
        
        try:
            result = await self._call_mcp_server(
                "resend-email", "send_email", {"to": to, "subject": subject, "body": body}
            )
            if result.get("status") == "success":
                return {"status": "sent_via_mcp", "provider": "resend", "to": to, "subject": subject}
        except Exception as e:
            print(f"MCP email failed: {e}")
        
        return await self._send_email_direct(to, subject, body)
    
    async def _send_email_direct(self, to: str, subject: str, body: str) -> dict:
        """Send email directly via Resend API."""
        import requests
        
        api_key = os.getenv("RESEND_API_KEY")
        if not api_key:
            return {"status": "failed", "error": "RESEND_API_KEY not configured"}
        
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                json={
                    "from": os.getenv("EMAIL_FROM", "CulturalGuard <onboarding@resend.dev>"),
                    "to": to,
                    "subject": subject,
                    "html": body
                },
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return {"status": "sent", "provider": "resend", "message_id": data.get("id"), "to": to}
            else:
                return {"status": "failed", "error": response.text, "code": response.status_code}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def send_email_sync(self, to: str, subject: str, body: str) -> dict:
        """Synchronous wrapper for send_email."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.send_email(to, subject, body))
                    return future.result()
            else:
                return loop.run_until_complete(self.send_email(to, subject, body))
        except RuntimeError:
            return asyncio.run(self.send_email(to, subject, body))
    
    # =========================================================================
    # Discord
    # =========================================================================
    
    async def notify_discord(self, content: str, urgency: str = "normal", metadata: dict = None) -> dict:
        """Notify Discord channel."""
        if not self.discord_available:
            return {"status": "simulated", "error": "Discord not configured", "content": content, "urgency": urgency}
        
        return await self._notify_discord_direct(content, urgency, metadata)
    
    async def _notify_discord_direct(self, content: str, urgency: str, metadata: dict = None) -> dict:
        """Send message via Discord Bot API."""
        import requests
        
        bot_token = os.getenv("DISCORD_BOT_TOKEN")
        channel_id = os.getenv("DISCORD_CHANNEL_ID")
        
        if not bot_token or not channel_id:
            return {"status": "failed", "error": "Discord credentials not configured"}
        
        embed = {
            "title": f"CulturalGuard Alert: {urgency.upper()}",
            "description": content[:2000],
            "color": self._urgency_to_color(urgency),
            "fields": []
        }
        
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    embed["fields"].append({"name": key, "value": str(value)[:1000], "inline": True})
        
        from datetime import datetime
        embed["footer"] = {"text": "CulturalGuard"}
        embed["timestamp"] = datetime.now().isoformat()
        
        try:
            response = requests.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                json={"content": f"Human Review Required" if urgency == "critical" else "CulturalGuard Alert", "embeds": [embed]},
                headers={"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return {"status": "sent", "provider": "discord", "message_id": data.get("id")}
            else:
                return {"status": "failed", "error": response.text, "code": response.status_code}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _urgency_to_color(self, urgency: str) -> int:
        colors = {"low": 0x3498db, "normal": 0xf39c12, "high": 0xe74c3c, "critical": 0x8e44ad}
        return colors.get(urgency, 0xf39c12)
    
    def notify_discord_sync(self, content: str, urgency: str = "normal", metadata: dict = None) -> dict:
        """Synchronous wrapper for notify_discord."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.notify_discord(content, urgency, metadata))
                    return future.result()
            else:
                return loop.run_until_complete(self.notify_discord(content, urgency, metadata))
        except RuntimeError:
            return asyncio.run(self.notify_discord(content, urgency, metadata))
    
    # =========================================================================
    # Slack
    # =========================================================================
    
    async def notify_slack(self, content: str, urgency: str = "normal", metadata: dict = None) -> dict:
        """Notify Slack channel via webhook."""
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not webhook_url:
            return {"status": "failed", "error": "SLACK_WEBHOOK_URL not configured"}
        
        # Get metadata values
        meta = metadata or {}
        risk_level = meta.get("risk_level", "UNKNOWN")
        risk_score = meta.get("risk_score", 0.0)
        platform = meta.get("platform", "unknown")
        market = meta.get("market", "unknown")
        risk_factors = meta.get("risk_factors", [])
        
        urgency_emoji = {
            "low": ":white_check_mark:",
            "normal": ":warning:",
            "high": ":rotating_light:",
            "critical": ":fire:"
        }
        
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{urgency_emoji.get(urgency, ':warning:')} CulturalGuard Alert: {risk_level}"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Content:*\n{content[:500]}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Risk Score:*\n{risk_score:.2f}"},
                    {"type": "mrkdwn", "text": f"*Platform:*\n{platform}"},
                    {"type": "mrkdwn", "text": f"*Market:*\n{market}"}
                ]
            }
        ]
        
        if risk_factors:
            factor_text = "\n".join([f"- [{rf.get('category', '?')}] {rf.get('phrase', '')}" for rf in risk_factors[:5]])
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Risk Factors:*\n{factor_text}"}})
        
        try:
            import requests
            response = requests.post(webhook_url, json={"blocks": blocks}, headers={"Content-Type": "application/json"})
            
            if response.status_code == 200:
                return {"status": "sent", "provider": "slack"}
            else:
                return {"status": "failed", "error": response.text}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def notify_slack_sync(self, content: str, urgency: str = "normal", metadata: dict = None) -> dict:
        """Synchronous wrapper for notify_slack."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.notify_slack(content, urgency, metadata))
                    return future.result()
            else:
                return loop.run_until_complete(self.notify_slack(content, urgency, metadata))
        except RuntimeError:
            return asyncio.run(self.notify_slack(content, urgency, metadata))
    
    # =========================================================================
    # Human-in-the-loop escalation
    # =========================================================================
    
    async def escalate_to_human(
        self,
        content: str,
        risk_score: float,
        risk_level: str,
        risk_factors: list,
        diagnosis: list,
        platform: str,
        market: str
    ) -> dict:
        """Escalate high-risk content to human reviewers."""
        results = {
            "escalated": True,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "notifications": []
        }
        
        urgency = "low"
        if risk_score >= 0.9:
            urgency = "critical"
        elif risk_score >= 0.8:
            urgency = "high"
        elif risk_score >= 0.7:
            urgency = "normal"
        
        metadata = {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "platform": platform,
            "market": market,
            "factor_count": len(risk_factors)
        }
        
        # Send to Discord
        if self.discord_available:
            discord_content = f"**Cultural Risk Alert - {risk_level}**\n\nContent: {content[:500]}\n\nRisk Score: {risk_score:.2f}\nPlatform: {platform}\nMarket: {market}"
            discord_result = await self.notify_discord(content=discord_content, urgency=urgency, metadata=metadata)
            results["notifications"].append({"type": "discord", "status": discord_result.get("status")})
        
        # Send email
        email_to = os.getenv("EMAIL_TO", "")
        if email_to and self.resend_available:
            email_body = f"<h2>CulturalGuard Alert</h2><p><strong>Risk Level:</strong> {risk_level}</p><p><strong>Risk Score:</strong> {risk_score:.2f}</p><p><strong>Content:</strong> {content}</p>"
            email_result = await self.send_email(to=email_to, subject=f"CulturalGuard Alert: {risk_level}", body=email_body)
            results["notifications"].append({"type": "email", "status": email_result.get("status")})
        
        # Send to Slack
        if self.slack_available:
            slack_result = await self.notify_slack(content=content, urgency=urgency, metadata={**metadata, "risk_factors": risk_factors})
            results["notifications"].append({"type": "slack", "status": slack_result.get("status")})
        
        return results
    
    def escalate_to_human_sync(
        self,
        content: str,
        risk_score: float,
        risk_level: str,
        risk_factors: list,
        diagnosis: list,
        platform: str,
        market: str
    ) -> dict:
        """Synchronous wrapper for escalate_to_human."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.escalate_to_human(content, risk_score, risk_level, risk_factors, diagnosis, platform, market)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.escalate_to_human(content, risk_score, risk_level, risk_factors, diagnosis, platform, market)
                )
        except RuntimeError:
            return asyncio.run(
                self.escalate_to_human(content, risk_score, risk_level, risk_factors, diagnosis, platform, market)
            )


# =========================================================================
# Helpers
# =========================================================================

def send_escalation_email(subject: str, body: str, recipients: str) -> dict:
    """Simple sync wrapper for email sending."""
    client = MCPClient()
    return client.send_email_sync(to=recipients, subject=subject, body=body)


def notify_discord_human_review(content: str, urgency: str = "normal") -> dict:
    """Simple sync wrapper for Discord notifications."""
    client = MCPClient()
    return client.notify_discord_sync(content=content, urgency=urgency)


if __name__ == "__main__":
    print("=" * 60)
    print("  CulturalGuard MCP Client - Test")
    print("=" * 60)
    
    client = MCPClient()
    
    print(f"\nMCP Available: {MCP_AVAILABLE}")
    print(f"Resend Available: {client.resend_available}")
    print(f"Discord Available: {client.discord_available}")
    print(f"Slack Available: {client.slack_available}")
    
    print("\n--- Testing Email ---")
    result = client.send_email_sync(to="test@example.com", subject="Test", body="<p>Test</p>")
    print(f"Email: {result.get('status')}")
    
    print("\n--- Testing Discord ---")
    result = client.notify_discord_sync(content="Test", urgency="normal")
    print(f"Discord: {result.get('status')}")
    
    print("\n--- Testing Slack ---")
    result = client.notify_slack_sync(content="Test", urgency="normal", metadata={"risk_level": "REVISE_REQUIRED", "risk_score": 0.6, "platform": "linkedin", "market": "kr"})
    print(f"Slack: {result.get('status')}")
    
    print("\n" + "=" * 60)
