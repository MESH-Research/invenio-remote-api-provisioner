# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 MESH Research
#
# invenio-groups is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.

"""Pytest configuration for invenio-groups.

See https://pytest-invenio.readthedocs.io/ for documentation on which test
fixtures are available.
"""


# from traceback import format_exc
import traceback
import pytest
from flask_security.utils import hash_password
from invenio_access.models import ActionRoles, Role
from invenio_access.permissions import superuser_access, system_identity
from invenio_administration.permissions import administration_access_action
from invenio_app.factory import create_api
from invenio_communities.proxies import current_communities
from invenio_communities.communities.records.api import Community
from invenio_rdm_records.services.pids import providers
from invenio_rdm_records.services.stats import (
    permissions_policy_lookup_factory,
)
from invenio_records_resources.services.custom_fields import TextCF
from invenio_records_resources.services.custom_fields.errors import (
    CustomFieldsException,
)
from invenio_records_resources.services.custom_fields.mappings import Mapping
from invenio_records_resources.services.custom_fields.validate import (
    validate_custom_fields,
)
from invenio_search import current_search_client
from invenio_search.engine import dsl
from invenio_search.engine import search as search_engine
from invenio_search.utils import build_alias_name
from invenio_stats.queries import TermsQuery
from invenio_vocabularies.proxies import current_service as vocabulary_service
from invenio_vocabularies.records.api import Vocabulary
import marshmallow as ma
import os
from .fake_datacite_client import FakeDataCiteClient

pytest_plugins = ("celery.contrib.pytest",)

AllowAllPermission = type(
    "Allow",
    (),
    {"can": lambda self: True, "allows": lambda *args: True},
)()


def AllowAllPermissionFactory(obj_id, action):
    return AllowAllPermission


def _(x):
    """Identity function for string extraction."""
    return x


@pytest.fixture(scope="module")
def extra_entry_points():
    return {
        "invenio_base.api_apps": [
            "invenio_remote_api_provisioner ="
            " invenio_remote_api_provisioner."
            "ext:InvenioRemoteAPIProvisioner"
        ],
        "invenio_base.apps": [
            "invenio_remote_api_provisioner ="
            " invenio_remote_api_provisioner."
            "ext:InvenioRemoteAPIProvisioner"
        ],
        "invenio_celery.tasks": [
            "invenio_remote_api_provisioner ="
            " invenio_remote_api_provisioner."
            "tasks"
        ],
    }


@pytest.fixture(scope="module")
def communities_service(app):
    return current_communities.service


test_config = {
    "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg2://"
    "invenio:invenio@localhost:5432/invenio",
    "SQLALCHEMY_TRACK_MODIFICATIONS": True,
    "INVENIO_WTF_CSRF_ENABLED": False,
    "INVENIO_WTF_CSRF_METHODS": [],
    "APP_DEFAULT_SECURE_HEADERS": {
        "content_security_policy": {"default-src": []},
        "force_https": False,
    },
    "BROKER_URL": "amqp://guest:guest@localhost:5672//",
    "CELERY_BROKER_URL": "amqp://guest:guest@localhost:5672//",
    # "BROKER_URL": "redis://localhost:6379/0",
    # "BROKER_URL": "amqp://invenio:invenio@localhost:5672//",
    # "CELERY_BROKER_URL": "amqp://invenio:invenio@localhost:5672//",
    # "CELERY_CACHE_BACKEND": "memory",
    # "CELERY_RESULT_BACKEND": "cache",
    "CELERY_TASK_ALWAYS_EAGER": True,
    "CELERY_TASK_EAGER_PROPAGATES_EXCEPTIONS": True,
    "RATELIMIT_ENABLED": False,
    "SECRET_KEY": "test-secret-key",
    "SECURITY_PASSWORD_SALT": "test-secret-key",
    "TESTING": True,
    "RECORDS_REFRESOLVER_CLS": "invenio_records.resolver.InvenioRefResolver",
    "RECORDS_REFRESOLVER_STORE": (
        "invenio_jsonschemas.proxies.current_refresolver_store"
    ),
    # Variable not used. We set it to silent warnings
    "JSONSCHEMAS_HOST": "not-used",
    # Define files storage class list
    "FILES_REST_STORAGE_CLASS_LIST": {
        "L": "Local",
        "F": "Fetch",
        "R": "Remote",
    },
    "FILES_REST_DEFAULT_STORAGE_CLASS": "L",
}

