#!/usr/bin/env python3
"""
Signal Bot using signal-cli-rest-api
Receives messages via WebSocket, verifies sender is in a specific group, and replies via REST API.
"""

import requests
import json
import sys
import logging
import time
import websocket
import threading
from typing import Optional, Dict, Any, Set

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalBotREST:
    def __init__(self, phone_number: str, group_id: str, api_url: str = "http://localhost:8080"):
        """
        Initialize the Signal bot using REST API.
        
        Args:
            phone_number: Your Signal phone number (e.g., "+1234567890")
            group_id: The group ID to verify membership against
            api_url: Base URL for signal-cli-rest-api (default: http://localhost:8080)
        """
        self.phone_number = phone_number
        self.group_id = group_id
        self.api_url = api_url.rstrip('/')
        self.group_members: Set[str] = set()
        self.last_member_refresh = 0  # Timestamp of last member list refresh
        self.member_refresh_interval = 300  # Refresh every 5 minutes (300 seconds)
        
    def verify_registration(self) -> bool:
        """
        Verify that the account is registered with the REST API.
        
        Returns:
            True if account is registered, False otherwise
        """
        logger.info(f"Verifying registration for {self.phone_number}...")
        
        try:
            # Try to get account info
            response = requests.get(
                f"{self.api_url}/v1/about",
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"✓ REST API is accessible at {self.api_url}")
                return True
            else:
                logger.error(f"✗ REST API returned status {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to REST API: {e}")
            logger.error(f"Make sure signal-cli-rest-api is running at {self.api_url}")
            return False
    
    def get_group_members(self) -> bool:
        """
        Fetch the list of members in the specified group via REST API.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Fetching members for group {self.group_id}")
        
        try:
            # Get groups list
            response = requests.get(
                f"{self.api_url}/v1/groups/{self.phone_number}",
                timeout=10
            )
            
            if response.status_code == 200:
                groups = response.json()
                logger.debug(f"API Response type: {type(groups)}")
                logger.debug(f"API Response: {groups}")
                
                # Handle if response is a dict with a 'groups' key
                if isinstance(groups, dict):
                    groups = groups.get('groups', [])
                
                # Ensure groups is a list
                if not isinstance(groups, list):
                    logger.error(f"Unexpected response format. Expected list, got {type(groups)}")
                    return False
                
                for group in groups:
                    # Handle both dict and string group items
                    if isinstance(group, str):
                        logger.warning(f"Group item is a string, not a dict: {group}")
                        continue
                    
                    if not isinstance(group, dict):
                        logger.warning(f"Group item is not a dict: {type(group)}")
                        continue
                    
                    # Check multiple possible group ID fields
                    group_id = group.get('id', '')
                    internal_id = group.get('internal_id', '')
                    group_id_alt = group.get('groupId', '')
                    
                    logger.debug(f"Group IDs - id: '{group_id}', internal_id: '{internal_id}', groupId: '{group_id_alt}'")
                    logger.debug(f"Target group_id: '{self.group_id}'")
                    logger.debug(f"Group data: {group}")
                    
                    # Match against any of the possible ID fields
                    if self.group_id in (group_id, internal_id, group_id_alt):
                        # Extract phone numbers from members
                        members = group.get('members', [])
                        self.group_members = set()
                        
                        for member in members:
                            if isinstance(member, dict):
                                number = member.get('number') or member.get('uuid') or member.get('recipientAddress')
                                if number:
                                    self.group_members.add(number)
                            elif isinstance(member, str):
                                self.group_members.add(member)
                        
                        logger.info(f"✓ Successfully fetched group members: {len(self.group_members)} members")
                        logger.debug(f"Members: {self.group_members}")
                        return True
                
                logger.warning(f"Group {self.group_id} not found in {len(groups)} groups")
                return False
            else:
                logger.error(f"Failed to fetch groups: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching group members: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
    
    def is_member_of_group(self, sender: str) -> bool:
        """
        Check if a sender is a member of the specified group.
        
        Args:
            sender: Phone number or UUID of the sender
            
        Returns:
            True if sender is in the group, False otherwise
            If group members couldn't be fetched, returns True (accept all)
        """
        current_time = time.time()
        
        # Refresh member list if it's been too long or if it's empty
        if not self.group_members or (current_time - self.last_member_refresh) > self.member_refresh_interval:
            logger.info("Refreshing group members list...")
            if self.get_group_members():
                self.last_member_refresh = current_time
            else:
                logger.warning("Could not refresh group members")
                # If we've never successfully fetched members, accept all
                if not self.group_members:
                    logger.warning("No group members cached - accepting message from all senders")
                    return True
        
        is_member = sender in self.group_members
        logger.info(f"Sender {sender} is {'a' if is_member else 'not a'} member of the group")
        return is_member
    
    def send_message(self, recipient: str, message: str) -> bool:
        """
        Send a message via REST API.
        
        Args:
            recipient: Phone number to send the message to
            message: Message content
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Sending message to {recipient}: {message}")
        
        try:
            payload = {
                "message": message,
                "number": self.phone_number,
                "recipients": [recipient]
            }
            
            response = requests.post(
                f"{self.api_url}/v2/send",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 201:
                logger.info("✓ Message sent successfully")
                return True
            else:
                logger.error(f"Failed to send message: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def process_message(self, message_data: Dict[str, Any]) -> None:
        """
        Process a received message.
        
        Args:
            message_data: Dictionary containing message information
        """
        try:
            envelope = message_data.get('envelope', {})
            source = envelope.get('source') or envelope.get('sourceNumber')
            
            # Log all envelope types for debugging
            logger.debug(f"Processing envelope - source: {source}, keys: {list(envelope.keys())}")
            
            if not source:
                logger.debug("Message has no source (typing indicator, etc.), skipping")
                return
            
            # Check for sync messages (when bot performs actions)
            sync_message = envelope.get('syncMessage', {})
            if sync_message:
                # Check if this is a sent message with group info
                sent_message = sync_message.get('sentMessage', {})
                if sent_message:
                    sent_group_info = sent_message.get('groupInfo', {})
                    if sent_group_info:
                        group_id = sent_group_info.get('groupId')
                        update_type = sent_group_info.get('type', 'UNKNOWN')
                        if group_id == self.group_id and update_type == 'UPDATE':
                            logger.info(f"🔄 Bot performed group {update_type}, refreshing member list and checking for new members...")
                            
                            # Store old members before refresh
                            old_members = self.group_members.copy()
                            
                            if self.get_group_members():
                                logger.info(f"✓ Member list refreshed successfully")
                                
                                # Find new members (in current list but not in old list)
                                new_members = self.group_members - old_members
                                
                                if new_members:
                                    logger.info(f"👋 New member(s) detected: {new_members}")
                                    welcome_message = (
                                        "Welcome to the Bancroft Welcome Lobby! 🎉\n\n"
                                        "I'm a bot that can help you join various community groups. "
                                        "These are the available commands I currently accept.\n\n"
                                        "For the available groups:\n"
                                        "join 1 - Mutual Aid & Sanctuary Lobby\n"
                                        "join 2 - Community Resource Hub\n"
                                        "join 3 - IT & Low Tech\n"
                                        "join 4 - Monitor/Patrol Group (vetted)\n"
                                        "join 5 - Bancroft Elementary (vetted)\n"
                                        "join 6 - Block Captains (vetted)\n"
                                        "join 7 - General Chat\n"
                                        "join 8 - Bancroft ICE Alerts"
                                    )
                                    
                                    # Send welcome message to each new member
                                    for new_member in new_members:
                                        # Don't send welcome to the bot itself
                                        if new_member != self.phone_number:
                                            logger.info(f"Sending welcome message to {new_member}")
                                            self.send_message(new_member, welcome_message)
                            else:
                                logger.warning(f"⚠ Failed to refresh member list")
                            self.last_member_refresh = time.time()
                logger.debug(f"Sync message from {source}, skipping further processing")
                return
            
            # Skip other messages from the bot itself (but not sync messages)
            if source == self.phone_number:
                logger.debug(f"Skipping non-sync message from bot itself ({source})")
                return
            
            # Check if this is a data message (actual text message)
            data_message = envelope.get('dataMessage', {})
            if not data_message:
                logger.debug(f"Non-data message from {source} (receipt, typing, etc.), skipping")
                return
            
            # Check for group info updates (member joins/leaves)
            group_info = data_message.get('groupInfo', {})
            if group_info:
                group_id = group_info.get('groupId')
                update_type = group_info.get('type', 'UNKNOWN')
                
                # Log the full group_info structure for debugging
                logger.debug(f"Group info structure: {json.dumps(group_info, indent=2)}")
                
                if group_id == self.group_id:
                    logger.info(f"🔄 Group {update_type} detected for {self.group_id}, refreshing member list...")
                    
                    # Check for members being added to the group
                    # Signal can have 'membersAdded' field in groupInfo
                    members_added = group_info.get('membersAdded', [])
                    
                    if members_added:
                        logger.info(f"👋 Members added to group: {members_added}")
                        welcome_message = (
                                "Welcome to the Bancroft Welcome Lobby! 🎉\n\n"
                                "I'm a bot that can help you join various community groups. "
                                "These are the available commands I currently accept.\n\n"
                                "For the available groups, you can type 'join <number>' where <number> is 1-8\n"
                                "type 'join 1' for Mutual Aid & Sanctuary Lobby\n"
                                "type 'join 2' for Community Resource Hub\n"
                                "type 'join 3' for IT & Low Tech\n"
                                "type 'join 4' for Monitor/Patrol Group (vetted)\n"
                                "type 'join 5' for Bancroft Elementary (vetted)\n"
                                "type 'join 6' for Block Captains (vetted)\n"
                                "type 'join 7' for General Chat\n"
                                "type 'join 8' for Bancroft ICE Alerts"
                        )
                        repeat_message = (
                                "For the available groups, you can type 'join <number>' where <number> is 1-8\n"
                                "type 'join 1' for Mutual Aid & Sanctuary Lobby\n"
                                "type 'join 2' for Community Resource Hub\n"
                                "type 'join 3' for IT & Low Tech\n"
                                "type 'join 4' for Monitor/Patrol Group (vetted)\n"
                                "type 'join 5' for Bancroft Elementary (vetted)\n"
                                "type 'join 6' for Block Captains (vetted)\n"
                                "type 'join 7' for General Chat\n"
                                "type 'join 8' for Bancroft ICE Alerts"
                        )
                        
                        # Send welcome message to each added member
                        for member in members_added:
                            # Extract phone number from member object
                            if isinstance(member, dict):
                                member_number = member.get('number') or member.get('uuid') or member.get('recipientAddress')
                            else:
                                member_number = member
                            
                            # Don't send welcome to the bot itself
                            if member_number and member_number != self.phone_number:
                                logger.info(f"Sending welcome message to {member_number}")
                                self.send_message(member_number, welcome_message)
                    
                    if self.get_group_members():
                        logger.info(f"✓ Member list refreshed successfully")
                    else:
                        logger.warning(f"⚠ Failed to refresh member list")
                    self.last_member_refresh = time.time()
                # Skip processing group update messages as regular messages
                logger.debug(f"Group update message from {source}, skipping text processing")
                return
            
            message_text = data_message.get('message')
            
            # Skip empty or null messages
            if not message_text:
                logger.debug(f"Empty or null message from {source}, skipping")
                return
            
            message_text = message_text.strip()
            
            if not message_text:
                logger.debug(f"Empty message from {source}, skipping")
                return
            
            logger.info(f"📨 Received message from {source}: {message_text}")
            logger.info(f"🔍 Processing command - message_lower will be: {message_text.lower()}")
            
            # Check if sender is in the group and send a reply based on message content
            if self.is_member_of_group(source):
                logger.info(f"✓ Sender {source} is verified as group member")
                # Convert message to lowercase for case-insensitive comparison
                message_lower = message_text.lower()
                
                if message_lower == "join 1":
                    reply_text = "Here's the Link for 1; Mutual Aid & Sanctuary Lobby"
                    self.send_message(source, reply_text)
                elif message_lower == "join 2":
                    reply_text = "Here's the Link for 2; Community Resource Hub"
                    self.send_message(source, reply_text)
                elif message_lower == "join 3":
                    reply_text = "Here's the Link for 3; IT & Low Tech"
                    self.send_message(source, reply_text)
                elif message_lower == "join 4":
                    reply_text = "Monitor/Patrol Group is a vetted chat, you'll have to get the link from an admin"
                    self.send_message(source, reply_text)
                elif message_lower == "join 5":
                    reply_text = "Bancroft Elementary is a vetted chat, you'll have to get the link from an admin"
                    self.send_message(source, reply_text)
                elif message_lower == "join 6":
                    reply_text = "Block Captains is a vetted chat, you'll have to get the link from an admin"
                    self.send_message(source, reply_text)
                elif message_lower == "join 7":
                    reply_text = "Here's the Link for 7; General Chat"
                    self.send_message(source, reply_text)
                elif message_lower == "join 8":
                    reply_text = "Here's the Link for 8; Bancroft ICE Alerts"
                    self.send_message(source, reply_text)
                elif message_lower.startswith("join"):
                    # Message starts with "join" but is not a valid command
                    reply_text = f"Hello! I received your message: '{message_text}', but I only accept the numbers 1 through 8 after 'join'."
                    self.send_message(source, reply_text)
                else:
                    # Message doesn't start with "join" at all
                    reply_text = f"Hello! I received your message: '{message_text}', but it's not a recognized command; try using these commands: 'join 1', 'join 2', 'join 3', 'join 4', 'join 5', 'join 6', 'join 7', or 'join 8'."
                    self.send_message(source, reply_text)
            else:
                logger.warning(f"❌ Sender {source} is not in the authorized group")
                # Send a rejection message
                rejection_text = "Sorry, you are not authorized to use this bot. Only members of the authorized group can interact with me."
                self.send_message(source, rejection_text)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def on_message(self, ws, message):
        """WebSocket message handler."""
        try:
            data = json.loads(message)
            logger.debug(f"WebSocket message: {json.dumps(data, indent=2)}")
            
            # Check if this message has an envelope (actual message data)
            if 'envelope' in data:
                self.process_message(data)
            else:
                logger.debug("Message without envelope, skipping")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error in WebSocket handler: {e}")
    
    def on_error(self, ws, error):
        """WebSocket error handler."""
        logger.error(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket close handler."""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
    
    def on_open(self, ws):
        """WebSocket open handler."""
        logger.info("✓ WebSocket connection established")
    
    def receive_messages(self) -> None:
        """
        Start receiving messages via WebSocket.
        """
        logger.info("Starting to receive messages via WebSocket...")
        
        # First, verify the REST API is accessible
        if not self.verify_registration():
            logger.error("Cannot connect to REST API. Exiting.")
            return
        
        # Try to fetch group members
        if not self.get_group_members():
            logger.warning("Could not fetch group members initially, will accept all messages for now")
            logger.warning("Group verification will be disabled until members are fetched")
        
        # Build WebSocket URL
        ws_url = self.api_url.replace('http://', 'ws://').replace('https://', 'wss://')
        ws_url = f"{ws_url}/v1/receive/{self.phone_number}"
        
        logger.info(f"Connecting to WebSocket: {ws_url}")
        
        # Create WebSocket connection
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        # Run WebSocket in a loop with auto-reconnect
        while True:
            try:
                logger.info("Starting WebSocket connection...")
                ws.run_forever()
                logger.warning("WebSocket connection closed, reconnecting in 5 seconds...")
                time.sleep(5)
            except KeyboardInterrupt:
                logger.info("Stopping message reception...")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                logger.info("Reconnecting in 5 seconds...")
                time.sleep(5)


def main():
    """Main entry point for the script."""
    # Configuration - Update these values
    PHONE_NUMBER = "+16124679789"  # Your Signal phone number
    GROUP_ID = "PC3uaxhx3gppAdVRu9life/xgfkZyFn4odjX75/pd9I="  # The group ID to verify against
    API_URL = "http://localhost:8080"  # signal-cli-rest-api URL
    
    # Validate configuration
    if PHONE_NUMBER == "+1234567890" or GROUP_ID == "your-group-id-here":
        logger.error("Please update PHONE_NUMBER and GROUP_ID in the script")
        sys.exit(1)
    
    # Create and run the bot
    bot = SignalBotREST(PHONE_NUMBER, GROUP_ID, API_URL)
    bot.receive_messages()


if __name__ == "__main__":
    main()
