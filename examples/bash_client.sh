#!/bin/bash
# Bash client for YubiKey Daemon - REST API and Socket Server examples.
#
# This script demonstrates how to interact with the YubiKey daemon from WSL
# using standard command-line tools like curl and netcat (nc).
#
# Protocol Information:
# - REST API: HTTP/JSON on port 5000 (default)
# - Socket Server: Line-based TCP on port 5001 (default)
# - Both services bind to localhost (127.0.0.1)
# - YubiKey touch required for TOTP generation
#
# Usage:
#     ./bash_client.sh [OPTIONS]
#
# Options:
#     --host HOST         API/socket host (default: 127.0.0.1)
#     --rest-port PORT    REST API port (default: 5000)
#     --socket-port PORT  Socket server port (default: 5001)
#     --account ACCOUNT   Specific account name for TOTP
#     --rest-only         Only test REST API
#     --socket-only       Only test socket server
#     --interactive       Interactive socket mode
#     --help              Show this help message
#
# Examples:
#     ./bash_client.sh                    # Test both REST API and socket
#     ./bash_client.sh --rest-only        # Test only REST API
#     ./bash_client.sh --socket-only      # Test only socket server
#     ./bash_client.sh --account GitHub   # Get TOTP for specific account
#     ./bash_client.sh --interactive      # Interactive socket session

set -euo pipefail

# Default configuration
HOST="127.0.0.1"
REST_PORT="5000"
SOCKET_PORT="5001"
ACCOUNT=""
REST_ONLY=false
SOCKET_ONLY=false
INTERACTIVE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Utility functions
print_header() {
    echo -e "\n${BLUE}$*${NC}"
    echo "$(printf '=%.0s' $(seq 1 ${#1}))"
}

print_success() {
    echo -e "${GREEN}✅ $*${NC}"
}

print_error() {
    echo -e "${RED}❌ $*${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $*${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $*${NC}"
}

# Check if required tools are available
check_dependencies() {
    local missing_tools=()

    if ! command -v curl &> /dev/null; then
        missing_tools+=("curl")
    fi

    if ! command -v nc &> /dev/null; then
        missing_tools+=("netcat (nc)")
    fi

    if ! command -v jq &> /dev/null; then
        print_warning "jq not found - JSON responses will not be formatted"
    fi

    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        echo "Please install them:"
        echo "  Ubuntu/Debian: sudo apt install curl netcat-openbsd jq"
        echo "  Alpine: apk add curl netcat-openbsd jq"
        exit 1
    fi
}

# Parse JSON response if jq is available
format_json() {
    if command -v jq &> /dev/null; then
        jq . 2>/dev/null || cat
    else
        cat
    fi
}

# REST API Functions
test_rest_health() {
    print_header "REST API - Health Check"
    local url="http://${HOST}:${REST_PORT}/health"

    if response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$url" 2>/dev/null); then
        http_code=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
        body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')

        echo "Request: GET $url"
        echo "Status Code: $http_code"
        echo "Response:"
        echo "$body" | format_json

        if [ "$http_code" -eq 200 ]; then
            print_success "Health check successful"
            return 0
        else
            print_error "Health check failed (HTTP $http_code)"
            return 1
        fi
    else
        print_error "Failed to connect to REST API at $url"
        print_info "Make sure the YubiKey Daemon REST API is running:"
        print_info "  poetry run python -m src.rest_api"
        return 1
    fi
}

test_rest_list_accounts() {
    print_header "REST API - List Accounts"
    local url="http://${HOST}:${REST_PORT}/api/accounts"

    if response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$url" 2>/dev/null); then
        http_code=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
        body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')

        echo "Request: GET $url"
        echo "Status Code: $http_code"
        echo "Response:"
        echo "$body" | format_json

        if [ "$http_code" -eq 200 ]; then
            print_success "Account listing successful"
            # Extract account count if jq is available
            if command -v jq &> /dev/null; then
                account_count=$(echo "$body" | jq -r '.accounts | length' 2>/dev/null || echo "unknown")
                print_info "Found $account_count account(s)"
            fi
            return 0
        else
            print_error "Account listing failed (HTTP $http_code)"
            return 1
        fi
    else
        print_error "Failed to connect to REST API"
        return 1
    fi
}

