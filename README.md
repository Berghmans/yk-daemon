# YubiKey Daemon (yk-daemon)

[![CI](https://github.com/Berghmans/yk-daemon/actions/workflows/ci.yml/badge.svg)](https://github.com/Berghmans/yk-daemon/actions/workflows/ci.yml)

A Windows daemon/service that provides YubiKey OATH-TOTP access to WSL (Windows Subsystem for Linux) and other local applications via REST API and socket interfaces.

## Problem Statement

WSL 'cannot' directly access USB devices like YubiKeys due to USB passthrough limitations. This daemon bridges that gap by running on Windows (where YubiKey is accessible) and exposing its functionality to WSL applications.

## Features

- **OATH-TOTP Support**: Generate time-based one-time passwords from YubiKey
- **Dual Interface**:
  - REST API (HTTP) for easy integration
  - TCP Socket for low-latency requests
- **User Notifications**: Optional popup windows and sound alerts when YubiKey touch is required
- **Background Service**: Runs as a Windows background process
- **Localhost Only**: Secure by default, only accessible from local machine
- **WSL Compatible**: Seamless integration with Linux applications in WSL

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Windows                          │
│                                                         │
│  ┌──────────────┐         ┌─────────────────────────┐  │
│  │   YubiKey    │◄────────┤    yk-daemon (Python)   │  │
│  │   (USB)      │         │  - REST API (port 5000) │  │
│  └──────────────┘         │  - Socket (port 5001)   │  │
│                           │  - Notifications        │  │
│                           └─────────┬───────────────┘  │
│                                     │                   │
└─────────────────────────────────────┼───────────────────┘
                                      │ localhost (127.0.0.1)
                                      │
┌─────────────────────────────────────┼───────────────────┐
│                        WSL          │                   │
│                                     ▼                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Linux Applications / Scripts                    │  │
│  │  - curl http://127.0.0.1:5000/api/totp           │  │
│  │  - netcat 127.0.0.1 5001                         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Windows 10/11
- Python 3.12+
- Poetry (Python dependency management)
- YubiKey with OATH-TOTP configured
- WSL 2 (if accessing from Linux)

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd yk-daemon

# Install Poetry (if not already installed)
# See: https://python-poetry.org/docs/#installation

# Install dependencies
poetry install

# Configure (optional)
cp config.example.json config.json
# Edit config.json with your preferences

# Run the daemon
poetry run python yk-daemon.py
```

### Running as Windows Service

```bash
# Install as service
poetry run python yk-daemon.py --install

# Start service
poetry run python yk-daemon.py --start

# Stop service
poetry run python yk-daemon.py --stop

# Uninstall service
poetry run python yk-daemon.py --remove
```

## API Documentation

### REST API

Base URL: `http://127.0.0.1:5000`

#### Get TOTP Code

```http
GET /api/totp
```

**Response:**
```json
{
  "success": true,
  "totp": "123456",
  "timestamp": "2025-10-17T12:34:56Z"
}
```

#### List Available TOTP Accounts

```http
GET /api/accounts
```

**Response:**
```json
{
  "success": true,
  "accounts": [
    {"name": "GitHub", "issuer": "github.com"},
    {"name": "AWS", "issuer": "aws.amazon.com"}
  ]
}
```

#### Get TOTP for Specific Account

```http
GET /api/totp/<account_name>
```

**Response:**
```json
{
  "success": true,
  "account": "GitHub",
  "totp": "123456",
  "timestamp": "2025-10-17T12:34:56Z"
}
```

#### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "yubikey_connected": true,
  "version": "0.1.0"
}
```

### Socket Protocol

Connect to: `127.0.0.1:5001`

#### Get TOTP Code

**Request:**
```
GET_TOTP\n
```

**Response:**
```
OK 123456\n
```

#### Get TOTP for Specific Account

**Request:**
```
GET_TOTP GitHub\n
```

**Response:**
```
OK 123456\n
```

#### List Accounts

**Request:**
```
LIST_ACCOUNTS\n
```

**Response:**
```
OK GitHub,AWS,Google\n
```

#### Error Response

```
ERROR <error_message>\n
```

## Configuration

Create a `config.json` file:

```json
{
  "rest_api": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 5000
  },
  "socket": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 5001
  },
  "notifications": {
    "popup": true,
    "sound": true,
    "sound_file": "notification.wav"
  },
  "logging": {
    "level": "INFO",
    "file": "yk-daemon.log"
  }
}
```

## Usage Examples

### From WSL (curl)

```bash
# Get TOTP code
curl http://127.0.0.1:5000/api/totp

# Get TOTP for specific account
curl http://127.0.0.1:5000/api/totp/GitHub

# List accounts
curl http://127.0.0.1:5000/api/accounts
```

### From WSL (Python)

```python
import requests

