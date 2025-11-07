"""
Slack integration module for Liberty Flow trading system.
Provides asynchronous messaging capabilities to send trading updates to Slack channels.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, Union
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.webhook.async_client import AsyncWebhookClient
from slack_sdk.errors import SlackApiError

from app.config import settings, get_logger

logger = get_logger(__name__)

class SlackNotifier:
    """
    Handles asynchronous Slack notifications for the Liberty Flow trading system.
    Supports both Slack API (bot token) and webhook methods.
    """
    def __init__(self):
        self._client = AsyncWebClient(token=settings.slack.SLACK_BOT_TOKEN) if settings.slack.SLACK_BOT_TOKEN else None

        # Initialize multiple webhooks dictionary
        self._webhooks = {}
        if settings.slack.SLACK_NIFTY_STATUS_WEBHOOK:
            self._webhooks['default'] = AsyncWebhookClient(settings.slack.SLACK_NIFTY_STATUS_WEBHOOK)
        if settings.slack.SLACK_BANKNIFTY_STATUS_WEBHOOK:
            self._webhooks['banknifty'] = AsyncWebhookClient(settings.slack.SLACK_BANKNIFTY_STATUS_WEBHOOK)

        # Keep backward compatibility - existing code uses self._webhook
        self._webhook = self._webhooks.get('default')

        if not self._client and not self._webhooks:
            logger.warning("No Slack credentials configured. Slack notifications will be disabled.")
            
    async def send_message(self,
                          message: str,
                          channel: Optional[str] = None,
                          blocks: Optional[list] = None,
                          attachments: Optional[list] = None,
                          webhook_name: Optional[str] = None) -> bool:
        """
        Send a message to Slack asynchronously.

        Args:
            message: The text message to send
            channel: The Slack channel to send to (only used with bot token method)
            blocks: Optional formatted message blocks
            attachments: Optional message attachments
            webhook_name: Optional webhook name ('default', 'banknifty'). Defaults to 'default' if not specified.

        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        try:
            # Select the appropriate webhook
            webhook_to_use = None
            if webhook_name:
                webhook_to_use = self._webhooks.get(webhook_name)
                if not webhook_to_use:
                    logger.error(f"Webhook '{webhook_name}' not found. Available webhooks: {list(self._webhooks.keys())}")
                    return False
            else:
                # Use default webhook for backward compatibility
                webhook_to_use = self._webhook

            # Try webhook first if available (doesn't require channel)
            if webhook_to_use:
                return await self._send_webhook(webhook_to_use, message, blocks, attachments)

            # Fall back to API client if webhook not available
            elif self._client and channel:
                return await self._send_api(channel, message, blocks, attachments)

            # Log and return if neither method can be used
            elif self._client and not channel:
                logger.error("Channel is required when sending messages via Slack API")
                return False
            else:
                logger.debug(f"Slack notification not sent (disabled): {message}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")
            return False
    
    async def _send_webhook(self,
                           webhook_client: AsyncWebhookClient,
                           message: str,
                           blocks: Optional[list] = None,
                           attachments: Optional[list] = None) -> bool:
        """Send message via webhook"""
        try:
            response = await webhook_client.send(
                text=message,
                blocks=blocks,
                attachments=attachments
            )
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Webhook error: {response.status_code}, {response.body}")
                return False
        except Exception as e:
            logger.error(f"Webhook send error: {str(e)}")
            return False
    
    async def _send_api(self, 
                       channel: str,
                       message: str, 
                       blocks: Optional[list] = None,
                       attachments: Optional[list] = None) -> bool:
        """Send message via Slack API"""
        try:
            response = await self._client.chat_postMessage(
                channel=channel,
                text=message,
                blocks=blocks,
                attachments=attachments
            )
            return True
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return False
            
    async def send_status_update(self, status: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a formatted status update for the trading system
        
        Args:
            status: The current system status
            details: Optional dictionary with additional details
            
        Returns:
            bool: Success status
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Status Update:* `{status}`"
                }
            }
        ]
        
        if details:
            fields = []
            for key, value in details.items():
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:*\n{value}"
                })
                
            if fields:
                blocks.append({
                    "type": "section",
                    "fields": fields[:10]  # Max 10 fields per section
                })
        
        return await self.send_message(
            message=f"Status Update: {status}",
            blocks=blocks
        )
    
    async def send_breakout_alert(self, 
                                 direction: str, 
                                 price: float, 
                                 option_details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a breakout alert notification
        
        Args:
            direction: "LONG" or "SHORT"
            price: The breakout price
            option_details: Optional dictionary with option trade details
            
        Returns:
            bool: Success status
        """
        color = "#36a64f" if direction == "LONG" else "#ff2b2b"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 {direction} BREAKOUT DETECTED 🚨",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Breakout Price:* `{price}`"
                }
            }
        ]
        
        attachments = [{
            "color": color,
            "blocks": []
        }]
        
        if option_details:
            fields = []
            for key, value in option_details.items():
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:*\n{value}"
                })
                
            if fields:
                attachments[0]["blocks"].append({
                    "type": "section",
                    "fields": fields[:10]  # Max 10 fields per section
                })
        
        return await self.send_message(
            message=f"{direction} BREAKOUT at {price}",
            blocks=blocks,
            attachments=attachments
        )

# Create a global instance to be imported elsewhere
slack = SlackNotifier()

async def test_slack():
    """Test function to verify Slack integration is working"""
    success = await slack.send_message("Test message from Liberty Flow")
    if success:
        logger.info("Slack test message sent successfully")
    else:
        logger.error("Failed to send Slack test message")
    return success