# FIXME: provide proper namespace url
test_config["COMMUNITIES_NAMESPACES"] = {
    "kcr": "https://invenio-dev.hcommons-staging.org/terms/"
}

test_config["COMMUNITIES_CUSTOM_FIELDS"] = [
    TextCF(name="kcr:commons_instance"),
    TextCF(name="kcr:commons_group_id"),
    TextCF(name="kcr:commons_group_name"),
    TextCF(name="kcr:commons_group_description"),
    TextCF(name="kcr:commons_group_visibility"),
]

test_config["COMMUNITIES_CUSTOM_FIELDS_UI"] = [
    {
        "section": "Linked Commons Group",
        "hidden": False,
        "description": (
            "Information about a Commons group that owns the collection"
        ),
        "fields": [
            {
                "field": "kcr:commons_group_name",
                "ui_widget": "Input",
                "props": {
                    "label": "Commons Group Name",
                    "placeholder": "",
                    "icon": "",
                    "description": ("Name of the Commons group."),
                    "disabled": True,
                },
            },
            {
                "field": "kcr:commons_group_id",
                "ui_widget": "Input",
                "props": {
                    "label": "Commons Group ID",
                    "placeholder": "",
                    "icon": "",
                    "description": ("ID of the Commons group"),
                    "disabled": True,
                },
            },
            {
                "field": "kcr:commons_instance",
                "ui_widget": "Input",
                "props": {
                    "label": "Commons Instance",
                    "placeholder": "",
                    "icon": "",
                    "description": (
                        "The Commons to which the group belongs (e.g., "
                        "STEMEd+ Commons, MLA Commons, Humanities Commons)"
                    ),
                    "disabled": True,
                },
            },
            {
                "field": "kcr:commons_group_description",
                "ui_widget": "Input",
                "props": {
                    "label": "Commons Group Description",
                    "placeholder": "",
                    "icon": "",
                    "description": ("Description of the Commons group."),
                    "disabled": True,
                },
            },
            {
                "field": "kcr:commons_group_visibility",
                "ui_widget": "Input",
                "props": {
                    "label": "Commons Group Visibility",
                    "placeholder": "",
                    "icon": "",
                    "description": ("Visibility of the Commons group."),
                    "disabled": True,
                },
            },
        ],
    }
]

# enable DataCite DOI provider
test_config["DATACITE_ENABLED"] = True
test_config["DATACITE_USERNAME"] = "INVALID"
test_config["DATACITE_PASSWORD"] = "INVALID"
test_config["DATACITE_PREFIX"] = "10.1234"
test_config["DATACITE_DATACENTER_SYMBOL"] = "TEST"
# ...but fake it

test_config["RDM_PERSISTENT_IDENTIFIER_PROVIDERS"] = [
    # DataCite DOI provider with fake client
    providers.DataCitePIDProvider(
        "datacite",
        client=FakeDataCiteClient("datacite", config_prefix="DATACITE"),
        label=_("DOI"),
    ),
    # DOI provider for externally managed DOIs
    providers.ExternalPIDProvider(
        "external",
        "doi",
        validators=[
            providers.BlockedPrefixes(config_names=["DATACITE_PREFIX"])
        ],
        label=_("DOI"),
    ),
    # OAI identifier
    providers.OAIPIDProvider(
        "oai",
        label=_("OAI ID"),
    ),
]


