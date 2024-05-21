# -*- coding: utf-8 -*-
#
# This file is part of the invenio-remote-api-provisioner package.
# Copyright (C) 2023, MESH Research.
#
# invenio-remote-api-provisioner is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see
# LICENSE file for more details.

"""Signals for invenio-remote-api-provisioner."""

from blinker import Namespace

remote_api_provisioning_events = Namespace()

remote_api_provisioning_triggered = remote_api_provisioning_events.signal(
    "remote-api-provisioning-triggered"
)
"""Remote api provisioning signal.

"""
