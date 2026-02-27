# Bancroft-Welcome-Lobby-Bot
A bot that uses the Signal RESTful server API to automate traffic
# Signal Bot - Community Group Manager

A Python-based Signal bot that manages community group access through automated welcome messages and command-based group invitations. The bot uses the `signal-cli-rest-api` to receive messages via WebSocket and respond via REST API.

## Features

- **Automated Welcome Messages**: Automatically greets new members when they join the group
- **Group Verification**: Only responds to messages from verified group members
- **Command-Based Group Access**: Users can request to join different community groups using simple commands
- **Auto-Reconnect**: Automatically reconnects if the WebSocket connection drops
- **Member List Caching**: Periodically refreshes group member list (every 5 minutes)
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

## Prerequisites

- Python 3.7 or higher
- [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) running locally or on a server
- A registered Signal account with signal-cli
- Access to a Signal group where the bot is a member

## Installation

1. **Clone or download this repository**

2. **Install required Python packages:**
```bash
pip install requests websocket-client
pip install signalbot
```

3. **Set up signal-cli-rest-api:**
   - Follow the [signal-cli-rest-api documentation](https://github.com/bbernhard/signal-cli-rest-api) to set up and register your Signal account
   - Ensure the API is running (default: `http://localhost:8080`)

## Configuration

Edit the `main()` function in `signalbot.py` to configure your bot:

```python
PHONE_NUMBER = "phone number"  # Your Signal phone number
GROUP_ID = "group ID"  # The group ID to verify against
API_URL = "http://localhost:8080"  # signal-cli-rest-api URL
```

### Finding Your Group ID

To find your group ID, you can:
1. Use the signal-cli-rest-api endpoint: `GET /v1/groups/{phone_number}`
2. Check the API response for the group you want to use
3. The group ID is typically a base64-encoded string

## Usage

### Running the Bot

```bash
python signalbot.py
```

Or make it executable:
```bash
chmod +x signalbot.py
./signalbot.py
```

### Available Commands

Users in the authorized group can send these commands to the bot:

- `join 1` - Mutual Aid & Sanctuary Lobby
- `join 2` - Community Resource Hub
- `join 3` - IT & Low Tech
- `join 4` - Monitor/Patrol Group (vetted)
- `join 5` - Bancroft Elementary (vetted)
- `join 6` - Block Captains (vetted)
- `join 7` - General Chat
- `join 8` - Bancroft ICE Alerts

**Note:** Groups 4, 5, and 6 are marked as "vetted" and require admin approval. The bot will inform users to contact an admin for access.

### Customizing Commands

To modify the available groups or add new commands, edit the `process_message()` method in the `SignalBotREST` class:

```python
if message_lower == "join 1":
    reply_text = "Here's the Link for 1; Mutual Aid & Sanctuary Lobby"
    self.send_message(source, reply_text)
```

## How It Works

1. **WebSocket Connection**: The bot connects to signal-cli-rest-api via WebSocket to receive real-time messages
2. **Message Processing**: When a message is received, the bot:
   - Verifies the sender is a member of the authorized group
   - Parses the message for valid commands
   - Sends appropriate responses via REST API
3. **New Member Detection**: When new members join the group, the bot automatically sends them a welcome message with available commands
4. **Auto-Refresh**: The bot periodically refreshes the group member list to stay up-to-date

## Architecture

### Class: `SignalBotREST`

**Key Methods:**
- `verify_registration()` - Verifies the REST API is accessible
- `get_group_members()` - Fetches current group members
- `is_member_of_group()` - Checks if a sender is authorized
- `send_message()` - Sends messages via REST API
- `process_message()` - Handles incoming messages and commands
- `receive_messages()` - Starts the WebSocket listener

## Logging

The bot uses Python's built-in logging module with DEBUG level enabled. Logs include:
- Connection status
- Message reception and processing
- Group member updates
- Errors and warnings

To adjust logging level, modify:
```python
logging.basicConfig(
    level=logging.INFO,  # Change to INFO, WARNING, or ERROR
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

## Security Considerations

- **Group Verification**: Only members of the specified group can interact with the bot
- **Unauthorized Access**: Non-members receive a rejection message
- **Vetted Groups**: Sensitive groups require admin approval rather than automatic access
- **API Access**: Ensure your signal-cli-rest-api is not publicly accessible without proper security measures

## Troubleshooting

### Bot doesn't respond to messages
- Check that signal-cli-rest-api is running
- Verify the `PHONE_NUMBER` and `GROUP_ID` are correct
- Check logs for connection errors
- Ensure the bot's Signal account is a member of the group

### WebSocket connection fails
- Verify the API URL is correct
- Check if the API is accessible: `curl http://localhost:8080/v1/about`
- Review firewall settings if running on a remote server

### Group members not detected
- Ensure the bot has permission to view group members
- Check the group ID format (should be base64-encoded)
- Review API logs for group fetch errors

## Dependencies

- `requests` - HTTP library for REST API calls
- `websocket-client` - WebSocket client for receiving messages
- `json` - JSON parsing (built-in)
- `logging` - Logging functionality (built-in)
- `threading` - Thread management (built-in)
