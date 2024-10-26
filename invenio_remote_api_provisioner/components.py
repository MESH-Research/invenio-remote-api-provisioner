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
from invenio_drafts_resources.services.records.components import (
    ServiceComponent,
)
from invenio_records_resources.services.uow import TaskOp, unit_of_work

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

    @unit_of_work()
    def _do_method_action(
        self,
        service_method,
        identity,
        record=None,
        draft=None,
        uow=None,
        **kwargs,
    ):
        current_app.logger.warning("Service method: %s", service_method)
        current_app.logger.warning("record:")
        current_app.logger.warning(record)
        current_app.logger.warning("data:")
        current_app.logger.warning(kwargs.get("data"))
        current_app.logger.warning(kwargs.keys())
        for endpoint, events in self.endpoints.items():
            current_app.logger.warning("Endpoint: %s", endpoint)
            if service_method in events.keys():
                event_config = events[service_method]
                timing_field = event_config.get("timing_field")
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
                        f"Record {record.get('id')} last updated "
                        f"at {last_update}"
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
                        uow.register(
                            TaskOp(
                                send_remote_api_update,
                                record=record,
                                draft=draft,
                                endpoint=endpoint,
                                service_type=self.service_type,
                                service_method=service_method,
                            )
                        )

                        # FIXME: We've deprecated this code using a queue
                        # in favour of directly calling the task. (Which is
                        # processed in a queue anyway and is much more
                        # easily tested.)
                        #
                        # current_app.logger.info(
                        #     "Record has not been updated in the last 30 "
                        #     "seconds."
                        # )
                        # current_app.logger.info(
                        #     f"Sending {self.service_type} {service_method} "
                        #     f"message to {endpoint} for record "
                        #     f"{record.get('id') if record else None}, "
                        #     f"draft {draft.get('id') if draft else None}"
                        # )

                        # messages_content = [
                        #     {
                        #         "service_type": self.service_type,
                        #         "service_method": service_method,
                        #         "request_url": request_url,
                        #         "http_method": http_method,
                        #         "payload_object": payload_object,
                        #         "record_id": (
                        #             record.get("id") if record else None
                        #         ),
                        #         "draft_id": draft.get("id") if draft
                        #   else None,
                        #         "request_headers": headers,
                        #     }
                        # ]

                        # current_queues.queues[
                        #     "remote-api-provisioning-events"
                        # ].publish(messages_content)
                        # remote_api_provisioning_triggered.send(
                        #     current_app._get_current_object()
                        # )

                        # conf = app_obj.config.get(
                        #     "REMOTE_API_PROVISIONER_EVENTS"
                        # ).get(event["service_type"])
                        # endpoint_conf = [
                        #     v
                        #     for k, v in conf.items()
                        #     if k in event["request_url"]
                        # ][0]
                        # method_conf = endpoint_conf[event["service_method"]]
                        # callback = method_conf.get("callback")
                        # Because it's called as a linked callback from
                        # another task, the signature will receive the result
                        # of the prior task as the first argument.
                        # current_app.logger.debug("Callback args:")
                        # current_app.logger.debug(pformat(event))
                        # callback_signature = (
                        #     callback.s(**event) if callback else None
                        # )

            # the `link` task call will be executed after the task
            # send_remote_api_update.apply_async(
            #     kwargs=event,
            #     link=callback_signature,
            # )
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