response = requests.get('http://127.0.0.1:5000/api/totp')
data = response.json()
print(f"TOTP Code: {data['totp']}")
```

### From WSL (Socket)

```bash
# Using netcat
echo "GET_TOTP" | nc 127.0.0.1 5001
```

```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 5001))
sock.send(b'GET_TOTP\n')
response = sock.recv(1024).decode()
print(response)  # OK 123456
sock.close()
```

## Development

### Project Structure

```
yk-daemon/
├── README.md
├── CLAUDE.md
├── pyproject.toml        # Poetry configuration
├── poetry.lock           # Poetry lock file
├── config.json
├── yk-daemon.py          # Main daemon entry point
├── src/
│   ├── __init__.py
│   ├── yubikey.py        # YubiKey OATH-TOTP interface
│   ├── rest_api.py       # REST API server (Flask)
│   ├── socket_server.py  # TCP socket server
│   ├── notifications.py  # Windows notifications & sounds
│   ├── service.py        # Windows service wrapper
│   └── config.py         # Configuration management
├── tests/
│   ├── test_yubikey.py
│   ├── test_api.py
│   └── test_socket.py
└── examples/
    ├── bash_client.sh
    └── python_client.py
```

### Dependencies

Managed via Poetry (`pyproject.toml`):

- **yubikey-manager** (ykman): Official YubiKey library
- **Flask**: REST API framework
- **pywin32**: Windows service support
- **plyer**: Cross-platform notifications
- **pydub**: Sound playback (optional)

### Testing

```bash
# Run tests
poetry run pytest tests/

# Run with coverage
poetry run pytest --cov=src tests/

# Run linting
poetry run ruff check .

# Format code
poetry run ruff format .
```

## Roadmap

- [x] Project setup and documentation
- [ ] Core YubiKey OATH-TOTP integration
- [ ] REST API implementation
- [ ] Socket server implementation
- [ ] Windows notifications (popup + sound)
- [ ] Configuration management
- [ ] Windows service support
- [ ] Error handling and logging
- [ ] Unit tests
- [ ] Example client scripts
- [ ] Multiple YubiKey support
- [ ] Authentication/authorization
- [ ] FIDO2/U2F support
- [ ] PIV support
- [ ] GUI configuration tool

## Security Considerations

- **Localhost Only**: By default, daemon only listens on 127.0.0.1
- **No Authentication**: Currently no authentication required (any local process can access)
- **Physical Access**: YubiKey requires physical touch for TOTP operations
- **Audit Logging**: All requests are logged for audit purposes

### Future Security Enhancements

- Optional API key/token authentication
- Request rate limiting
- Process whitelisting
- Encrypted socket communication

## Troubleshooting

### YubiKey Not Detected

```bash
# Check YubiKey is connected
ykman list

# Check YubiKey OATH accounts
ykman oath accounts list
```

### Cannot Connect from WSL

1. Ensure Windows Firewall allows localhost connections
2. Verify daemon is running: `curl http://127.0.0.1:5000/health` from Windows
3. Check if ports are in use: `netstat -an | findstr "5000"`

### Service Won't Start

1. Check logs: `yk-daemon.log`
2. Run in foreground mode: `poetry run python yk-daemon.py --debug`
3. Verify Python path in service configuration

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Follow conventional commit format (see below)
5. Submit a pull request

### Conventional Commits

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automated versioning and changelog generation. Format your commit messages as:

```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` - New feature (minor version bump)
- `fix:` - Bug fix (patch version bump)
- `feat!:` or `BREAKING CHANGE:` - Breaking change (major version bump)
- `docs:` - Documentation only
- `chore:` - Maintenance tasks
- `test:` - Test additions or changes
- `refactor:` - Code refactoring

**Examples:**
```bash
feat: add REST API for TOTP generation
fix: handle YubiKey disconnect during operation
docs: update API documentation with examples
```

## Release Process

This project uses automated releases via GitHub Actions and [release-please](https://github.com/googleapis/release-please):

1. **Development**: Make changes and commit using conventional commit format
2. **Merge to main**: When commits are merged to main, release-please analyzes them
3. **Release PR**: If releasable commits exist, release-please creates/updates a Release PR with:
   - Version bump in `pyproject.toml`
   - Updated `CHANGELOG.md`
   - Release notes
4. **Release**: When the Release PR is merged, GitHub Actions automatically:
   - Builds distribution packages with Poetry
   - Creates a GitHub release with changelog
   - Uploads wheel and sdist artifacts
   - Tags the release

### Version Bumping Rules

- `feat:` commits trigger a **minor** version bump (0.1.0 → 0.2.0)
- `fix:` commits trigger a **patch** version bump (0.1.0 → 0.1.1)
- `feat!:` or commits with `BREAKING CHANGE:` trigger a **major** version bump (0.1.0 → 1.0.0)
- Other commit types (`docs:`, `chore:`, etc.) are included in changelog but don't bump version

## License

[Specify your license here]

## Author

Olivier Berghmans (olivier@cloudar.be)

## Acknowledgments

- Yubico for YubiKey hardware and software libraries
- The WSL team for making Windows/Linux integration possible
