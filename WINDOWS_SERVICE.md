# Windows Service Configuration

## File Locations

When running as a Windows service, the daemon uses the following locations:

### Configuration File
```
C:\ProgramData\yk-daemon\config.json
```

**Override:** Set the `YK_DAEMON_CONFIG_PATH` environment variable to use a different location.

### Log File

The service attempts to write logs to the following locations (in priority order):

1. **Primary location** (preferred):
   ```
   C:\ProgramData\yk-daemon\yk-daemon.log
   ```

2. **Fallback location** (if ProgramData is not writable):
   ```
   C:\Users\<YourUser>\AppData\Local\Temp\yk-daemon.log
   ```

The actual log file location is logged at the start of each service run.

**Override:** Set the `logging.file` path in your config.json to use a different location.

## Installation

```powershell
# Install the service (run as Administrator)
yk-daemon --install

# The installation will display the exact paths for your system
```

## Setting Up Configuration

1. **Create the configuration directory** (if it doesn't exist):
   ```powershell
   mkdir C:\ProgramData\yk-daemon
   ```

2. **Create config.json** with your settings:
   ```json
   {
     "rest_api": {
       "enabled": true,
       "host": "127.0.0.1",
       "port": 5100
     },
     "socket": {
       "enabled": true,
       "host": "127.0.0.1",
       "port": 5101
     },
     "notifications": {
       "popup": true,
       "sound": true
     },
     "logging": {
       "level": "INFO",
       "file": "C:\\ProgramData\\yk-daemon\\yk-daemon.log"
     }
   }
   ```

3. **Start the service**:
   ```powershell
   yk-daemon --start
   # or
   sc start YubiKeyDaemonService
   ```

## Checking Logs

View the log file (check primary location first):
```powershell
# Primary location
Get-Content C:\ProgramData\yk-daemon\yk-daemon.log -Tail 50 -Wait

# If not found, check fallback location
Get-Content $env:TEMP\yk-daemon.log -Tail 50 -Wait
```

To find which location is being used:
```powershell
# Check if primary exists
Test-Path C:\ProgramData\yk-daemon\yk-daemon.log

# Check if fallback exists
Test-Path $env:TEMP\yk-daemon.log
```

## Service Management

```powershell
# Install
yk-daemon --install

# Start
yk-daemon --start

# Stop
yk-daemon --stop

# Remove
yk-daemon --remove

# Check status
sc query YubiKeyDaemonService
```

## Troubleshooting

If the service fails to start:

1. Check the log file at `C:\ProgramData\yk-daemon\yk-daemon.log`
2. Verify config.json exists and is valid JSON
3. Ensure Python and dependencies are installed correctly
4. Run in foreground mode to debug: `python -m yk_daemon.service --fg`
