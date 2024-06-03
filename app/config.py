import os
import logging


IGNORED_MODEL_NAMES = ["gpt-4", "gpt-3.5", "websearch", "dall-e-3", "gpt-4o"]
IMAGE_MODEL_NAMES = ["dalle3", "dalle-3", "dall-e-3"]
AUTH_TOKEN = os.getenv("AUTHORIZATION")
HISTORY_MSG_LIMIT = os.getenv("HISTORY_MSG_LIMIT", 0)
HTTP_PROXY = os.getenv("HTTP_PROXY")
HTTPS_PROXY = os.getenv("HTTPS_PROXY")
# SOCKS5_PROXY_URL = os.getenv("HTTP_PROXY_URL", "no_proxy")


def configure_logging():
    extended_log_format = (
        '%(asctime)s | %(levelname)s | %(name)s | '
        '%(process)d | %(filename)s:%(lineno)d | %(funcName)s | %(message)s'
    )
    logging.basicConfig(level=logging.DEBUG, format=extended_log_format)