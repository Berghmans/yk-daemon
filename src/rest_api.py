"""Flask-based REST API server for YubiKey OATH-TOTP operations.

This module provides a REST API interface for generating TOTP codes and
managing OATH accounts on a YubiKey device.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from flask import Flask, jsonify

from src.config import Config, RestApiConfig
from src.notifications import Notifier, create_notifier_from_config
from src.yubikey import (
    AccountNotFoundError,
    DeviceNotFoundError,
    DeviceRemovedError,
    TouchTimeoutError,
    YubiKeyInterface,
)

logger = logging.getLogger(__name__)


def create_app(config: RestApiConfig, yubikey: YubiKeyInterface | None = None) -> Flask:
    """Create and configure Flask application.

    Args:
        config: REST API configuration
        yubikey: YubiKey interface (creates new instance if None)

    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    app.config["YUBIKEY"] = yubikey or YubiKeyInterface()

    @app.before_request
    def log_request() -> None:
        """Log incoming requests."""
        from flask import request

        logger.info(f"{request.method} {request.path} from {request.remote_addr}")

    @app.after_request
    def log_response(response: Any) -> Any:
        """Log outgoing responses."""
        from flask import request

        logger.info(
            f"{request.method} {request.path} -> {response.status_code} "
            f"({response.content_length} bytes)"
        )
        return response

    @app.route("/health", methods=["GET"])
    def health() -> tuple[Any, int]:
        """Health check endpoint with YubiKey status.

        Returns:
            JSON response with health status and YubiKey connection status
        """
        yubikey_interface: YubiKeyInterface = app.config["YUBIKEY"]
        status = yubikey_interface.get_status()

        response = {
            "success": True,
            "status": "healthy",
            "yubikey_status": status.value,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.debug(f"Health check: {response}")
        return jsonify(response), 200

    @app.route("/api/accounts", methods=["GET"])
    def list_accounts() -> tuple[Any, int]:
        """List all OATH accounts on the YubiKey.

        Returns:
            JSON response with list of account names
        """
        yubikey_interface: YubiKeyInterface = app.config["YUBIKEY"]

        try:
            accounts = yubikey_interface.list_accounts()
            response = {
                "success": True,
                "accounts": accounts,
                "count": len(accounts),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            logger.info(f"Listed {len(accounts)} accounts")
            return jsonify(response), 200

        except DeviceNotFoundError as e:
            logger.warning(f"Device not found: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "YubiKey not connected",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                503,
            )

        except DeviceRemovedError as e:
            logger.error(f"Device removed during operation: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "YubiKey disconnected during operation",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                503,
            )

        except Exception as e:
            logger.error(f"Internal error listing accounts: {e}", exc_info=True)
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Internal server error",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                500,
            )

    @app.route("/api/totp", methods=["GET"])
    def get_default_totp() -> tuple[Any, int]:
        """Get TOTP code for the default (first) account.

        Returns:
            JSON response with TOTP code for the first account
        """
        yubikey_interface: YubiKeyInterface = app.config["YUBIKEY"]

        try:
            # List accounts to get the first one
            accounts = yubikey_interface.list_accounts()

            if not accounts:
                logger.warning("No accounts found on YubiKey")
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "No accounts found",
                            "message": "No OATH accounts found on YubiKey",
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    ),
                    404,
                )

            # Get TOTP for first account
            default_account = accounts[0]
            code = yubikey_interface.generate_totp(default_account)

            response = {
                "success": True,
                "account": default_account,
                "code": code,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            logger.info(f"Generated TOTP for default account: {default_account}")
            return jsonify(response), 200

        except DeviceNotFoundError as e:
            logger.warning(f"Device not found: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "YubiKey not connected",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                503,
            )

        except TouchTimeoutError as e:
            logger.warning(f"Touch timeout: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Touch timeout",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                408,
            )

        except DeviceRemovedError as e:
            logger.error(f"Device removed during operation: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "YubiKey disconnected during operation",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                503,
            )

        except Exception as e:
            logger.error(f"Internal error generating TOTP: {e}", exc_info=True)
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Internal server error",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                500,
            )

    @app.route("/api/totp/<path:account>", methods=["GET"])
    def get_totp_for_account(account: str) -> tuple[Any, int]:
        """Get TOTP code for a specific account.

        Args:
            account: Account name/identifier

        Returns:
            JSON response with TOTP code for the specified account
        """
        yubikey_interface: YubiKeyInterface = app.config["YUBIKEY"]

        try:
            code = yubikey_interface.generate_totp(account)

            if not code:
                logger.warning(f"Empty code returned for account: {account}")
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Failed to generate code",
                            "message": "Empty TOTP code returned",
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    ),
                    500,
                )

            response = {
                "success": True,
                "account": account,
                "code": code,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            logger.info(f"Generated TOTP for account: {account}")
            return jsonify(response), 200

        except AccountNotFoundError as e:
            logger.warning(f"Account not found: {account}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Account not found",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                404,
            )

        except DeviceNotFoundError as e:
            logger.warning(f"Device not found: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "YubiKey not connected",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                503,
            )

        except TouchTimeoutError as e:
            logger.warning(f"Touch timeout: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Touch timeout",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                408,
            )

        except DeviceRemovedError as e:
            logger.error(f"Device removed during operation: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "YubiKey disconnected during operation",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                503,
            )

        except Exception as e:
            logger.error(f"Internal error generating TOTP: {e}", exc_info=True)
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Internal server error",
                        "message": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                500,
            )

    return app


def run_server(
    config: RestApiConfig,
    yubikey: YubiKeyInterface | None = None,
    full_config: Config | None = None,
) -> None:
    """Run the Flask REST API server.

    Args:
        config: REST API configuration
        yubikey: YubiKey interface (creates new instance if None)
        full_config: Full daemon configuration for creating notifier (optional)
    """
    # Create notifier from config if provided
    notifier: Notifier | None = None
    if full_config and yubikey is None:
        notifier = create_notifier_from_config(full_config.notifications)
        yubikey = YubiKeyInterface(notifier=notifier)

    app = create_app(config, yubikey)

    logger.info(f"Starting REST API server on {config.host}:{config.port}")

    # Run with debug=False for production
    app.run(host=config.host, port=config.port, debug=False, threaded=True)
