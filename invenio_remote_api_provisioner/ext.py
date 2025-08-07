# -*- coding: utf-8 -*-
#
# This file is part of the invenio-remote-api-provisioner package.
# Copyright (C) 2024, Mesh Research.
#
# invenio-remote-api-provisioner is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see
# LICENSE file for more details.

import json
import os
from pprint import pformat

from flask import current_app
from invenio_queues import current_queues
from invenio_rdm_records.services.communities.components import (
    CommunityServiceComponents as DefaultCommunityComponents,
)
from invenio_rdm_records.services.components import (
    DefaultRecordsComponents,
)
from invenio_remote_api_provisioner.signals import (
    remote_api_provisioning_triggered,
)
from invenio_remote_api_provisioner.tasks import send_remote_api_update

from . import config
from .components import RemoteAPIProvisionerFactory


def on_remote_api_provisioning_triggered(
    app_obj,
):
    """Consume the remote_api_provisioning_triggered signal.

    Provisioning event task is called directly from the service component
    but the callback updates the record with the result of the provisioning
    via an event queue to avoid detached instance errors.

    Events consumed from the remote-api-provisioning-events queue
    are processed here. The event is a dictionary with the
    following keys:

    - "response_json" (dict): The JSON response from the external API
    - "service_type" (str): The type of service that was called
    - "service_method" (str): The method of the service that was called
    - "request_url" (str): The URL that was requested of the external API
    - "payload_object" (dict): The JSON payload that was sent to the external
        API
    - "record" (dict): The new record that is being created for publication
        with the data added by other service components prior to this one
    - "draft" (dict): The draft that was being published, prior to
        publication (as a dictionary)
    - along with any other keyword arguments that are passed to the
        component method
    """
    current_app.logger.warning("Received remote_api_provisioning_triggered ****")

    for event in current_queues.queues["remote-api-provisioning-events"].consume():
        current_app.logger.debug(
            f"Consumed event: {event['service_type']} "
            f"{event['service_method']} "
            f"{event['record'].get('id') or event['data'].get('slug')}  ****"
        )

        if os.getenv("MOCK_SIGNAL_SUBSCRIBER"):  # for unit tests
            current_app.logger.debug("Event:")
            current_app.logger.debug(event)
            os.environ["MOCK_SIGNAL_SUBSCRIBER"] = json.dumps(event)
            return
        else:
            conf = app_obj.config.get("REMOTE_API_PROVISIONER_EVENTS").get(
                event["service_type"]
            )
            # app_obj.logger.debug("service conf:")
            # app_obj.logger.debug(pformat(conf.keys()))
            # app_obj.logger.debug(f"event request_url: {event['request_url']}")
            endpoint_conf = [v for k, v in conf.items() if k in event["request_url"]][0]
            method_conf = endpoint_conf[event["service_method"]]
            callback = method_conf.get("callback")
            # Because it's called as a linked callback from another task,
            # the signature will receive the result of the prior task
            # as the first argument.

            callback.delay(**event)

            # callback_signature = callback.s(**event) if callback else None

            # the `link` task call will be executed after the task
            # send_remote_api_update.apply_async(
            #     kwargs=event,
            #     link=callback_signature,
            # )


class InvenioRemoteAPIProvisioner(object):
    """Flask extension for invenio-remote-api-provisioner.

    Args:
        object (_type_): _description_
    """

    def __init__(self, app=None) -> None:
        """Extention initialization."""
        if app:
            self.init_app(app)

    def init_app(self, app) -> None:
        """Registers the Flask extension during app initialization.

        Args:
            app (Flask): the Flask application object on which to initialize
                the extension
        """
        self.init_config(app)
        self.init_listeners(app)
        app.extensions["invenio-remote-api-provisioner"] = self

    def init_config(self, app) -> None:
        """Initialize configuration for the extention.

        Args:
            app (Flask): the Flask application object on which to initialize
                the extension
        """
        for k in dir(config):
            if k.startswith("REMOTE_API_PROVISIONER_"):
                app.config.setdefault(k, getattr(config, k))

        records_component = RemoteAPIProvisionerFactory(app.config, "rdm_record")
        old_record_components = app.config.get(
            "RDM_RECORDS_SERVICE_COMPONENTS", [*DefaultRecordsComponents]
        )
        app.config["RDM_RECORDS_SERVICE_COMPONENTS"] = [
            *old_record_components,
            records_component,
        ]

        community_component = RemoteAPIProvisionerFactory(app.config, "community")
        old_community_components = app.config.get("COMMUNITIES_SERVICE_COMPONENTS", [])
        if not old_community_components:
            old_community_components = [*DefaultCommunityComponents]
        app.config["COMMUNITIES_SERVICE_COMPONENTS"] = [
            *old_community_components,
            community_component,
        ]

    def init_listeners(self, app):
        """Initialize listeners for the extension.

        Args:
            app (_type_): _description_
        """

        remote_api_provisioning_triggered.connect(
            on_remote_api_provisioning_triggered, app
        )