test_config["STATS_QUERIES"] = {
    "record-view": {
        "cls": TermsQuery,
        "permission_factory": AllowAllPermissionFactory,
        "params": {
            "index": "stats-record-view",
            "doc_type": "record-view-day-aggregation",
            "copy_fields": {
                "recid": "recid",
                "parent_recid": "parent_recid",
            },
            "query_modifiers": [],
            "required_filters": {
                "recid": "recid",
            },
            "metric_fields": {
                "views": ("sum", "count", {}),
                "unique_views": ("sum", "unique_count", {}),
            },
        },
    },
    "record-view-all-versions": {
        "cls": TermsQuery,
        "permission_factory": AllowAllPermissionFactory,
        "params": {
            "index": "stats-record-view",
            "doc_type": "record-view-day-aggregation",
            "copy_fields": {
                "parent_recid": "parent_recid",
            },
            "query_modifiers": [],
            "required_filters": {
                "parent_recid": "parent_recid",
            },
            "metric_fields": {
                "views": ("sum", "count", {}),
                "unique_views": ("sum", "unique_count", {}),
            },
        },
    },
    "record-download": {
        "cls": TermsQuery,
        "permission_factory": AllowAllPermissionFactory,
        "params": {
            "index": "stats-file-download",
            "doc_type": "file-download-day-aggregation",
            "copy_fields": {
                "recid": "recid",
                "parent_recid": "parent_recid",
            },
            "query_modifiers": [],
            "required_filters": {
                "recid": "recid",
            },
            "metric_fields": {
                "downloads": ("sum", "count", {}),
                "unique_downloads": ("sum", "unique_count", {}),
                "data_volume": ("sum", "volume", {}),
            },
        },
    },
    "record-download-all-versions": {
        "cls": TermsQuery,
        "permission_factory": AllowAllPermissionFactory,
        "params": {
            "index": "stats-file-download",
            "doc_type": "file-download-day-aggregation",
            "copy_fields": {
                "parent_recid": "parent_recid",
            },
            "query_modifiers": [],
            "required_filters": {
                "parent_recid": "parent_recid",
            },
            "metric_fields": {
                "downloads": ("sum", "count", {}),
                "unique_downloads": ("sum", "unique_count", {}),
                "data_volume": ("sum", "volume", {}),
            },
        },
    },
}

test_config["STATS_PERMISSION_FACTORY"] = permissions_policy_lookup_factory

SITE_UI_URL = os.environ.get("INVENIO_SITE_UI_URL", "http://localhost:5000")


def format_commons_search_payload(rec, data, record, owner, **kwargs):
    """Format payload for external service."""
    try:
        payload = {
            "record_id": record["id"],
            "type": "work",
            "network": "works",
            "primary_url": f"{SITE_UI_URL}/records/{record['id']}",
            "other_urls": [],
            "owner_name": owner["full_name"],
            "owner_username": owner["id_from_idp"],
            "full_content": "",
            "created_date": rec["created"],
            "updated_date": rec["updated"],
            "revision_id": rec["revision_id"],
            "version": rec["versions"]["index"],
        }
        if data.get("metadata", {}):
            meta = {
                "title": data["metadata"].get("title", ""),
                "description": data["metadata"].get("description", ""),
                "publication_date": data["metadata"].get(
                    "publication_date", ""
                ),
            }
            payload.update(meta)
            if data["metadata"].get("pids", {}).get("doi", {}):
                f"https://doi.org/{record['pids']['doi']['identifier']}",
            for u in [
                i
                for i in data["metadata"].get("identifiers", [])
                if i["scheme"] == "url" and i not in payload["other_urls"]
            ]:
                payload["other_urls"].append(u["identifier"])
            if record["files"]["enabled"]:
                payload["other_urls"].append(
                    f"{SITE_UI_URL}/records/{record['id']}/files",
                )
    except Exception as e:
        return {"internal_error": pformat(e)}

    return payload


