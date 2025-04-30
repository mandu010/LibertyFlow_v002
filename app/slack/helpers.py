"""
Helper functions for common Slack notification scenarios in the Liberty Flow system.
"""
import asyncio
from typing import Dict, Any, Optional, Union, List
from datetime import datetime

from app.slack.client import slack
from app.config import get_logger

logger = get_logger(__name__)

# Status constants based on your system states
STATUSES = {
    "AWAITING_TRIGGER": "Awaiting Trigger",
    "AWAITING_SWING": "Awaiting Swing Formation",
    "AWAITING_BREAKOUT": "Awaiting Breakouts",
    "TRAILING": "Trailing",
    "NOT_TRIGGERED": "Not Triggered -> Exit",
    "NO_BREAKOUT": "Swing formed but not broken out -> Exit",
    "EXITED": "Exited"
}

async def send_status_change(old_status: str, new_status: str, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Send status change notification asynchronously
    
    Args:
        old_status: Previous system status
        new_status: New system status
        details: Optional additional information
    """
    try:
        status_info = {
            "Previous Status": STATUSES.get(old_status, old_status),
            "Current Status": STATUSES.get(new_status, new_status),
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if details:
            status_info.update(details)
            
        # Run in background task
        asyncio.create_task(slack.send_status_update(
            status=STATUSES.get(new_status, new_status),
            details=status_info
        ))
    except Exception as e:
        logger.error(f"Error sending status change notification: {str(e)}")

async def send_breakout_notification(
    direction: str, 
    price: float,
    strike_price: Optional[float] = None, 
    option_type: Optional[str] = None,
    delta: Optional[float] = None,
    order_price: Optional[float] = None,
    other_details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Send breakout notification asynchronously
    
    Args:
        direction: "LONG" or "SHORT"
        price: The breakout price
        strike_price: Option strike price
        option_type: "CE" or "PE"
        delta: Option delta value
        order_price: Order price
        other_details: Any other trade details
    """
    try:
        option_details = {
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Direction": direction,
            "Breakout Price": price
        }
        
        # Add option details if available
        if strike_price:
            option_details["Strike Price"] = strike_price
        if option_type:
            option_details["Option Type"] = option_type
        if delta:
            option_details["Delta"] = f"{delta:.2f}"
        if order_price:
            option_details["Order Price"] = order_price
            
        # Add any additional details
        if other_details:
            option_details.update(other_details)
            
        # Run in background task
        asyncio.create_task(slack.send_breakout_alert(
            direction=direction,
            price=price,
            option_details=option_details
        ))
    except Exception as e:
        logger.error(f"Error sending breakout notification: {str(e)}")

async def send_error_notification(error_message: str, error_context: Optional[Dict[str, Any]] = None) -> None:
    """
    Send error notification asynchronously
    
    Args:
        error_message: The error message
        error_context: Optional context information
    """
    try:
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚠️ System Error",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:* ```{error_message}```"
                }
            }
        ]
        
        if error_context:
            context_text = "\n".join([f"*{k}:* {v}" for k, v in error_context.items()])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Context:*\n{context_text}"
                }
            })
        
        # Run in background task
        asyncio.create_task(slack.send_message(
            message=f"Error: {error_message}",
            blocks=blocks
        ))
    except Exception as e:
        logger.error(f"Error sending error notification: {str(e)}")