"""
Slack client for Liberty Flow trading system using slack_sdk.
Handles communication with Slack API to send messages and alerts.
"""

import os
import logging
from typing import Dict, Any, Optional, List, Union
from dotenv import load_dotenv

from slack_sdk import WebClient
from slack_sdk.webhook import WebhookClient
from slack_sdk.errors import SlackApiError

# Setup logging
logger = logging.getLogger(__name__)

class SlackClient:
    """Client for sending messages and alerts to Slack using slack_sdk."""
    
    def __init__(
        self, 
        webhook_url: Optional[str] = None,
        bot_token: Optional[str] = None,
        default_channel: Optional[str] = None
    ):
        """
        Initialize Slack client.
        
        Args:
            webhook_url: Slack webhook URL. If None, will attempt to load from .env file.
            bot_token: Slack Bot Token. If None, will attempt to load from .env file.
            default_channel: Default channel to send messages to (for WebClient).
        """
        # Load environment variables if credentials not provided
        if webhook_url is None or bot_token is None:
            load_dotenv()
            
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN")
        self.default_channel = default_channel or os.getenv("SLACK_DEFAULT_CHANNEL")
        
        # Initialize clients
        self.webhook_client = None
        self.web_client = None
        
        if self.webhook_url:
            self.webhook_client = WebhookClient(self.webhook_url)
            logger.info("Initialized Slack WebhookClient")
        
        if self.bot_token:
            self.web_client = WebClient(token=self.bot_token)
            logger.info("Initialized Slack WebClient")
            
        if not self.webhook_client and not self.web_client:
            logger.warning("No Slack credentials provided. Messages will not be sent.")
    
    def send_message(self, 
                    message: str, 
                    channel: Optional[str] = None,
                    blocks: Optional[List[Dict[str, Any]]] = None,
                    thread_ts: Optional[str] = None) -> bool:
        """
        Send a text message to Slack.
        
        Args:
            message: Message text to send
            channel: Channel to send to (required for WebClient, optional for WebhookClient)
            blocks: Optional block formatting for the message
            thread_ts: Optional thread timestamp to reply in a thread
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        # Try to send with WebClient if available
        if self.web_client:
            try:
                response = self.web_client.chat_postMessage(
                    channel=channel or self.default_channel,
                    text=message,
                    blocks=blocks,
                    thread_ts=thread_ts
                )
                logger.debug(f"Sent message via WebClient: {message[:50]}...")
                return True
            except SlackApiError as e:
                logger.error(f"Error sending message via WebClient: {e.response['error']}")
                # Fall back to webhook if WebClient fails
        
        # Try to send with WebhookClient if available
        if self.webhook_client:
            try:
                response = self.webhook_client.send(
                    text=message,
                    blocks=blocks
                )
                if response.status_code == 200:
                    logger.debug(f"Sent message via WebhookClient: {message[:50]}...")
                    return True
                else:
                    logger.error(f"Error sending message via WebhookClient. Status: {response.status_code}")
            except Exception as e:
                logger.error(f"Error sending message via WebhookClient: {str(e)}")
        
        return False
    
    def send_alert(self, 
                  title: str, 
                  message: str, 
                  level: str = "info", 
                  fields: Optional[List[Dict[str, str]]] = None,
                  channel: Optional[str] = None,
                  thread_ts: Optional[str] = None) -> bool:
        """
        Send a formatted alert message to Slack.
        
        Args:
            title: Alert title
            message: Alert message text
            level: Alert level (info, warning, error, success)
            fields: Optional list of field dictionaries with 'title' and 'value' keys
            channel: Optional channel override
            thread_ts: Optional thread timestamp to reply in a thread
            
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        # Set emoji based on level
        emoji_map = {
            "info": ":information_source:",
            "warning": ":warning:",
            "error": ":x:",
            "success": ":white_check_mark:",
        }
        emoji = emoji_map.get(level.lower(), ":information_source:")
        
        # Create blocks for the message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{title}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} {message}"
                }
            }
        ]
        
        # Add fields if provided
        if fields and len(fields) > 0:
            field_blocks = []
            
            # Process fields in pairs for two-column layout
            for i in range(0, len(fields), 2):
                field_pair = []
                
                # Add first field
                field_pair.append({
                    "type": "mrkdwn",
                    "text": f"*{fields[i]['title']}*\n{fields[i]['value']}"
                })
                
                # Add second field if it exists
                if i + 1 < len(fields):
                    field_pair.append({
                        "type": "mrkdwn",
                        "text": f"*{fields[i+1]['title']}*\n{fields[i+1]['value']}"
                    })
                
                # Add section with this pair of fields
                blocks.append({
                    "type": "section",
                    "fields": field_pair
                })
            
        # Add divider
        blocks.append({"type": "divider"})
        
        # Add fallback text
        text = f"{title}: {message}"
        
        return self.send_message(
            message=text,
            blocks=blocks,
            channel=channel,
            thread_ts=thread_ts
        )
    
    def send_strategy_alert(self, 
                           status: str,
                           details: Dict[str, Any],
                           channel: Optional[str] = None,
                           thread_ts: Optional[str] = None) -> bool:
        """
        Send a Liberty Flow strategy status alert.
        
        Args:
            status: Strategy status (one of the defined strategy statuses)
            details: Dictionary containing strategy details
            channel: Optional channel override
            thread_ts: Optional thread timestamp to reply in a thread
            
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        # Map status to alert level
        status_level_map = {
            "Awaiting Trigger": "info",
            "Awaiting Swing Formation": "info",
            "Awaiting Breakouts of any 1 of the swing formed": "warning",
            "Trailing": "success",
            "Not Triggered -> Exit": "info",
            "Swing formed but not broken out -> Exit": "warning",
            "Exited": "success"
        }
        
        level = status_level_map.get(status, "info")
        
        # Create fields for the alert
        fields = []
        for key, value in details.items():
            if key != "status":  # Status is already in the title
                fields.append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value)
                })
        
        return self.send_alert(
            title=f"Liberty Flow: {status}",
            message=f"Strategy status update: {status}",
            level=level,
            fields=fields,
            channel=channel,
            thread_ts=thread_ts
        )
        
    def upload_file(self,
                   file_path: str,
                   title: Optional[str] = None,
                   initial_comment: Optional[str] = None,
                   channel: Optional[str] = None) -> bool:
        """
        Upload a file to Slack.
        Requires WebClient (Bot Token).
        
        Args:
            file_path: Path to the file to upload
            title: Optional title for the file
            initial_comment: Optional comment to add with the file
            channel: Channel to upload to (if None, uses default)
            
        Returns:
            bool: True if file was uploaded successfully, False otherwise
        """
        if not self.web_client:
            logger.error("Cannot upload file: WebClient not initialized (Bot Token required)")
            return False
            
        try:
            response = self.web_client.files_upload_v2(
                channel=channel or self.default_channel,
                file=file_path,
                title=title,
                initial_comment=initial_comment
            )
            logger.debug(f"Uploaded file {file_path} to Slack")
            return True
        except SlackApiError as e:
            logger.error(f"Error uploading file: {e.response['error']}")
            return False