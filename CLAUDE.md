# YubiKey Daemon - Claude Code Instructions

This file contains project-specific instructions for Claude Code when working on the yk-daemon project.

## Project Overview

This is a Windows daemon written in Python that bridges YubiKey OATH-TOTP functionality to WSL and other local applications. The daemon runs on Windows (where USB YubiKey is accessible) and exposes REST API and socket interfaces on localhost.

## Architecture Principles

1. **Python-based**: All code should be Python 3.12+
2. **Dependency Management**: Use Poetry for all dependency management
3. **Dual Interface**: Maintain both REST API (Flask) and TCP socket server
4. **Windows-first**: Designed to run as a Windows service/background process
5. **Localhost Only**: Security by default - bind to 127.0.0.1 only
6. **Single YubiKey**: Support one YubiKey at a time (for now)

## Key Technical Decisions

### YubiKey Integration
- Use `yubikey-manager` (ykman) library for YubiKey OATH-TOTP operations
- Focus on OATH-TOTP only (not FIDO2, PIV, or other modes)
- Require physical touch for each TOTP generation

### Communication Protocols
- **REST API**: Flask on port 5000 (default)
  - JSON responses
  - Simple GET endpoints
  - Health check endpoint
- **Socket Server**: TCP on port 5001 (default)
  - Line-based protocol (commands end with `\n`)
  - Simple text responses: `OK <result>` or `ERROR <message>`

### Notifications
- **Popup**: Use Windows notification system (win10toast or plyer)
- **Sound**: Play notification sound when YubiKey touch required
- Both should be configurable (on/off)

### Windows Service
- Use `pywin32` for Windows service functionality
- Support command-line arguments: `--install`, `--start`, `--stop`, `--remove`, `--debug`
- Log to file when running as service
- Support foreground mode for development/debugging

## Code Structure

```
src/
├── yubikey.py        # YubiKey interface (ykman wrapper)
├── rest_api.py       # Flask REST API
├── socket_server.py  # TCP socket server
├── notifications.py  # Windows popup + sound
├── service.py        # Windows service wrapper
└── config.py         # Configuration loading/validation
```

## Development Guidelines

### When implementing YubiKey functionality:
- Use `ykman.device` for device detection
- Use `ykman.oath` for OATH-TOTP operations
- Handle device not found gracefully
- Handle device removed during operation
- Always show notification before requesting touch

### When implementing API endpoints:
- Keep responses simple and consistent
- Always include `success` boolean in JSON responses
- Include timestamps in ISO 8601 format
- Handle YubiKey errors gracefully (return 503 Service Unavailable)
- Log all requests for audit purposes

### When implementing socket protocol:
- Keep it simple: line-based protocol
- Commands: `GET_TOTP`, `GET_TOTP <account>`, `LIST_ACCOUNTS`
- Responses: `OK <data>` or `ERROR <message>`
- Handle multiple concurrent connections
- Use threading for socket server

### Error Handling:
- Never crash the daemon on YubiKey errors
- Log all errors with context
- Return meaningful error messages to clients
- Distinguish between:
  - YubiKey not connected (503 Service Unavailable)
  - User didn't touch in time (408 Request Timeout)
  - Account not found (404 Not Found)
  - Internal errors (500 Internal Server Error)

### Configuration:
- Load from `config.json` if exists
- Provide sensible defaults
- Validate configuration on load
- Support environment variable overrides for common settings

### Logging:
- Use Python `logging` module
- Log to file and console (in debug mode)
- Include timestamps, log level, and context
- Log levels:
  - DEBUG: Detailed protocol/operation info
  - INFO: Requests, YubiKey operations
  - WARNING: Retryable errors, timeouts
  - ERROR: Fatal errors, YubiKey disconnected
  - CRITICAL: Service failures

### Testing:
- Write unit tests for each module
- Mock YubiKey operations in tests
- Test error conditions
- Test concurrent requests
- Provide example client scripts in `examples/`
- Run tests with: `poetry run pytest tests/`
- Check coverage: `poetry run pytest --cov=src tests/`
- Lint code: `poetry run ruff check .`
- Format code: `poetry run ruff format .`

## Dependencies

All dependencies are managed via Poetry in `pyproject.toml`.

### Core:
- `yubikey-manager`: YubiKey OATH interface
- `Flask`: REST API framework
- `pywin32`: Windows service support

### Notifications:
- `plyer`: Cross-platform notifications (use Windows backend)
- OR `win10toast`: Windows 10 toast notifications
- `pygame` or `playsound`: Sound playback

### Development:
- `pytest`: Testing framework
- `pytest-cov`: Coverage reporting
- `ruff`: Modern linting and formatting (replaces black + flake8)
- `mypy`: Type checking

### Installing Dependencies:
```bash
# Install all dependencies including dev
poetry install

# Install only production dependencies
poetry install --without dev

# Add a new dependency
poetry add <package-name>

# Add a dev dependency
poetry add --group dev <package-name>
```

## Security Notes

### Current Security Model:
- Localhost-only binding (127.0.0.1)
- No authentication required
- Any local process can access
- Physical YubiKey touch required for TOTP

### Future Security Enhancements (not now):
- API key/token authentication
- Process whitelisting
- Request rate limiting
- TLS for socket connections

## Common Pitfalls

1. **YubiKey library initialization**: ykman requires proper device detection before any operations
2. **Threading**: Flask and socket server need separate threads, handle shutdown gracefully
3. **Windows service**: Must handle Windows service events (stop, pause, continue)
4. **WSL networking**: Use 127.0.0.1 (not localhost) for consistent behavior
5. **Touch timeout**: YubiKey touch has timeout, handle gracefully

## Testing Strategy

1. **Unit tests**: Mock YubiKey, test logic
2. **Integration tests**: Use test YubiKey if available
3. **Manual testing**: Test from WSL with curl and netcat
4. **Service testing**: Install and run as Windows service

## Commit Message Style

Follow conventional commits:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation only
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Build process, dependencies

Examples:
- `feat: add REST API for TOTP generation`
- `fix: handle YubiKey disconnect during operation`
- `docs: update API documentation with examples`

## Priority Order for Implementation

1. Poetry setup and project configuration (`pyproject.toml`)
2. Core YubiKey OATH integration (`src/yubikey.py`)
3. Configuration management (`src/config.py`)
4. REST API (`src/rest_api.py`)
5. Socket server (`src/socket_server.py`)
6. Notifications (`src/notifications.py`)
7. Main daemon entry point (`yk-daemon.py`)
8. Windows service wrapper (`src/service.py`)
9. Tests and examples
10. Documentation refinements

## When in Doubt

- **Simplicity over features**: Start simple, add features later
- **Error handling over crashes**: Never let daemon crash
- **Logging over silence**: Log important operations
- **Security by default**: Localhost-only, no network exposure
- **WSL compatibility**: Test that it works from WSL before considering done

## Resources

- YubiKey Manager CLI: https://github.com/Yubico/yubikey-manager
- Flask documentation: https://flask.palletsprojects.com/
- Python Windows services: https://stackoverflow.com/questions/32404/how-do-you-run-a-python-script-as-a-service-in-windows
- WSL networking: https://learn.microsoft.com/en-us/windows/wsl/networking