test_rest_get_totp() {
    local account="$1"

    if [ -n "$account" ]; then
        print_header "REST API - Get TOTP for Account: $account"
        local url="http://${HOST}:${REST_PORT}/api/totp/$account"
    else
        print_header "REST API - Get TOTP (Default Account)"
        local url="http://${HOST}:${REST_PORT}/api/totp"
    fi

    print_info "Touch your YubiKey when it blinks..."

    if response=$(curl -s -w "HTTPSTATUS:%{http_code}" --max-time 30 "$url" 2>/dev/null); then
        http_code=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
        body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')

        echo "Request: GET $url"
        echo "Status Code: $http_code"
        echo "Response:"
        echo "$body" | format_json

        if [ "$http_code" -eq 200 ]; then
            print_success "TOTP generation successful"
            # Extract TOTP code if jq is available
            if command -v jq &> /dev/null; then
                totp_code=$(echo "$body" | jq -r '.code' 2>/dev/null || echo "unknown")
                if [ "$totp_code" != "null" ] && [ "$totp_code" != "unknown" ]; then
                    print_success "TOTP Code: $totp_code"
                fi
            fi
            return 0
        else
            print_error "TOTP generation failed (HTTP $http_code)"
            return 1
        fi
    else
        print_error "Failed to connect to REST API or request timed out"
        return 1
    fi
}

# Socket Server Functions
send_socket_command() {
    local command="$1"
    local timeout="${2:-30}"

    # Fast approach: try the most likely working netcat syntax first
    local response=""
    local nc_cmd=""

    # Determine best netcat command based on what works
    # Most WSL/Linux systems use netcat-openbsd which supports -q
    if nc -q 1 -w 2 "$HOST" "$SOCKET_PORT" </dev/null >/dev/null 2>&1; then
        # OpenBSD netcat with quick quit and connection timeout
        nc_cmd="nc -q 1 -w 2"
    elif nc -w 2 "$HOST" "$SOCKET_PORT" </dev/null >/dev/null 2>&1; then
        # GNU netcat with connection timeout
        nc_cmd="nc -w 2"
    else
        # Basic netcat fallback
        nc_cmd="nc"
    fi

    # Send command with optimized timeout
    if command -v timeout >/dev/null 2>&1; then
        response=$(printf "%s\n" "$command" | timeout "$timeout" $nc_cmd "$HOST" "$SOCKET_PORT" 2>/dev/null)
    else
        response=$(printf "%s\n" "$command" | $nc_cmd "$HOST" "$SOCKET_PORT" 2>/dev/null)
    fi

    # Check result
    if [ $? -ne 0 ] || [ -z "$response" ]; then
        print_error "Failed to connect to socket server at $HOST:$SOCKET_PORT"
        print_info "Make sure the YubiKey Daemon socket server is running:"
        print_info "  poetry run python -m src.socket_server"
        print_info "Debug: Try manually testing with: echo '$command' | $nc_cmd $HOST $SOCKET_PORT"
        return 1
    fi

    echo "Command: $command"
    echo "Response: $response"

    if [[ "$response" == OK* ]]; then
        data="${response#OK }"
        print_success "Command successful"
        [ -n "$data" ] && print_info "Data: $data"
        return 0
    elif [[ "$response" == ERROR* ]]; then
        error_msg="${response#ERROR }"
        print_error "Command failed: $error_msg"
        return 1
    else
        print_error "Invalid response format: $response"
        print_info "Raw response: '$response'"
        return 1
    fi
}

test_socket_list_accounts() {
    print_header "Socket Server - List Accounts"
    send_socket_command "LIST_ACCOUNTS" 10
}

test_socket_get_totp() {
    local account="$1"

    if [ -n "$account" ]; then
        print_header "Socket Server - Get TOTP for Account: $account"
        print_info "Touch your YubiKey when it blinks..."
        send_socket_command "GET_TOTP $account" 30
    else
        print_header "Socket Server - Get TOTP (Default Account)"
        print_info "Touch your YubiKey when it blinks..."
        send_socket_command "GET_TOTP" 30
    fi
}

# Interactive socket mode
interactive_socket_mode() {
    print_header "Socket Server - Interactive Mode"
    print_info "Server: $HOST:$SOCKET_PORT"
    print_info "Commands: LIST_ACCOUNTS, GET_TOTP [account], or Ctrl+C to exit"
    echo

    while true; do
        echo -n "> "
        read -r user_input

        if [ -z "$user_input" ]; then
            continue
        fi

        echo "Sending: $user_input"
        if ! send_socket_command "$user_input" 30; then
            print_warning "Command failed, but continuing..."
        fi
        echo
    done
}

# Main test functions
test_rest_api() {
    print_header "Testing REST API"
    echo "API URL: http://$HOST:$REST_PORT"
    echo

    local failed=0

    # Health check
    if ! test_rest_health; then
        ((failed++))
    fi

    echo

    # List accounts
    if ! test_rest_list_accounts; then
        ((failed++))
    fi

    echo

    # Only get TOTP if a specific account was requested
    if [ -n "$ACCOUNT" ]; then
        # Get TOTP for specific account
        if ! test_rest_get_totp "$ACCOUNT"; then
            ((failed++))
        fi
        echo
    else
        print_info "Skipping TOTP test (no --account specified)"
        print_info "To test TOTP generation, use: --account <account_name>"
        echo
    fi

    if [ $failed -eq 0 ]; then
        print_success "All REST API tests passed!"
    else
        print_error "$failed REST API test(s) failed"
    fi

    return $failed
}