test_config["REMOTE_API_PROVISIONER_EVENTS"] = {
    "https://hcommons.org/api/v1/search_update": {
        # "create": {
        #     "method": "POST",
        #     "payload": lambda rec, data, record, owner, **kwargs: (
        #         format_commons_search_payload(rec, data, record, **kwargs)
        #     ),
        # },
        # "update_draft": {
        #     "method": "PUT",
        #     "payload": lambda rec, data, record, owner, **kwargs: (
        #         format_commons_search_payload(
        #             rec, data, record, owner, **kwargs
        #         )
        #     ),
        # },
        "publish": {
            "method": "POST",
            "payload": lambda rec, data, record, owner, **kwargs: (
                format_commons_search_payload(
                    rec, data, record, owner, **kwargs
                )
            ),
        },
        "delete_record": {
            "method": "DELETE",
            "payload": lambda rec, data, record, owner, **kwargs: (
                format_commons_search_payload(
                    rec, data, record, owner, **kwargs
                )
            ),
        },
    },
}


# @pytest.fixture(scope="session")
# def broker_uri():
#     yield "amqp://guest:guest@localhost:5672//"


@pytest.fixture(scope="session")
def celery_config(celery_config):
    # celery_config["broker_url"] = broker_uri
    celery_config["broker_url"] = "amqp://guest:guest@localhost:5672//"
    return celery_config


# Vocabularies


@pytest.fixture(scope="module")
def resource_type_type(app):
    """Resource type vocabulary type."""
    return vocabulary_service.create_type(
        system_identity, "resourcetypes", "rsrct"
    )


@pytest.fixture(scope="module")
def resource_type_v(app, resource_type_type):
    """Resource type vocabulary record."""
    vocabulary_service.create(
        system_identity,
        {
            "id": "dataset",
            "icon": "table",
            "props": {
                "csl": "dataset",
                "datacite_general": "Dataset",
                "datacite_type": "",
                "openaire_resourceType": "21",
                "openaire_type": "dataset",
                "eurepo": "info:eu-repo/semantics/other",
                "schema.org": "https://schema.org/Dataset",
                "subtype": "",
                "type": "dataset",
            },
            "title": {"en": "Dataset"},
            "tags": ["depositable", "linkable"],
            "type": "resourcetypes",
        },
    )

    vocabulary_service.create(
        system_identity,
        {  # create base resource type
            "id": "image",
            "props": {
                "csl": "figure",
                "datacite_general": "Image",
                "datacite_type": "",
                "openaire_resourceType": "25",
                "openaire_type": "dataset",
                "eurepo": "info:eu-repo/semantic/other",
                "schema.org": "https://schema.org/ImageObject",
                "subtype": "",
                "type": "image",
            },
            "icon": "chart bar outline",
            "title": {"en": "Image"},
            "tags": ["depositable", "linkable"],
            "type": "resourcetypes",
        },
    )

    vocab = vocabulary_service.create(
        system_identity,
        {
            "id": "image-photograph",
            "props": {
                "csl": "graphic",
                "datacite_general": "Image",
                "datacite_type": "Photo",
                "openaire_resourceType": "25",
                "openaire_type": "dataset",
                "eurepo": "info:eu-repo/semantic/other",
                "schema.org": "https://schema.org/Photograph",
                "subtype": "image-photograph",
                "type": "image",
            },
            "icon": "chart bar outline",
            "title": {"en": "Photo"},
            "tags": ["depositable", "linkable"],
            "type": "resourcetypes",
        },
    )

    Vocabulary.index.refresh()

    return vocab


@pytest.fixture(scope="module")
def community_type_type(app):
    """Resource type vocabulary type."""
    return vocabulary_service.create_type(
        system_identity, "communitytypes", "comtyp"
    )


