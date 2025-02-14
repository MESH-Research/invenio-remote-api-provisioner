# -*- coding: utf-8 -*-
#
# This file is part of the invenio-remote-search-provisioner package.
# (c) 2024 Mesh Research
#
# invenio-remote-search-provisioner is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see
# LICENSE file for more details.


"""RDM service component to trigger external provisioning messages."""

import arrow
from flask import current_app
from flask_principal import Identity
from invenio_drafts_resources.services.records.components import (
    ServiceComponent,
)
from invenio_rdm_records.records.api import RDMRecord, RDMDraft
from invenio_records_resources.services.uow import (
    TaskOp,
    unit_of_work,
    UnitOfWork,
)

from pprint import pformat
from typing import Optional
from .tasks import send_remote_api_update

# from .signals import remote_api_provisioning_triggered
# from .utils import get_user_idp_info


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
    - method: the HTTP method to use or a callable that returns the
              method string
    - payload: the payload dictionary to send or a callable that returns
              the payload dictionary
    - with_record_owner: a boolean to include the record owner in the
                         payload
    - callback: a callback function to update the record or draft after
                the remote API call is successful
    - url_factory: a callable that returns the URL string
    - auth_token: the authentication token to use for the request
    - timing_field: the name of the custom field that stores the last
                      update date/time of the record

    The component class is responsible for sending the message to the
    endpoint, handling any response, and calling any callback function
    defined in the configuration.
    """

    all_endpoints = app_config.get("REMOTE_API_PROVISIONER_EVENTS", {})
    endpoints = all_endpoints.get(service_type, {})
    service_type = service_type

    @unit_of_work()
    def publish(self, identity, record, draft=None, uow=None, **kwargs):
        self._do_method_action(
            "publish", identity, record, draft=draft, uow=uow, **kwargs
        )

    @unit_of_work()
    def update(self, identity, record, draft=None, data=None, uow=None, **kwargs):
        self._do_method_action(
            "update", identity, record, draft=draft, data=data, uow=uow, **kwargs
        )

    @unit_of_work()
    def delete(self, identity, record, draft=None, uow=None, **kwargs):
        self._do_method_action(
            "delete", identity, record, draft=draft, uow=uow, **kwargs
        )

    @unit_of_work()
    def delete_record(self, identity, record, data=None, uow=None, **kwargs):
        self._do_method_action(
            "delete_record", identity, record, data=data, uow=uow, **kwargs
        )

    # FIXME: either fix unit_of_work decoration or add other methods
    #        explicitly to the component class
    @unit_of_work()
    def _do_method_action(
        self,
        service_method: str,
        identity: Identity,
        record: RDMRecord,
        draft: Optional[RDMDraft] = None,
        data: Optional[dict] = None,
        uow: Optional[UnitOfWork] = None,
        **kwargs,
    ):
        for endpoint, events in self.endpoints.items():
            if service_method in events.keys():
                # current_app.logger.debug(f"service_method: {service_method}")
                # current_app.logger.debug(f"draft: {draft}")
                # current_app.logger.debug(f"record: {record}")
                # current_app.logger.debug(f"data: {data}")
                # current_app.logger.debug(
                #     f"kwargs: {pformat({k: v for k, v in kwargs.items()})}",
                # )
                event_config = events[service_method]
                timing_field = event_config.get("timing_field")
                # Prevent infinite loop if callback triggers a
                # subsequent publish by not issuing signal
                # if record has been updated in the last 30 seconds
                # NOTE: You will need to update the timing field value in your
                # callback function. We cannot do this here in case the API
                # call is not successful.
                if service_type == "rdm_record":
                    visibility = record.get("access", {}).get("record", None)
                    if not visibility and draft:
                        visibility = draft.get("access", {}).get("record", "public")
                elif service_type == "community":
                    visibility = record.get("access", {}).get("visibility", None)
                else:
                    raise ValueError(f"Invalid service type: {service_type}")

                last_update = None
                if record and visibility == "public":
                    # TODO: has to be custom field?
                    if service_type == "rdm_record":
                        recid = record.get("id")
                    elif service_type == "community" and data:
                        recid = data["slug"]
                    elif service_type == "community" and service_method == "delete":
                        recid = None
                    elif service_type == "community" and service_method == "restore":
                        recid = None  # FIXME: Implement restore

                    if timing_field:
                        last_update = record["custom_fields"].get(timing_field)
                    current_app.logger.info(
                        f"Record {recid} last updated " f"at {last_update}"
                    )
                    last_update_dt = (
                        arrow.get(last_update)
                        if last_update
                        else arrow.utcnow().shift(days=-1)
                    )
                    if last_update_dt.shift(seconds=5) > arrow.utcnow():
                        current_app.logger.info(
                            "Record has been updated in the last 5 seconds."
                            " Avoiding infinite loop."
                        )
                        current_app.logger.info(last_update_dt)
                    elif record and uow:
                        task_payload = {
                            "identity_id": identity.id,
                            "record": record.copy(),
                            "is_published": (
                                record.is_published
                                if hasattr(record, "is_published")
                                else None
                            ),
                            "is_draft": (
                                record.is_draft if hasattr(record, "is_draft") else None
                            ),
                            "is_deleted": (
                                record.is_deleted
                                if hasattr(record, "is_deleted")
                                else None
                            ),
                            "parent": record.parent,
                            "latest_version_index": (
                                getattr(record.versions, "latest_index", None)
                                if hasattr(record, "versions")
                                else None
                            ),
                            "current_version_index": (
                                getattr(record.versions, "index", None)
                                if hasattr(record, "versions")
                                else None
                            ),
                            "draft": draft,
                            "data": data,
                            "endpoint": endpoint,
                            "service_type": self.service_type,
                            "service_method": service_method,
                        }
                        # current_app.logger.debug(f"task_payload: {task_payload}")
                        uow.register(TaskOp(send_remote_api_update, **task_payload))

    methods = list(
        set(
            [
                m
                for k, v in endpoints.items()
                for m in v.keys()
                if m not in ["publish", "update"]  # FIXME: testing hack
            ]
        )
    )
    component_props = {
        "service_type": service_type,
        "endpoints": endpoints,
        "_do_method_action": _do_method_action,
    }

    for m in methods:
        component_props[m] = (
            lambda self, identity, service_method=m, **kwargs: self._do_method_action(  # noqa: E501
                service_method, identity, **kwargs
            )
        )
    component_props["update"] = update
    component_props["publish"] = publish
    component_props["delete"] = delete
    component_props["delete_record"] = delete_record
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
