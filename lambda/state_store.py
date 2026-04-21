"""SSM Parameter Store state management for last-seen RSS entry GUIDs."""
import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_PREFIX = "/notifier/state"


def _param_path(feed_url: str) -> str:
    """Derive the SSM parameter path for a given feed URL.

    Path format: {SSM_STATE_PATH_PREFIX}/{md5_hex_of_feed_url}
    """
    prefix = os.environ.get("SSM_STATE_PATH_PREFIX", _DEFAULT_PREFIX)
    url_hash = hashlib.md5(feed_url.encode()).hexdigest()
    return f"{prefix}/{url_hash}"


def read_last_seen(feed_url: str, ssm_client) -> Optional[str]:
    """Return the stored GUID for *feed_url*, or None if no state exists yet.

    Raises any SSM exception other than ParameterNotFound so that callers
    are aware of unexpected failures (Requirement 2.1, 4.3).
    """
    path = _param_path(feed_url)
    try:
        response = ssm_client.get_parameter(Name=path)
        value: str = response["Parameter"]["Value"]
        logger.debug("Read last-seen GUID from SSM", extra={"path": path, "guid": value})
        return value
    except ssm_client.exceptions.ParameterNotFound:
        logger.info("No existing state for feed (bootstrap)", extra={"path": path})
        return None


def write_last_seen(feed_url: str, guid: str, ssm_client) -> None:
    """Persist *guid* as the last-seen entry identifier for *feed_url*.

    Uses PutParameter with Overwrite=True so subsequent writes update the
    existing parameter rather than raising an error (Requirement 2.3).
    """
    path = _param_path(feed_url)
    ssm_client.put_parameter(
        Name=path,
        Value=guid,
        Type="String",
        Overwrite=True,
    )
    logger.debug("Wrote last-seen GUID to SSM", extra={"path": path, "guid": guid})