@pytest.fixture(scope="module")
def community_type_v(app, community_type_type):
    """Community type vocabulary record."""
    vocabulary_service.create(
        system_identity,
        {
            "id": "organization",
            "title": {"en": "Organization"},
            "type": "communitytypes",
        },
    )

    vocabulary_service.create(
        system_identity,
        {
            "id": "event",
            "title": {"en": "Event"},
            "type": "communitytypes",
        },
    )

    vocabulary_service.create(
        system_identity,
        {
            "id": "topic",
            "title": {"en": "Topic"},
            "type": "communitytypes",
        },
    )

    vocabulary_service.create(
        system_identity,
        {
            "id": "project",
            "title": {"en": "Project"},
            "type": "communitytypes",
        },
    )

    vocabulary_service.create(
        system_identity,
        {
            "id": "group",
            "title": {"en": "Group"},
            "type": "communitytypes",
        },
    )

    Vocabulary.index.refresh()


def create_communities_custom_fields(app):
    """Creates one or all custom fields for communities.

    $ invenio custom-fields communities create [field].
    """
    available_fields = app.config.get("COMMUNITIES_CUSTOM_FIELDS")
    namespaces = set(app.config.get("COMMUNITIES_NAMESPACES").keys())
    try:
        validate_custom_fields(
            given_fields=None,
            available_fields=available_fields,
            namespaces=namespaces,
        )
    except CustomFieldsException as e:
        print(f"Custom fields configuration is not valid. {e.description}")
    # multiple=True makes it an iterable
    properties = Mapping.properties_for_fields(None, available_fields)

    try:
        communities_index = dsl.Index(
            build_alias_name(
                current_communities.service.config.record_cls.index._name
            ),
            using=current_search_client,
        )
        communities_index.put_mapping(body={"properties": properties})
    except search_engine.RequestError as e:
        print("An error occured while creating custom fields.")
        print(e.info["error"]["reason"])


@pytest.fixture(scope="function")
def sample_communities(app, db):
    create_communities_custom_fields(app)

    def create_communities(app, communities_service) -> None:
        communities = communities_service.read_all(
            identity=system_identity, fields=["slug"]
        )
        if communities.total > 0:
            print("Communities already exist.")
            return
        communities_data = {
            "knowledgeCommons": [
                (
                    "123",
                    "Commons Group 1",
                    "Community 1",
                ),
                (
                    "456",
                    "Commons Group 2",
                    "Community 2",
                ),
                (
                    "789",
                    "Commons Group 3",
                    "Community 3",
                ),
                (
                    "101112",
                    "Commons Group 4",
                    "Community 4",
                ),
            ],
            "msuCommons": [
                (
                    "131415",
                    "MSU Group 1",
                    "MSU Community 1",
                ),
                (
                    "161718",
                    "MSU Group 2",
                    "MSU Community 2",
                ),
                (
                    "181920",
                    "MSU Group 3",
                    "MSU Community 3",
                ),
                (
                    "212223",
                    "MSU Group 4",
                    "MSU Community 4",
                ),
            ],
        }
        try:
            for instance in communities_data.keys():
                for c in communities_data[instance]:
                    slug = c[2].lower().replace("-", "").replace(" ", "")
                    rec_data = {
                        "access": {
                            "visibility": "public",
                            "member_policy": "open",
                            "record_policy": "open",
                        },
                        "slug": c[2].lower().replace(" ", "-"),
                        "metadata": {
                            "title": c[2],
                            "description": c[2] + " description",
                            "type": {
                                "id": "event",
                            },
                            "curation_policy": "Curation policy",
                            "page": f"Information for {c[2].lower()}",
                            "website": f"https://{slug}.com",
                            "organizations": [
                                {
                                    "name": "Organization 1",
                                }
                            ],
                        },
                        "custom_fields": {
                            "kcr:commons_instance": instance,
                            "kcr:commons_group_id": c[0],
                            "kcr:commons_group_name": c[1],
                            "kcr:commons_group_description": (
                                f"{c[1]} description"
                            ),
                            "kcr:commons_group_visibility": "public",
                        },
                    }
                    rec = communities_service.create(
                        identity=system_identity, data=rec_data
                    )
                    assert rec["metadata"]["title"] == c[2]
            Community.index.refresh()
        except ma.exceptions.ValidationError:
            print("Error creating communities.")
            print(traceback.format_exc())
            pass

    return create_communities


