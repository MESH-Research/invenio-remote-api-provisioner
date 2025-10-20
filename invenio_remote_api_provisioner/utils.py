#
# This file is part of the invenio-remote-api-provisioner package.
# Copyright (C) 2024, MESH Research.
#
# invenio-remote-search-provisioner is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see
# LICENSE file for more details.

"""Utility functions for invenio-remote-api-provisioner."""

from invenio_accounts.models import User


def get_user_idp_info(user: User) -> dict:
    """Get the user's IDP information.

    params:
        user: The user's InvenioRDM id.

    Returns:
        A dict containing the user's IDP information with
        the keys "authentication_source" and "id_from_idp".
        Or an empty dict if the user has no IDP information.
    """
    user_info = {}
    if (
        user
        and user.external_identifiers
        and len(user.external_identifiers) > 0
    ):
        user_info.update(
            {
                "authentication_source": user.external_identifiers[0].method,
                "id_from_idp": user.external_identifiers[0].id,
            }
        )
    return user_info
