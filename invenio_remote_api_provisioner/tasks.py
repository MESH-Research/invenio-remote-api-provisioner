# -*- coding: utf-8 -*-
#
# This file is part of the invenio-remote-api-provisioner package.
# Copyright (C) 2024, MESH Research.
#
# invenio-remote-api-provisioner is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see
# LICENSE file for more details.

"""Celery task to send record event notices to remote API."""

# from celery import current_app as current_celery_app
from celery import shared_task
from celery.utils.log import get_task_logger
from flask import Response, current_app as app
from invenio_queues import current_queues
import logging
import os
from pathlib import Path
from pprint import pformat
import requests

task_logger = get_task_logger(__name__)

task_logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s:RemoteUserDataService:%(levelname)s: %(message)s"
)
log_folder = Path(__file__).parent / "logs"
os.makedirs(log_folder, exist_ok=True)
file_handler = logging.handlers.RotatingFileHandler(
    log_folder / "celery.log",
    mode="a",
    maxBytes=1000000,
    backupCount=5,
)
file_handler.setFormatter(formatter)
if task_logger.hasHandlers():
    task_logger.handlers.clear()
task_logger.addHandler(file_handler)


# TODO: Make retries configurable
@shared_task(
    bind=True,
    ignore_result=False,
    retry_for=(RuntimeError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def send_remote_api_update(
    self,
    service_type: str = "",
    service_method: str = "",
    request_headers: dict = {},
    request_url: str = "",
    http_method: str = "",
    payload_object: dict = {},
    record_id: str = "",
    draft_id: str = "",
    **kwargs,
) -> Response:
    """Send a record event update to a remote API."""

    with app.app_context():
        app.logger.debug("Sending remote api update ************")
        app.logger.info("payload:")
        app.logger.info(pformat(payload_object))

        response = requests.request(
            http_method,
            url=request_url,
            json=payload_object,
            allow_redirects=False,
            timeout=10,
            headers=request_headers,
        )
        if response.status_code != 200:
            app.logger.error(
                "Error sending notification (status code"
                f" {response.status_code})"
            )
            app.logger.error(response.text)
            raise RuntimeError(
                f"Error sending notification (status code "
                f"{response.status_code})"
            )
        else:
            app.logger.info("Notification sent successfully")
            app.logger.info("response:")
            app.logger.info(response.json())
            app.logger.info("-----------------------")

        try:
            response_string = response.json()
        except ValueError as e:
            app.logger.error(f"Error decoding response: {e}")
            response_string = response.text

        return response_string
