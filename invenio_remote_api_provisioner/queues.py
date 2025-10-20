#
# This file is part of the invenio-remote-api-provisioner package.
# Copyright (C) 2023, MESH Research.
#
# invenio-remote-api-provisioner is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see
# LICENSE file for more details.

"""Message queues."""

from flask import current_app


def declare_queues():
    """Execute callbacks."""
    return [
        {
            "name": "remote-api-provisioning-events",
            "exchange": current_app.config[
                "REMOTE_API_PROVISIONER_MQ_EXCHANGE"
            ],
        }
    ]
