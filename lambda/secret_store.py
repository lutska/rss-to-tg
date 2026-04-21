"""SSM Parameter Store loader for Telegram bot credentials (SecureString)."""
import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_BOT_TOKEN_PATH = "/notifier/telegram/bot_token"
_DEFAULT_CHAT_ID_PATH = "/notifier/telegram/chat_id"


def load_secrets(ssm_client) -> dict:
    """Read bot_token and chat_id from SSM SecureString parameters.

    Parameter paths are read from environment variables:
      - SSM_BOT_TOKEN_PATH  (default: /notifier/telegram/bot_token)
      - SSM_CHAT_ID_PATH    (default: /notifier/telegram/chat_id)

    Raises immediately if either parameter is missing or the SSM call fails
    (Requirement 4.3) — exceptions are never swallowed.

    Returns:
        dict with keys 'bot_token' and 'chat_id'.
    """
    bot_token_path = os.environ.get("SSM_BOT_TOKEN_PATH", _DEFAULT_BOT_TOKEN_PATH)
    chat_id_path = os.environ.get("SSM_CHAT_ID_PATH", _DEFAULT_CHAT_ID_PATH)

    logger.debug("Loading secrets from SSM", extra={"bot_token_path": bot_token_path, "chat_id_path": chat_id_path})

    bot_token = _get_secure_parameter(ssm_client, bot_token_path)
    chat_id = _get_secure_parameter(ssm_client, chat_id_path)

    logger.info("Secrets loaded successfully from SSM")
    return {"bot_token": bot_token, "chat_id": chat_id}


def _get_secure_parameter(ssm_client, path: str) -> str:
    """Fetch a single SecureString parameter value from SSM.

    Raises on any error (missing parameter, permission denied, etc.).
    """
    try:
        response = ssm_client.get_parameter(Name=path, WithDecryption=True)
        value: str = response["Parameter"]["Value"]
        if not value:
            raise ValueError(f"SSM parameter '{path}' exists but has an empty value")
        logger.debug("Fetched SSM parameter", extra={"path": path})
        return value
    except Exception:
        logger.error("Failed to load secret from SSM", extra={"path": path}, exc_info=True)
        raise
