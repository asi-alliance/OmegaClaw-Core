"""Where the plugin's outbound API calls should go.

The container entrypoint scrubs every API key out of the agent's environment and
starts a local proxy that holds them instead, so code running inside has no key
to read. Calls go to the proxy, which injects the real credential on the way
out. Run outside that setup - a test, a bare checkout - and the keys are in the
environment as usual.

Each upstream has a route on the proxy, so picking a destination is a matter of
naming the route:

    base_url, api_key = upstream("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY")
"""

import logging
import os

logger = logging.getLogger(__name__)

# The proxy answers with a real credential, so the client only needs a
# non-empty placeholder to satisfy its own argument checking.
PROXY_KEY = "proxy"


def gateway_url():
    """The proxy's base URL, or "" when calls should go direct."""
    try:
        from config import config_get_by_key
        url = config_get_by_key("GATEWAY_URL", "") or ""
    except ModuleNotFoundError:
        # No core on the path: honour the environment so the plugin stays
        # usable on its own.
        url = os.environ.get("GATEWAY_URL", "")
    return str(url).rstrip("/")


def upstream(route, direct_base_url, key_env):
    """Resolve one upstream to the (base_url, api_key) a client should use.

    `route` is the proxy path for this service, without slashes.
    Returns an api_key of None when going direct and the variable is unset, so
    the caller can report which key is missing rather than failing obscurely.
    """
    proxy = gateway_url()
    if proxy:
        logger.info("Routing %s through the gateway proxy", route)
        return f"{proxy}/{route}/", PROXY_KEY
    return direct_base_url, os.environ.get(key_env)
