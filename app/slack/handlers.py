"""
Slack event handlers for Liberty Flow trading system.
Contains functions for handling various strategy events and sending appropriate alerts.
"""

from app.slack.client import SlackClient
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import from app config
from app.config import settings, get_logger

# Setup logger
logger = get_logger(__name__)

class SlackAlertHandler:
    """Handler for sending strategy alerts to Slack."""
    
    def __init__(self, 
                slack_client: Optional[SlackClient] = None,
                default_channel: Optional[str] = None):
        """
        Initialize Slack alert handler.
        
        Args:
            slack_client: SlackClient instance. If None, a new instance will be created.
            default_channel: Default channel to send alerts to.
        """
        self.slack_client = slack_client or SlackClient()
        self.default_channel = default_channel
        self.current_strategy_thread = None  # To keep thread context for a strategy run
        
    def start_new_strategy_thread(self, message: str = "Starting new strategy run") -> bool:
        """
        Start a new thread for the current strategy run.
        
        Args:
            message: Initial message for the thread
            
        Returns:
            bool: True if thread was created successfully, False otherwise
        """
        # Only available with WebClient (Bot Token)
        if not hasattr(self.slack_client, 'web_client') or not self.slack_client.web_client:
            logger.warning("Cannot create thread: WebClient not initialized")
            self.current_strategy_thread = None
            return False
            
        try:
            response = self.slack_client.web_client.chat_postMessage(
                channel=self.default_channel or self.slack_client.default_channel,
                text=f"🔄 *LIBERTY FLOW STRATEGY* 🔄\n{message}\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.current_strategy_thread = response["ts"]
            logger.info(f"Started new strategy thread with timestamp: {self.current_strategy_thread}")
            return True
        except Exception as e:
            logger.error(f"Error creating thread: {str(e)}")
            self.current_strategy_thread = None
            return False
    
    def handle_strategy_status_change(self, 
                                     status: str, 
                                     details: Dict[str, Any],
                                     start_new_thread: bool = False) -> bool:
        """
        Handle strategy status change event.
        
        Args:
            status: New strategy status
            details: Dictionary containing strategy details
            start_new_thread: Whether to start a new thread for this event
            
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        logger.info(f"Strategy status changed to: {status}")
        
        # Start new thread if requested and not already in a thread
        if start_new_thread and not self.current_strategy_thread:
            self.start_new_strategy_thread(f"Strategy status: {status}")
        
        return self.slack_client.send_strategy_alert(
            status=status, 
            details=details,
            channel=self.default_channel,
            thread_ts=self.current_strategy_thread
        )
        
    def handle_trigger_event(self, 
                            trigger_type: str, 
                            details: Dict[str, Any],
                            start_new_thread: bool = False) -> bool:
        """
        Handle strategy trigger event.
        
        Args:
            trigger_type: Type of trigger (e.g., "Range Breakout", "Gap Open", "Large Candle")
            details: Dictionary containing trigger details
            start_new_thread: Whether to start a new thread for this event
            
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        title = f"Strategy Triggered: {trigger_type}"
        message = f"Liberty Flow strategy has been triggered via {trigger_type}"
        
        # Start new thread if requested and not already in a thread
        if start_new_thread and not self.current_strategy_thread:
            self.start_new_strategy_thread(f"Strategy triggered: {trigger_type}")
        
        fields = []
        for key, value in details.items():
            fields.append({
                "title": key.replace("_", " ").title(),
                "value": str(value)
            })
            
        return self.slack_client.send_alert(
            title=title,
            message=message,
            level="warning",
            fields=fields,
            channel=self.default_channel,
            thread_ts=self.current_strategy_thread
        )
        
    def handle_swing_formation(self, 
                              swing_type: str, 
                              price: float, 
                              details: Dict[str, Any]) -> bool:
        """
        Handle swing formation event.
        
        Args:
            swing_type: Type of swing ("high" or "low")
            price: Price at which the swing was formed
            details: Dictionary containing swing details
            
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        title = f"Swing {swing_type.title()} Formed"
        message = f"Swing {swing_type} formed at price {price}"
        
        fields = []
        for key, value in details.items():
            fields.append({
                "title": key.replace("_", " ").title(),
                "value": str(value)
            })
            
        return self.slack_client.send_alert(
            title=title,
            message=message,
            level="info",
            fields=fields,
            channel=self.default_channel,
            thread_ts=self.current_strategy_thread
        )
        
    def handle_breakout(self, 
                       breakout_type: str, 
                       price: float, 
                       details: Dict[str, Any]) -> bool:
        """
        Handle breakout event.
        
        Args:
            breakout_type: Type of breakout ("high" or "low")
            price: Price at which the breakout occurred
            details: Dictionary containing breakout details
            
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        title = f"Breakout: Swing {breakout_type.title()}"
        message = f"Price broke {breakout_type} swing level at {price}"
        
        fields = []
        for key, value in details.items():
            fields.append({
                "title": key.replace("_", " ").title(),
                "value": str(value)
            })
            
        return self.slack_client.send_alert(
            title=title,
            message=message,
            level="warning",
            fields=fields,
            channel=self.default_channel,
            thread_ts=self.current_strategy_thread
        )
        
    def handle_order_placed(self, order_details: Dict[str, Any]) -> bool:
        """
        Handle order placed event.
        
        Args:
            order_details: Dictionary containing order details
            
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        title = "Order Placed"
        message = f"Liberty Flow strategy placed an order: {order_details.get('symbol', '')}"
        
        fields = []
        for key, value in order_details.items():
            if key != "symbol":  # Symbol is already in the message
                fields.append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value)
                })
            
        return self.slack_client.send_alert(
            title=title,
            message=message,
            level="success",
            fields=fields,
            channel=self.default_channel,
            thread_ts=self.current_strategy_thread
        )
        
    def handle_strategy_exit(self, 
                            exit_reason: str, 
                            pnl: Optional[float] = None, 
                            details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle strategy exit event.
        
        Args:
            exit_reason: Reason for exiting the strategy
            pnl: Optional profit/loss amount
            details: Optional dictionary containing exit details
            
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        title = "Strategy Exited"
        message = f"Liberty Flow strategy exited: {exit_reason}"
        
        fields = []
        if pnl is not None:
            fields.append({
                "title": "P&L",
                "value": str(pnl)
            })
            
        if details:
            for key, value in details.items():
                fields.append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value)
                })
                
        level = "success" if pnl and pnl > 0 else "warning"
            
        return self.slack_client.send_alert(
            title=title,
            message=message,
            level=level,
            fields=fields,
            channel=self.default_channel,
            thread_ts=self.current_strategy_thread
        )
        
    def handle_error(self, 
                    error_type: str, 
                    error_message: str, 
                    details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle error event.
        
        Args:
            error_type: Type of error
            error_message: Error message
            details: Optional dictionary containing error details
            
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        title = f"Error: {error_type}"
        message = error_message
        
        fields = []
        if details:
            for key, value in details.items():
                fields.append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value)
                })
                
        return self.slack_client.send_alert(
            title=title,
            message=message,
            level="error",
            fields=fields,
            channel=self.default_channel,
            thread_ts=self.current_strategy_thread
        )
        
    def upload_chart(self, 
                    file_path: str, 
                    title: Optional[str] = None, 
                    comment: Optional[str] = None) -> bool:
        """
        Upload a chart image to Slack.
        
        Args:
            file_path: Path to the chart image file
            title: Optional title for the chart
            comment: Optional comment to add with the chart
            
        Returns:
            bool: True if chart was uploaded successfully, False otherwise
        """
        if not hasattr(self.slack_client, 'upload_file'):
            logger.warning("Cannot upload chart: upload_file method not available")
            return False
            
        return self.slack_client.upload_file(
            file_path=file_path,
            title=title or "Liberty Flow Chart",
            initial_comment=comment,
            channel=self.default_channel
        )