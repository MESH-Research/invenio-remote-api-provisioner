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
from flask_principal import Identity
from invenio_access.permissions import system_identity
from invenio_access.utils import get_identity
from invenio_accounts import current_accounts
from invenio_rdm_records.records.api import RDMRecord, RDMDraft
import logging
import os
from pathlib import Path
from pprint import pformat
import requests
from typing import Optional, Union
from .utils import get_user_idp_info

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


def get_payload_object(
    identity: Identity,
    payload: Union[dict, callable],
    record: Optional[RDMRecord] = None,
    with_record_owner: bool = False,
    **kwargs,
) -> dict:
    """Get the payload object for the notification.

    Parameters:
        identity (str): The identity of the user performing
                            the service operation.
        record (dict): The record returned from the service method.
        payload (dict or callable): The payload object or a callable
                                    that returns the payload object.
        with_record_owner (bool): Include the record owner in the
                                    payload object. Requires an extra
                                    database query to get the user. If
                                    true then the payload callable
                                    receives the record owner as a
                                    keyword argument.
        **kwargs: Any additional keyword arguments passed through
                    from the parent service method. This includes
                    ``errors`` where there are operation problems.
                    See this extension's README for the service
                    method details.
    """
    owner = None
    if with_record_owner:
        if identity.id == "system":
            owner = {
                "id": "system",
                "email": "",
                "username": "system",
            }
        else:
            user = current_accounts.datastore.get_user_by_id(identity.id)
            owner = {
                "id": identity.id,
                "email": user.email,
                "username": user.username,
            }
            owner.update(user.user_profile)
            owner.update(get_user_idp_info(user))

    if callable(payload):
        payload_object = payload(
            identity, record=record, owner=owner, **kwargs
        )
    elif isinstance(payload, dict):
        payload_object = payload
    else:
        raise ValueError(
            "Event payload must be a dict or a callable that returns a"
            " dict."
        )
    if "internal_error" in payload_object.keys():
        raise RuntimeError(payload_object["internal_error"])
    else:
        return payload_object


def get_http_method(
    identity: Identity,
    record: RDMRecord,
    draft: RDMDraft,
    event_config: dict,
    **kwargs,
) -> str:

    if callable(event_config["http_method"]):
        http_method = event_config["http_method"](
            identity, record=record, draft=draft, **kwargs
        )
    else:
        http_method = event_config["http_method"]
    return http_method


def get_headers(event_config: dict) -> dict:
    headers = event_config.get("headers", {})
    if event_config.get("auth_token"):
        headers["Authorization"] = f"Bearer {event_config['auth_token']}"
    return headers


def get_request_url(
    identity: Identity,
    endpoint: str,
    record: RDMRecord,
    draft: RDMDraft,
    event_config: dict,
    **kwargs,
) -> str:
    if event_config.get("url_factory"):
        request_url = event_config["url_factory"](
            identity, record=record, draft=draft, **kwargs
        )
        task_logger.debug("Request URL: %s", request_url)
    else:
        request_url = endpoint
    return request_url


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
    identity_id: str = "",
    record: Optional[RDMRecord] = None,
    draft: Optional[RDMDraft] = None,
    endpoint: str = "",
    service_type: str = "",
    service_method: str = "",
    **kwargs,
) -> Response:
    """Send a record event update to a remote API."""

    with app.app_context():

        if identity_id != "system":
            user_object = current_accounts.datastore.get_user_by_id(
                identity_id
            )
            identity = get_identity(user_object)
        else:
            identity = system_identity

        event_config = (
            app.config.get("REMOTE_API_PROVISIONER_EVENTS", {})
            .get(service_type, {})
            .get(endpoint, {})
            .get(service_method, {})
        )
        app.logger.warning(f"Event config: {event_config}")
        app.logger.warning(f"Service type: {service_type}")
        app.logger.warning(f"Endpoint: {endpoint}")
        app.logger.warning(f"Service method: {service_method}")
        app.logger.warning(f"Identity: {identity_id}")
        app.logger.warning(f"Record: {type(record)}")
        app.logger.warning(f"Draft: {type(draft)}")

        payload_object = None
        if event_config.get("payload"):
            try:
                payload_object = get_payload_object(
                    identity,
                    event_config["payload"],
                    record=record,
                    draft=draft,
                    with_record_owner=event_config.get(
                        "with_record_owner", False
                    ),
                    **kwargs,
                )
                # current_app.logger.debug("Payload object:")
                # current_app.logger.debug(pformat(payload_object))
            except (RuntimeError, ValueError) as e:
                task_logger.error(
                    f"Could not send "
                    f"{service_type} {service_method} "
                    f"update for record {record.id}: Problem assembling "
                    f"update payload: {e}"
                )

        request_url = get_request_url(
            identity, endpoint, record, draft, event_config, **kwargs
        )
        http_method = get_http_method(
            identity, record, draft, event_config, **kwargs
        )
        request_headers = get_headers(event_config)

        task_logger.debug("Sending remote api update ************")
        task_logger.info("payload:")
        task_logger.info(pformat(payload_object))
        task_logger.info(f"request_url: {request_url}")
        task_logger.info(f"http_method: {http_method}")
        task_logger.info(f"request_headers: {request_headers}")
        task_logger.info(f"record_id: {record.id}")
        task_logger.info(f"draft_id: {draft.get('id')}")

        response = requests.request(
            http_method,
            url=request_url,
            json=payload_object,
            allow_redirects=False,
            timeout=10,
            headers=request_headers,
        )
        print(response)
        if response.status_code != 200:
            task_logger.error(
                "Error sending notification (status code"
                f" {response.status_code})"
            )
            task_logger.error(response.text)
            raise RuntimeError(
                f"Error sending notification (status code "
                f"{response.status_code})"
            )
        else:
            task_logger.info("Notification sent successfully")
            task_logger.info("response:")
            task_logger.info(response.json())
            task_logger.info("-----------------------")

        try:
            response_string = response.json()
        except ValueError as e:
            task_logger.error(f"Error decoding response: {e}")
            response_string = response.text

        callback = event_config.get("callback")
        if callback:
            task_logger.info("Calling callback")
            callback(
                response_json=response_string,
                service_type=service_type,
                service_method=service_method,
                request_url=request_url,
                payload_object=payload_object,
                record_id=record.id,
                draft_id=draft.get("id"),
                **kwargs,
            )

        return response_string
