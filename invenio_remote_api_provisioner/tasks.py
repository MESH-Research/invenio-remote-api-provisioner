#
# This file is part of the invenio-remote-api-provisioner package.
# Copyright (C) 2024, MESH Research.
#
# invenio-remote-api-provisioner is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see
# LICENSE file for more details.

"""Celery task to send record event notices to remote API."""

import logging
import logging.handlers
import os
from collections.abc import Callable
from pathlib import Path

import requests

# from celery import current_app as current_celery_app
from celery import shared_task
from celery.utils.log import get_task_logger
from flask import Response
from flask import current_app as app
from flask_principal import Identity
from invenio_access.permissions import system_identity
from invenio_access.utils import get_identity
from invenio_accounts import current_accounts
from invenio_queues import current_queues
from invenio_rdm_records.records.api import RDMDraft, RDMRecord

from .signals import remote_api_provisioning_triggered
from .utils import get_user_idp_info

task_logger = get_task_logger(__name__)

task_logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s:RemoteAPIProvisioner:%(levelname)s: %(message)s"
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
    payload: dict | Callable,
    record: dict = {},
    data: dict = {},
    with_record_owner: bool = False,
    **kwargs,
) -> dict:
    """Get the payload object for the notification.

    Parameters:
        identity (str): The identity of the user performing
                            the service operation.
        record (dict): The record returned from the service method.
        data (dict): The data returned from the service method.
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
            # Add user profile data if available
            if hasattr(user, 'user_profile') and user.user_profile:
                owner.update(user.user_profile)
            # Add IDP info
            owner.update(get_user_idp_info(user))

    if callable(payload):
        payload_object = payload(
            identity, record=record, owner=owner, data=data, **kwargs
        )
    elif isinstance(payload, dict):
        payload_object = payload
    else:
        raise ValueError(
            "Event payload must be a dict or a callable that returns a" " dict."
        )
    
    if payload_object and "internal_error" in payload_object.keys():
        raise RuntimeError(payload_object["internal_error"])
    elif not payload_object:
        raise RuntimeError("Payload object is empty")
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
        http_method: str = event_config["http_method"](
            identity, record=record, draft=draft, **kwargs
        )
    else:
        http_method: str = event_config["http_method"]
    return http_method


def get_headers(event_config: dict) -> dict:
    headers: dict = event_config.get("headers", {})
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
        # task_logger.debug("Request URL: %s", request_url)
    else:
        request_url = endpoint
    return request_url


# TODO: Make retries configurable
@shared_task(
    bind=False,
    ignore_result=True,
    retry_for=(RuntimeError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def send_remote_api_update(
    identity_id: str = "",
    record: dict = {},
    is_published: bool = False,
    is_draft: bool = False,
    is_deleted: bool = False,
    parent: dict | None = None,
    latest_version_index: int | None = None,
    latest_version_id: str | None = None,
    current_version_index: int | None = None,
    draft: dict | None = None,
    endpoint: str = "",
    service_type: str = "",
    service_method: str = "",
    data: dict = {},
    **kwargs,
) -> tuple[Response, dict | str | int | list | None]:
    """Send a record event update to a remote API.

    Parameters:
        identity_id (str): The ID of the user performing
                            the service operation.
        record (RDMRecord): The record to be updated, dumped to a
                            dictionary.
        is_published (bool): Whether the record is published. This is
                            retrieved from the record object before it
                            is serialized for this celery task, since
                            the property is not part of the record's
                            serialization.
        draft (RDMDraft): The draft to be updated.
        endpoint (str): The endpoint to send the request to.
        service_type (str): The type of service whose method triggers
                            this task. (One of "rdm_record" or "community".)
        service_method (str): The name of the service method that triggers
                            this task.
        **kwargs: Any additional keyword arguments passed through
                    from the parent service method.

    Note: We add the following parameter values to the record dictionary
    when it is passed on to other functions by this task. These are
    properties of the record object that are not part of the record's
    serialization received by this task (via celery):
        - is_published
        - is_draft
        - is_deleted
        - parent
        - latest_version_index
        - latest_version_id
        - current_version_index

    Returns:
        tuple[Response, Union[dict, str, int, list, None]]: The response from
        the remote API and the result of the callback function (if any).
    """
    record["is_published"] = is_published
    record["is_draft"] = is_draft
    record["is_deleted"] = is_deleted
    record["parent"] = parent
    record["latest_version_index"] = latest_version_index
    record["latest_version_id"] = latest_version_id
    record["current_version_index"] = current_version_index

    # with app.app_context():

    if identity_id != "system":
        user_object = current_accounts.datastore.get_user_by_id(identity_id)
        identity = get_identity(user_object)
    else:
        identity = system_identity

    event_config = (
        app.config.get("REMOTE_API_PROVISIONER_EVENTS", {})
        .get(service_type, {})
        .get(endpoint, {})
        .get(service_method, {})
    )
    # task_logger.warning(f"Event config: {event_config}")
    # task_logger.warning(f"Service type: {service_type}")
    # task_logger.warning(f"Endpoint: {endpoint}")
    # task_logger.warning(f"Service method: {service_method}")
    # task_logger.warning(f"Identity: {identity_id}")
    # task_logger.warning(f"Record: {type(record)}")
    # task_logger.warning(f"Draft: {type(draft)}")

    payload_object = None
    if event_config.get("payload"):
        try:
            payload_object = get_payload_object(
                identity,
                event_config["payload"],
                record=record,
                draft=draft,
                data=data,
                with_record_owner=event_config.get("with_record_owner", False),
                **kwargs,
            )
            # current_app.logger.debug("Payload object:")
            # current_app.logger.debug(pformat(payload_object))
        except (RuntimeError, ValueError) as e:
            task_logger.error(
                f"Could not send "
                f"{service_type} {service_method} "
                f"update for record {record.get('id') or data.get('slug')}: "
                "Problem assembling "
                f"update payload: {e}"
            )

    request_url = get_request_url(
        identity, endpoint, record, draft, event_config, **kwargs
    )
    http_method = get_http_method(identity, record, draft, event_config, **kwargs)
    request_headers = get_headers(event_config)

    # task_logger.warning("Sending remote api update ************")
    # task_logger.info("payload:")
    # task_logger.info(pformat(payload_object))
    # task_logger.info(f"request_url: {request_url}")
    # task_logger.info(f"http_method: {http_method}")
    # task_logger.info(f"request_headers: {request_headers}")
    # task_logger.info(f"record_id: {record['id']}")
    # task_logger.info(f"draft_id: {draft.get('id')}")

    response = requests.request(
        http_method,
        url=request_url,
        json=payload_object,
        allow_redirects=False,
        timeout=10,
        headers=request_headers,
    )
    print(response)
    if response.status_code != 200:  # FIXME: Always 200?
        task_logger.error(
            "Error sending notification (status code" f" {response.status_code})"
        )
        task_logger.error(response.text)
        raise RuntimeError(
            f"Error sending notification (status code " f"{response.status_code})"
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
    callback_result = None
    if callback:
        callback_record = record
        callback_draft = draft
        callback_data = data
        for k in [
            "is_published",
            "is_draft",
            "is_deleted",
            "parent",
            "latest_version_index",
            "latest_version_id",
            "current_version_index",
        ]:
            if callback_record and k in callback_record.keys():
                del callback_record[k]
            if callback_draft and k in callback_draft.keys():
                del callback_draft[k]
            if callback_data and k in callback_data.keys():
                del callback_data[k]

        task_logger.info("Calling callback")

        messages_content = [
            {
                "response_json": response_string,
                "service_type": service_type,
                "service_method": service_method,
                "request_url": request_url,
                "payload_object": payload_object,
                "record": callback_record,
                "draft": callback_draft,
                "data": callback_data,
                **kwargs,
            }
        ]

        # Publish the message to the event queue.
        current_queues.queues["remote-api-provisioning-events"].publish(
            messages_content
        )
        # Send the signal so that Invenio knows to consume the message
        remote_api_provisioning_triggered.send(app._get_current_object())

        # callback_result = callback.delay(
        #     response_json=response_string,
        #     service_type=service_type,
        #     service_method=service_method,
        #     request_url=request_url,
        #     payload_object=payload_object,
        #     record=callback_record,
        #     draft=callback_draft,
        #     **kwargs,
        # )

    return response.text, callback_result
