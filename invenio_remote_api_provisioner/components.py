# -*- coding: utf-8 -*-
#
# This file is part of the invenio-remote-search-provisioner package.
# (c) 2024 Mesh Research
#
# invenio-remote-search-provisioner is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see
# LICENSE file for more details.


"""RDM service component to trigger external provisioning messages."""

from calendar import c
import arrow
from flask import current_app
from invenio_accounts import current_accounts
from invenio_communities.proxies import current_communities
from invenio_drafts_resources.services.records.components import (
    ServiceComponent,
)
from invenio_queues import current_queues
from invenio_rdm_records.proxies import (
    current_rdm_records_service as records_service,
)
import os
from pprint import pformat

from .signals import remote_api_provisioning_triggered
from .utils import get_user_idp_info


def RemoteAPIProvisionerFactory(app_config, service_type):
    """Factory function to construct a service component to emit messages.

    This factory function dynamically constructs a service component class
    whose methods send messages to remote API endpoints. By constructing the
    class dynamically, we avoid defining many unused methods that would be
    called on every operation of the service class but do nothing. Instead,
    the dynamically constructed class only includes the methods that are
    configured to send messages to a remote API.

    This component is injected into either the RDMRecordService or
    CommunityService, depending on this service_type value supplied
    by the factory function that creates the component class
    (either "rdm_record" or "community").

    As with all service components, the public methods of the component
    class are called during the execution of the method with the same
    name in the parent service. Only the methods that are defined in the
    component configuration will perform any action.

    *Note that this class includes methods
    for all the possible service methods available from either the
    RDMRecordService or CommunityService, but not all methods will be
    available for both services.*

    The component class is responsible for sending messages to the
    configured endpoints for the service type. The endpoints are
    configured in the application configuration under the key
    REMOTE_API_PROVISIONER_EVENTS.

    The configuration is a dictionary with the service type as the key
    and a dictionary of endpoints as the value. The endpoints dictionary
    has the endpoint URL as the key and a dictionary of events as the
    value. The events dictionary has the service method name as the key
    and a dictionary of the method properties as the value.

    The method properties dictionary has the following keys
    - method: the HTTP method to use
    - payload: the payload to send
    - with_record_owner: include the record owner in the payload
    - callback: a callback function to update the record or draft

    The component class is responsible for sending the message to the
    endpoint, handling any response, and calling any callback function
    defined in the configuration.
    """

    all_endpoints = app_config.get("REMOTE_API_PROVISIONER_EVENTS", {})
    endpoints = all_endpoints.get(service_type, {})
    service_type = service_type

    def _get_payload_object(
        self,
        identity,
        payload,
        record=None,
        with_record_owner=False,
        **kwargs,
    ):
        """Get the payload object for the notification.

        Parameters:
            identity (dict): The identity of the user performing
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

    def _do_method_action(
        self,
        service_method,
        identity,
        record=None,
        draft=None,
        **kwargs,
    ):
        current_app.logger.debug("Service method: %s", service_method)
        current_app.logger.debug("record:")
        current_app.logger.debug(record)
        current_app.logger.debug("data:")
        current_app.logger.debug(kwargs.get("data"))
        current_app.logger.debug(kwargs.keys())
        for endpoint, events in self.endpoints.items():
            if service_method in events.keys():
                timing_field = events[service_method].get("timing_field")
                # FIXME: prevent infinite loop if callback triggers a
                # subsequent publish by not issuing signal
                # if record has been updated in the last 30 seconds
                # NOTE: You will need to update the timing field value in your
                # callback function. We cannot do this here in case the API
                # call is not successful.
                visibility = record.get("access", {}).get("visibility", None)
                if not visibility:
                    visibility = draft.get("access", {}).get(
                        "record", "public"
                    )

                last_update = None
                if record and visibility == "public":
                    # TODO: has to be custom field?
                    if timing_field:
                        last_update = record["custom_fields"].get(timing_field)
                    current_app.logger.info(
                        f"Record {record.get('id')} last updated at {last_update}"
                    )
                    last_update_dt = (
                        arrow.get(last_update)
                        if last_update
                        else arrow.utcnow().shift(days=-1)
                    )
                    if last_update_dt.shift(seconds=5) > arrow.utcnow():
                        current_app.logger.info(
                            "Record has been updated in the last 30 seconds."
                            " Avoiding infinite loop."
                        )
                        current_app.logger.info(last_update_dt)
                    else:
                        current_app.logger.info(
                            "Record has not been updated in the last 30 "
                            "seconds."
                        )
                        current_app.logger.info(
                            f"Sending {self.service_type} {service_method} "
                            f"message to {endpoint} for record {record.get('id') if record else None}, "
                            f"draft {draft.get('id') if draft else None}"
                        )
                        if events[service_method].get("url_factory"):
                            request_url = events[service_method][
                                "url_factory"
                            ](identity, record=record, draft=draft, **kwargs)
                            current_app.logger.debug(
                                "Request URL: %s", request_url
                            )
                        else:
                            request_url = endpoint

                        if callable(events[service_method]["http_method"]):
                            http_method = events[service_method][
                                "http_method"
                            ](identity, record=record, draft=draft, **kwargs)
                        else:
                            http_method = events[service_method]["http_method"]

                        payload_object = None
                        if events[service_method].get("payload"):
                            try:
                                payload_object = self._get_payload_object(
                                    identity,
                                    events[service_method]["payload"],
                                    record=record,
                                    draft=draft,
                                    with_record_owner=events[
                                        service_method
                                    ].get("with_record_owner", False),
                                    **kwargs,
                                )
                                # current_app.logger.debug("Payload object:")
                                # current_app.logger.debug(pformat(payload_object))
                            except (RuntimeError, ValueError) as e:
                                current_app.logger.error(
                                    f"Could not send "
                                    f"{self.service_type} {service_method} "
                                    f"update for record {record.get('id') if record else None}"
                                    f", draft {draft.get('id') if draft else None}: Problem assembling "
                                    f"update payload: {e}"
                                )
                        headers = events[service_method].get("headers", {})
                        if events[service_method].get("auth_token"):
                            headers["Authorization"] = (
                                f"Bearer {events[service_method]['auth_token']}"
                            )
                            current_app.logger.debug(f"headers: {headers}")
                        messages_content = [
                            {
                                "service_type": self.service_type,
                                "service_method": service_method,
                                "request_url": request_url,
                                "http_method": http_method,
                                "payload_object": payload_object,
                                "record_id": (
                                    record.get("id") if record else None
                                ),
                                "draft_id": draft.get("id") if draft else None,
                                "request_headers": headers,
                            }
                        ]

                        current_queues.queues[
                            "remote-api-provisioning-events"
                        ].publish(messages_content)
                        remote_api_provisioning_triggered.send(
                            current_app._get_current_object()
                        )
                        # current_app.logger.debug(
                        #     f"Published {self.service_type} {service_method} event "
                        #     "to queue and emitted remote_api_provisioning_triggered"
                        #     " signal"
                        # )
                        # current_app.logger.debug(pformat(messages_content))

    methods = list(set([m for k, v in endpoints.items() for m in v.keys()]))
    component_props = {
        "service_type": service_type,
        "endpoints": endpoints,
        "_get_payload_object": _get_payload_object,
        "_do_method_action": _do_method_action,
    }
    for m in methods:
        component_props[m] = (
            lambda self, identity, service_method=m, **kwargs: self._do_method_action(  # noqa: E501
                service_method, identity, **kwargs
            )
        )
    service_names = {
        "rdm_record": "RDMRecord",
        "community": "Community",
    }
    RemoteAPIProvisionerComponent = type(
        f"RemoteAPI{service_names[service_type]}ProvisionerComponent",
        (ServiceComponent,),
        component_props,
    )

    return RemoteAPIProvisionerComponent
