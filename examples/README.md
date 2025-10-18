# YubiKey Daemon - Client Examples

This directory contains example client scripts demonstrating how to interact with the YubiKey daemon from WSL and other local applications.

## Overview

The YubiKey daemon exposes two interfaces for client communication:

1. **REST API** (HTTP/JSON) - Port 5100 (default)
2. **Socket Server** (TCP/Text) - Port 5101 (default)

Both interfaces provide the same functionality:
- List OATH accounts on YubiKey
- Generate TOTP codes for accounts
- Health/status checking

## Available Examples

### 1. `bash_client.sh` - Bash Script (curl + netcat)

Comprehensive bash script demonstrating both REST API and socket protocols using standard command-line tools.

```bash
# Make executable (if not already)
chmod +x bash_client.sh

# Test both REST API and socket server
./bash_client.sh

# Test only REST API
./bash_client.sh --rest-only

# Test only socket server
./bash_client.sh --socket-only

# Get TOTP for specific account
./bash_client.sh --account "GitHub"

# Interactive socket mode
./bash_client.sh --interactive

# Custom host/ports
./bash_client.sh --host 192.168.1.100 --rest-port 8000
```

**Features:**
- Colorized output with status indicators
- Error handling and timeout management
- JSON formatting (if `jq` is available)
- Interactive socket session mode
- Dependency checking (curl, netcat, jq)

**Prerequisites:**
- `curl` - for REST API calls
- `netcat` (nc) - for socket communication
- `jq` (optional) - for JSON formatting

### 2. `rest_api_client.py` - Python REST API Client

Python script using the `requests` library to demonstrate REST API usage.

```bash
# Install dependencies
pip install requests

# Basic usage
python rest_api_client.py

# Custom host/port
python rest_api_client.py --host 127.0.0.1 --port 8000

# Get TOTP for specific account
python rest_api_client.py --account "AWS"
```

**Features:**
- Clean JSON response formatting
- Comprehensive error handling
- Status code checking
- Timeout management
- Command-line argument parsing

### 3. `socket_client.py` - Python Socket Client

Python script using the `socket` library to demonstrate TCP socket protocol.

```bash
# Basic usage
python socket_client.py

# Interactive mode
python socket_client.py --interactive

# Custom host/port
python socket_client.py --host 127.0.0.1 --port 5002

# Get TOTP for specific account
python socket_client.py --account "Google"
```

**Features:**
- Line-based protocol implementation
- Interactive command session
- Concurrent connection handling
- Response parsing and validation
- Comprehensive error handling

### 4. `get_totp.py` - Direct YubiKey Interface

Direct YubiKey integration script (bypasses daemon) for development/testing.

```bash
# Direct YubiKey access
python get_totp.py
```

**Note:** This script directly accesses the YubiKey hardware and does not use the daemon services.

## Protocol Documentation

### REST API Endpoints

**Base URL:** `http://127.0.0.1:5100`

| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/health` | GET | Health check and YubiKey status | `{"success": true, "yubikey_status": "connected"}` |
| `/api/accounts` | GET | List all OATH accounts | `{"success": true, "accounts": ["GitHub", "AWS"]}` |
| `/api/totp` | GET | Get TOTP for first account | `{"success": true, "code": "123456", "account": "GitHub"}` |
| `/api/totp/<account>` | GET | Get TOTP for specific account | `{"success": true, "code": "654321", "account": "AWS"}` |

**Example requests:**
```bash
# Health check
curl http://127.0.0.1:5100/health

# List accounts
curl http://127.0.0.1:5100/api/accounts

# Get default TOTP
curl http://127.0.0.1:5100/api/totp

# Get specific account TOTP
curl http://127.0.0.1:5100/api/totp/GitHub
```

### Socket Protocol

**Connection:** TCP to `127.0.0.1:5101`

**Protocol:** Line-based, commands end with `\n`

| Command | Description | Response |
|---------|-------------|----------|
| `LIST_ACCOUNTS\n` | List all accounts | `OK GitHub,AWS,Google\n` |
| `GET_TOTP\n` | Get TOTP for first account | `OK 123456\n` |
| `GET_TOTP <account>\n` | Get TOTP for specific account | `OK 654321\n` |

**Response Format:**
- Success: `OK <data>\n`
- Error: `ERROR <message>\n`

**Example using netcat:**
```bash
# List accounts
echo "LIST_ACCOUNTS" | nc 127.0.0.1 5101

# Get default TOTP
echo "GET_TOTP" | nc 127.0.0.1 5101

# Get specific account TOTP
echo "GET_TOTP GitHub" | nc 127.0.0.1 5101
```

## Usage from WSL

All examples are designed to work seamlessly from WSL (Windows Subsystem for Linux):

1. **Start the YubiKey daemon on Windows** (where USB YubiKey is accessible)
2. **Run clients from WSL** using localhost (127.0.0.1) networking
3. **Touch YubiKey when prompted** during TOTP generation

### Common WSL Setup

```bash
# Install required tools (Ubuntu/Debian)
sudo apt update
sudo apt install curl netcat-openbsd jq python3-pip

# Install Python dependencies
pip3 install requests

# Test connectivity
./bash_client.sh --rest-only
```

## Error Handling Examples

All example scripts demonstrate proper error handling for common scenarios:

### Connection Errors
- Daemon not running
- Wrong host/port configuration
- Network connectivity issues

### YubiKey Errors
- YubiKey not connected
- No OATH accounts configured
- YubiKey removed during operation
- Touch timeout (user didn't touch YubiKey)

### Protocol Errors
- Invalid account names
- Malformed requests
- Server timeouts

### Example Error Responses

**REST API:**
```json
{
  "success": false,
  "error": "YubiKey not connected",
  "code": 503
}
```

**Socket Protocol:**
```
ERROR YubiKey not connected
ERROR Account 'InvalidAccount' not found
ERROR Touch timeout - please touch YubiKey
```

## Security Considerations

- **Localhost only:** All services bind to 127.0.0.1 (no network exposure)
- **No authentication:** Services trust all localhost connections
- **Physical security:** YubiKey touch required for TOTP generation
- **Process isolation:** Daemon runs with minimal privileges

## Troubleshooting

### Common Issues

1. **"Connection refused"**
   - Check if YubiKey daemon services are running
   - Verify host/port configuration
   - Check firewall settings

2. **"YubiKey not connected"**
   - Ensure YubiKey is plugged into USB port
   - Check YubiKey is recognized by Windows
   - Verify OATH accounts are configured

3. **"Touch timeout"**
   - Touch YubiKey LED when it blinks
   - Check YubiKey is not in use by another application
   - Increase timeout values if needed

4. **"No accounts found"**
   - Configure OATH accounts on YubiKey first
   - Use YubiKey Manager to add accounts
   - Verify accounts with `ykman oath accounts list`

### Debug Commands

```bash
# Check daemon processes
ps aux | grep -E "(rest_api|socket_server)"

# Test network connectivity
nc -zv 127.0.0.1 5100  # REST API
nc -zv 127.0.0.1 5101  # Socket server

# Check YubiKey detection
ykman oath accounts list
```

## Development

To add new examples or modify existing ones:

1. Follow the established patterns in existing scripts
2. Include comprehensive error handling
3. Support command-line arguments for flexibility
4. Add usage documentation
5. Test from both Windows and WSL environments

## Contributing

When adding new examples:
- Use clear, descriptive variable names
- Include inline documentation
- Handle edge cases gracefully
- Follow the project's coding style
- Update this README with new examples
