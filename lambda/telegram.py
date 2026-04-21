"""Telegram Bot API client for sending formatted RSS entry notifications."""
import logging
import time

from models import FeedEntry

logger = logging.getLogger(__name__)

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_RETRY_DELAYS = [1, 2, 4]  # sleep durations before each retry attempt


def format_message(entry: FeedEntry) -> str:
    """Format a FeedEntry as a Telegram HTML message string."""
    return f"📢 {entry.title}\n\n{entry.link}"


def send_message(token: str, chat_id: str, text: str, session) -> None:
    """Send a message via the Telegram Bot API.

    Makes 1 initial attempt plus up to 3 retries (4 total) with exponential
    backoff (1s, 2s, 4s before each retry) on non-200 responses. Logs each
    retry at WARNING level and the final failure at ERROR level. Does NOT
    raise an exception after all retries are exhausted.

    Args:
        token:    Telegram bot token.
        chat_id:  Target chat/channel ID.
        text:     Message text (HTML formatted).
        session:  A requests.Session instance used for the HTTP POST.
    """
    url = _TELEGRAM_API_URL.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    response = session.post(url, json=payload)
    if response.status_code == 200:
        return

    for retry_num, delay in enumerate(_RETRY_DELAYS, start=1):
        logger.warning(
            "Telegram sendMessage retry %d/%d after status=%d; sleeping %ds",
            retry_num,
            len(_RETRY_DELAYS),
            response.status_code,
            delay,
        )
        time.sleep(delay)
        response = session.post(url, json=payload)
        if response.status_code == 200:
            return

    logger.error(
        "Telegram sendMessage failed after %d retries: status=%d body=%s",
        len(_RETRY_DELAYS),
        response.status_code,
        response.text,
    )