test_socket_server() {
    print_header "Testing Socket Server"
    echo "Socket: $HOST:$SOCKET_PORT"
    echo

    local failed=0

    # List accounts
    if ! test_socket_list_accounts; then
        ((failed++))
    fi

    echo

    # Only get TOTP if a specific account was requested
    if [ -n "$ACCOUNT" ]; then
        # Get TOTP for specific account
        if ! test_socket_get_totp "$ACCOUNT"; then
            ((failed++))
        fi
        echo
    else
        print_info "Skipping TOTP test (no --account specified)"
        print_info "To test TOTP generation, use: --account <account_name>"
        echo
    fi

    if [ $failed -eq 0 ]; then
        print_success "All socket server tests passed!"
    else
        print_error "$failed socket server test(s) failed"
    fi

    return $failed
}

# Help function
show_help() {
    echo "Bash client for YubiKey Daemon - REST API and Socket Server examples"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --host HOST         API/socket host (default: 127.0.0.1)"
    echo "  --rest-port PORT    REST API port (default: 5000)"
    echo "  --socket-port PORT  Socket server port (default: 5001)"
    echo "  --account ACCOUNT   Specific account name for TOTP (optional)"
    echo "  --rest-only         Only test REST API"
    echo "  --socket-only       Only test socket server"
    echo "  --interactive       Interactive socket mode"
    echo "  --help              Show this help message"
    echo
    echo "Examples:"
    echo "  $0                           # Test connectivity only (no TOTP)"
    echo "  $0 --rest-only               # Test only REST API connectivity"
    echo "  $0 --socket-only             # Test only socket server connectivity"
    echo "  $0 --account GitHub          # Test connectivity AND get TOTP for GitHub"
    echo "  $0 --interactive             # Interactive socket session"
    echo "  $0 --host 172.25.144.1       # Use custom host (e.g., for WSL)"
    echo
    echo "Note:"
    echo "  TOTP generation only occurs when --account is specified to avoid"
    echo "  unwanted YubiKey touch prompts and notification sounds."
    echo
    echo "Prerequisites:"
    echo "  - YubiKey connected and configured with OATH accounts"
    echo "  - YubiKey Daemon services running (REST API and/or Socket Server)"
    echo "  - Required tools: curl, netcat (nc), jq (optional for JSON formatting)"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --rest-port)
            REST_PORT="$2"
            shift 2
            ;;
        --socket-port)
            SOCKET_PORT="$2"
            shift 2
            ;;
        --account)
            ACCOUNT="$2"
            shift 2
            ;;
        --rest-only)
            REST_ONLY=true
            shift
            ;;
        --socket-only)
            SOCKET_ONLY=true
            shift
            ;;
        --interactive)
            INTERACTIVE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate conflicting options
if [ "$REST_ONLY" = true ] && [ "$SOCKET_ONLY" = true ]; then
    print_error "Cannot use --rest-only and --socket-only together"
    exit 1
fi

if [ "$INTERACTIVE" = true ] && [ "$REST_ONLY" = true ]; then
    print_error "Cannot use --interactive with --rest-only"
    exit 1
fi

# Main execution
main() {
    print_header "YubiKey Daemon - Bash Client Examples"
    echo "Host: $HOST"
    echo "REST API Port: $REST_PORT"
    echo "Socket Port: $SOCKET_PORT"
    [ -n "$ACCOUNT" ] && echo "Target Account: $ACCOUNT"
    echo

    # Check dependencies
    check_dependencies

    # Handle interactive mode
    if [ "$INTERACTIVE" = true ]; then
        interactive_socket_mode
        return
    fi

    local total_failed=0

    # Run tests based on options
    if [ "$SOCKET_ONLY" = false ]; then
        if ! test_rest_api; then
            ((total_failed++))
        fi
    fi

    if [ "$REST_ONLY" = false ]; then
        if ! test_socket_server; then
            ((total_failed++))
        fi
    fi

    echo
    print_header "Summary"
    if [ $total_failed -eq 0 ]; then
        print_success "All tests completed successfully!"
        print_info "The YubiKey daemon is working correctly from WSL"
    else
        print_error "Some tests failed"
        print_info "Check that:"
        print_info "  1. YubiKey is connected and has OATH accounts configured"
        print_info "  2. YubiKey Daemon services are running"
        print_info "  3. Firewall allows localhost connections on specified ports"
        exit 1
    fi
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
