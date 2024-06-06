import logging

from flask import request, current_app as app

from app.config import IMAGE_MODEL_NAMES
from app.config import configure_logging
from app.utils import handle_error, fetch, generate_model_data, upload_file

configure_logging()


@app.route("/v1/chat/completions", methods=["GET", "POST", "OPTIONS"])
def onRequest():
    try:
        return fetch(request)
    except Exception as e:
        logging.error("An error occurred with chat : %s", e)
        return handle_error(e)


@app.route('/v1/models')
def list_models():
    return generate_model_data()


@app.route('/v1/images/generations', methods=["post"])
def image():
    try:
        request.get_json()["model"] = IMAGE_MODEL_NAMES[0]
        return fetch(request)
    except Exception as e:
        logging.error("An error occurred with image : %s", e)
        return handle_error(e)