# @pytest.fixture(scope="module")
# def testapp(app):
#     """Application with just a database.

#     Pytest-Invenio also initialises ES with the app fixture.
#     """
#     yield app


@pytest.fixture()
def users(UserFixture, app, db) -> list:
    """Create example user."""
    # user1 = UserFixture(
    #     email="scottia4@msu.edu",
    #     password="password"
    # )
    # user1.create(app, db)
    # user2 = UserFixture(
    #     email="scottianw@gmail.com",
    #     password="password"
    # )
    # user2.create(app, db)
    with db.session.begin_nested():
        datastore = app.extensions["security"].datastore
        user1 = datastore.create_user(
            email="info@inveniosoftware.org",
            password=hash_password("password"),
            active=True,
        )
        user2 = datastore.create_user(
            email="ser-testalot@inveniosoftware.org",
            password=hash_password("beetlesmasher"),
            active=True,
        )

    db.session.commit()
    return [user1, user2]


@pytest.fixture()
def admin_role_need(db):
    """Store 1 role with 'superuser-access' ActionNeed.

    WHY: This is needed because expansion of ActionNeed is
         done on the basis of a User/Role being associated with that Need.
         If no User/Role is associated with that Need (in the DB), the
         permission is expanded to an empty list.
    """
    role = Role(name="administration-access")
    db.session.add(role)

    action_role = ActionRoles.create(
        action=administration_access_action, role=role
    )
    db.session.add(action_role)

    db.session.commit()
    return action_role.need


@pytest.fixture()
def admin(UserFixture, app, db, admin_role_need):
    """Admin user for requests."""
    u = UserFixture(
        email="admin@inveniosoftware.org",
        password="admin",
    )
    u.create(app, db)

    datastore = app.extensions["security"].datastore
    _, role = datastore._prepare_role_modify_args(
        u.user, "administration-access"
    )

    datastore.add_role_to_user(u.user, role)
    db.session.commit()
    return u


@pytest.fixture()
def superuser_role_need(db):
    """Store 1 role with 'superuser-access' ActionNeed.

    WHY: This is needed because expansion of ActionNeed is
         done on the basis of a User/Role being associated with that Need.
         If no User/Role is associated with that Need (in the DB), the
         permission is expanded to an empty list.
    """
    role = Role(name="superuser-access")
    db.session.add(role)

    action_role = ActionRoles.create(action=superuser_access, role=role)
    db.session.add(action_role)

    db.session.commit()

    return action_role.need


@pytest.fixture()
def superuser_identity(admin, superuser_role_need):
    """Superuser identity fixture."""
    identity = admin.identity
    identity.provides.add(superuser_role_need)
    return identity


@pytest.fixture()
def minimal_record():
    """Minimal record data as dict coming from the external world."""
    return {
        "pids": {},
        "access": {
            "record": "public",
            "files": "public",
        },
        "files": {
            "enabled": False,  # Most tests don't care about files
        },
        "metadata": {
            "creators": [
                {
                    "person_or_org": {
                        "family_name": "Brown",
                        "given_name": "Troy",
                        "type": "personal",
                    }
                },
                {
                    "person_or_org": {
                        "name": "Troy Inc.",
                        "type": "organizational",
                    },
                },
            ],
            "publication_date": "2020-06-01",
            # because DATACITE_ENABLED is True, this field is required
            "publisher": "Acme Inc",
            "resource_type": {"id": "image-photograph"},
            "title": "A Romans story",
        },
    }


@pytest.fixture(scope="module")
def app_config(app_config) -> dict:
    for k, v in test_config.items():
        app_config[k] = v
    return app_config


@pytest.fixture(scope="module")
def create_app(entry_points):
    return create_api
