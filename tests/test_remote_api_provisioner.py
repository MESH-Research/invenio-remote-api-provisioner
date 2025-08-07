import json
import os
import time
from pprint import pformat

import arrow
import pytest  # noqa
from flask import current_app
from invenio_access.permissions import system_identity
from invenio_communities import current_communities
from invenio_queues import current_queues
from invenio_rdm_records.proxies import current_rdm_records
from invenio_remote_api_provisioner.signals import (
    remote_api_provisioning_triggered,
)

from .helpers.api_helpers import (
    format_commons_search_collection_payload,
    format_commons_search_payload,
)


def test_extension(app, search_clear):
    assert "invenio-remote-api-provisioner" in app.extensions


@pytest.mark.skip(reason="Utility")
def replace_value_in_dict(input_dict, pairs):
    for k, v in input_dict.items():
        if isinstance(v, dict):
            replace_value_in_dict(v, pairs)
        elif isinstance(v, str):
            for value, replacement in pairs:
                if value in v:
                    input_dict[k] = v.replace(value, replacement)
    return input_dict


def test_remote_api_provisioner(appctx):
    # from invenio_search import current_search, current_search_client

    # deleted = list(current_search.delete(ignore=[404]))
    assert True


def test_component_publish_signal(
    app,
    minimal_record,
    admin,
    location,
    resource_type_v,
    search,
    search_clear,
    db,
    requests_mock,
    monkeypatch,
    mock_signal_subscriber,
    create_records_custom_fields,
):
    """Test draft creation.

    This should not prompt any remote API operations.
    """

    monkeypatch.setenv("MOCK_SIGNAL_SUBSCRIBER", "True")
    # import invenio_remote_api_provisioner

    # monkeypatch.setattr(
    #     invenio_remote_api_provisioner.ext,
    #     "on_remote_api_provisioning_triggered",
    #     mock_signal_subscriber,
    # )
    rec_url = list(
        app.config["REMOTE_API_PROVISIONER_EVENTS"]["rdm_record"].keys()
    )[0]
    remote_response = {
        "_internal_id": "1234AbCD?",  # can't mock because set at runtime
        "_id": "2E9SqY0Bdd2QL-HGeUuA",
        "title": "A Romans Story 2",
        "primary_url": "http://works.kcommons.org/records/1234",
    }
    requests_mock.post(
        rec_url,
        json=remote_response,
        headers={"Authorization": "Bearer 12345"},
    )

    service = current_rdm_records.records_service

    assert admin.user.roles
    current_app.logger.debug(admin.user.roles)

    # Draft creation, no remote API operations should be prompted
    draft = service.create(admin.identity, minimal_record)
    actual_draft = draft.data
    assert actual_draft["metadata"]["title"] == "A Romans Story"
    assert requests_mock.call_count == 1  # user update at token login

    # Draft edit, no remote API operations should be prompted
    minimal_edited = minimal_record.copy()
    minimal_edited["metadata"]["title"] = "A Romans Story 2"
    edited_draft = service.update_draft(
        admin.identity, draft.id, minimal_record
    )
    actual_edited = edited_draft.data
    assert actual_edited["metadata"]["title"] == "A Romans Story 2"
    assert requests_mock.call_count == 1  # user update at token login

    # Publish, now this should prompt a remote API operation
    record = service.publish(admin.identity, edited_draft.id)
    actual_published = record.data
    assert actual_published["metadata"]["title"] == "A Romans Story 2"

    assert os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "rdm_record|publish"
    monkeypatch.setenv("MOCK_SIGNAL_SUBSCRIBER", "True")

    read_record = service.read(admin.identity, record.id)
    assert read_record.data["metadata"]["title"] == "A Romans Story 2"
    assert (
        os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "True"
    )  # wasn't set by subscriber

    # draft new version
    # no remote API operation should be prompted
    new_version = service.new_version(admin.identity, record.id)
    current_app.logger.debug(pformat(new_version.data))
    assert new_version.data["metadata"]["title"] == "A Romans Story 2"
    assert new_version.data["status"] == "new_version_draft"
    assert new_version.data["is_published"] is False
    assert new_version.data["id"] != actual_published["id"]
    assert new_version.data["parent"]["id"] == actual_published["parent"]["id"]
    assert new_version.data["versions"]["index"] == 2
    assert new_version.data["versions"]["is_latest"] is False
    assert new_version.data["versions"]["is_latest_draft"] is True
    # assert requests_mock.call_count == 1
    assert (
        os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "True"
    )  # wasn't set by subscriber

    # edited draft new version
    # no remote API operation should be prompted
    new_edited_data = new_version.data.copy()
    new_edited_data["metadata"]["publication_date"] = arrow.now().format(
        "YYYY-MM-DD"
    )
    new_edited_data["metadata"]["title"] = "A Romans Story 3"
    new_edited_data["custom_fields"]["kcr:commons_search_recid"] = (
        remote_response["_id"]
    )  # simulate the result of previous remote API operation
    new_edited_version = service.update_draft(
        admin.identity, new_version.id, new_edited_data
    )
    assert new_edited_version.data["metadata"]["title"] == "A Romans Story 3"
    # assert requests_mock.call_count == 1
    assert new_edited_version.data["status"] == "new_version_draft"
    assert new_edited_version.data["is_published"] is False
    assert new_edited_version.data["versions"]["index"] == 2
    assert new_edited_version.data["versions"]["is_latest"] is False
    assert new_edited_version.data["versions"]["is_latest_draft"] is True
    assert (
        new_edited_version.data["custom_fields"].get(
            "kcr:commons_search_recid"
        )
        == remote_response["_id"]
    )
    assert (
        os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "True"
    )  # wasn't set by subscriber

    # publish new version
    # this should trigger a remote API operation
    remote_response_2 = {
        "_internal_id": "1234AbCD?",  # can't mock because set at runtime
        "_id": "2E9SqY0Bdd2QL-HGeUuA",
        "title": "A Romans Story 3",
        "primary_url": "http://works.kcommons.org/records/1234",
    }
    requests_mock.put(
        rec_url + "/" + remote_response["_id"],
        json=remote_response_2,
        headers={"Authorization": "Bearer 12345"},
    )

    new_published_version = service.publish(admin.identity, new_version.id)
    assert os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "rdm_record|publish"
    monkeypatch.setenv("MOCK_SIGNAL_SUBSCRIBER", "True")
    assert (
        new_published_version.data["metadata"]["title"] == "A Romans Story 3"
    )

    read_new_version = service.read(admin.identity, new_published_version.id)
    assert (
        read_new_version.data["custom_fields"].get("kcr:commons_search_recid")
        == remote_response_2["_id"]
    )
    assert (
        os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "True"
    )  # wasn't set by subscriber

    deleted_record = service.delete_record(
        admin.identity, new_published_version.id, data={}
    )
    assert os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "rdm_record|delete_record"
    deleted_actual_data = {
        k: v
        for k, v in deleted_record.data.items()
        if k
        not in [
            "created",
            "updated",
            "links",
        ]
    }
    assert deleted_actual_data == {
        "access": {
            "embargo": {"active": False, "reason": None},
            "files": "public",
            "record": "public",
            "status": "metadata-only",
        },
        "custom_fields": {"kcr:commons_search_recid": "2E9SqY0Bdd2QL-HGeUuA"},
        "deletion_status": {"is_deleted": True, "status": "D"},
        "files": {
            "count": 0,
            "enabled": False,
            "entries": {},
            "order": [],
            "total_bytes": 0,
        },
        "id": read_new_version.data["id"],
        "is_draft": False,
        "is_published": True,
        "media_files": {
            "count": 0,
            "enabled": False,
            "entries": {},
            "order": [],
            "total_bytes": 0,
        },
        "metadata": {
            "creators": [
                {
                    "person_or_org": {
                        "family_name": "Brown",
                        "given_name": "Troy",
                        "name": "Brown, Troy",
                        "type": "personal",
                    }
                },
                {
                    "person_or_org": {
                        "family_name": "Troy Inc.",
                        "name": "Troy Inc.",
                        "type": "organizational",
                    }
                },
            ],
            "publication_date": read_new_version.data["metadata"][
                "publication_date"
            ],
            "publisher": "Acme Inc",
            "resource_type": {
                "id": "image-photograph",
                "title": {"en": "Photo"},
            },
            "title": "A Romans Story 3",
        },
        "parent": {
            "access": {
                "grants": [],
                "links": [],
                "owned_by": {"user": "1"},
                "settings": {
                    "accept_conditions_text": None,
                    "allow_guest_requests": False,
                    "allow_user_requests": False,
                    "secret_link_expiration": 0,
                },
            },
            "communities": {},
            "id": read_new_version.data["parent"]["id"],
            "pids": {},
        },
        "pids": {
            "oai": {
                "identifier": read_new_version.data["pids"]["oai"][
                    "identifier"
                ],
                "provider": "oai",
            }
        },
        "revision_id": 6,
        "stats": {
            "all_versions": {
                "data_volume": 0.0,
                "downloads": 0,
                "unique_downloads": 0,
                "unique_views": 0,
                "views": 0,
            },
            "this_version": {
                "data_volume": 0.0,
                "downloads": 0,
                "unique_downloads": 0,
                "unique_views": 0,
                "views": 0,
            },
        },
        "status": "published",
        "tombstone": {
            "citation_text": "Brown, T., & Troy Inc. (2024). A Romans Story "
            "3. Acme Inc.",
            "is_visible": True,
            "note": "",
            "removal_date": new_edited_version.data["metadata"][
                "publication_date"
            ],
            "removed_by": {"user": "1"},
        },
        "versions": {"index": 2, "is_latest": False},
    }
    monkeypatch.setenv("MOCK_SIGNAL_SUBSCRIBER", "True")

    restored_record = service.restore_record(admin.identity, deleted_record.id)

    # any extra queue events?
    assert (
        len(
            [
                c
                for c in current_queues.queues[
                    "remote-api-provisioning-events"
                ].consume()
            ]
        )
        == 0
    )

    assert os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "rdm_record|restore_record"
    restored_actual_data = {
        k: v
        for k, v in restored_record.data.items()
        if k
        not in [
            "created",
            "updated",
            "links",
        ]
    }
    restored_expected_data = deleted_actual_data.copy()
    del restored_expected_data["tombstone"]
    restored_expected_data["deletion_status"] = {
        "is_deleted": False,
        "status": "P",
    }
    restored_expected_data["revision_id"] = 9
    restored_expected_data["versions"]["is_latest"] = True
    restored_expected_data["versions"]["is_latest_draft"] = True
    assert restored_actual_data == restored_expected_data

    monkeypatch.delenv("MOCK_SIGNAL_SUBSCRIBER")


def test_component_community_publish_signal(
    app,
    minimal_community,
    admin,
    superuser_role_need,
    location,
    community_type_v,
    search,
    search_clear,
    db,
    requests_mock,
    monkeypatch,
    mock_signal_subscriber,
    create_communities_custom_fields,
):
    """Test signal emission for correct community events.

    This should not prompt any remote API operations.
    """

    monkeypatch.setenv("MOCK_SIGNAL_SUBSCRIBER", "True")
    rec_url = list(
        app.config["REMOTE_API_PROVISIONER_EVENTS"]["community"].keys()
    )[0]
    remote_response = {
        "_internal_id": "1234AbCD?",  # can't mock because set at runtime
        "_id": "2E9SqY0Bdd2QL-HGeUuA",
        "title": "My Community",
        "primary_url": "http://works.kcommons.org/records/1234",
    }
    requests_mock.post(
        rec_url,
        json=remote_response,
        headers={"Authorization": "Bearer 12345"},
    )

    service = current_communities.service
    current_app.logger.debug(service)
    current_app.logger.debug(service.config.components[-1])
    current_app.logger.debug(dir(service.config.components[-1]))

    assert admin.user.roles
    current_app.logger.debug(admin.user.roles)
    admin.identity.provides.add(superuser_role_need)

    # Creation,
    # API operations should be prompted
    new = service.create(admin.identity, minimal_community)
    actual_new = new.data
    assert actual_new["metadata"]["title"] == "My Community"
    assert requests_mock.call_count == 1  # user update at token login

    read_record = service.read(admin.identity, actual_new["id"])
    current_app.logger.debug(pformat(read_record.data))
    assert read_record.data["metadata"]["title"] == "My Community"
    assert (
        os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "community|create"
    )  # wasn't set by subscriber
    monkeypatch.setenv("MOCK_SIGNAL_SUBSCRIBER", "True")

    # Edit
    # now this should prompt a remote API operation
    minimal_edited = minimal_community.copy()
    minimal_edited["metadata"]["title"] = "My Community 2"
    # simulate the result of previous remote API operation
    minimal_edited["custom_fields"]["kcr:commons_search_recid"] = (
        remote_response["_id"]
    )
    minimal_edited["custom_fields"][
        "kcr:commons_search_updated"
    ] = arrow.utcnow().format(
        "YYYY-MM-DDTHH:mm:ssZ"
    )  # simulate the result of previous remote API operation

    time.sleep(5)
    edited_new = service.update(system_identity, new.id, minimal_edited)
    actual_edited = edited_new.data
    assert actual_edited["metadata"]["title"] == "My Community 2"
    assert requests_mock.call_count == 1  # user update at token login
    # confirm that no actual calls are being made during test
    assert (
        edited_new.data["custom_fields"].get("kcr:commons_search_recid")
        == remote_response["_id"]
    )
    minimal_edited["custom_fields"][
        "kcr:commons_search_updated"
    ] = arrow.utcnow().format(
        "YYYY-MM-DDTHH:mm:ssZ"
    )  # simulate the result of previous remote API operation
    assert os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "community|update"
    monkeypatch.setenv("MOCK_SIGNAL_SUBSCRIBER", "True")

    read_edited = service.read(admin.identity, edited_new.id)
    assert (
        read_edited.data["custom_fields"].get("kcr:commons_search_recid")
        == remote_response["_id"]
    )
    assert (
        os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "True"
    )  # read doesn't trigger signal

    time.sleep(5)
    deleted = service.delete_community(
        system_identity, read_edited.id, data={}
    )
    assert os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "community|delete"
    # deleted_actual_data = {
    #     k: v
    #     for k, v in deleted.data.items()
    #     if k
    #     not in [
    #         "created",
    #         "updated",
    #         "links",
    #     ]
    # }
    monkeypatch.setenv("MOCK_SIGNAL_SUBSCRIBER", "True")

    time.sleep(5)
    restored = service.restore_community(admin.identity, deleted.id)

    # any extra queue events?
    # assert (
    #     len(
    #         [
    #             c
    #             for c in current_queues.queues[
    #                 "remote-api-provisioning-events"
    #             ].consume()
    #         ]
    #     )
    #     == 0
    # )

    assert os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "community|restore"
    # restored_actual_data = {
    #     k: v
    #     for k, v in restored.data.items()
    #     if k
    #     not in [
    #         "created",
    #         "updated",
    #         "links",
    #     ]
    # }
    # restored_expected_data = deleted_actual_data.copy()
    # del restored_expected_data["tombstone"]
    # restored_expected_data["deletion_status"] = {
    #     "is_deleted": False,
    #     "status": "P",
    # }
    # restored_expected_data["revision_id"] = 9
    # assert restored_actual_data == restored_expected_data

    monkeypatch.delenv("MOCK_SIGNAL_SUBSCRIBER")


def test_ext_on_remote_api_provisioning_triggered(
    app,
    admin,
    minimal_record,
    location,
    search,
    search_clear,
    db,
    monkeypatch,
    requests_mock,
    create_records_custom_fields,
    resource_type_v,
):
    assert admin.user.roles

    from invenio_vocabularies.proxies import current_service as vocabulary_service

    vocab_item = vocabulary_service.read(
        admin.identity, ("resourcetypes", "image-photograph")
    )
    current_app.logger.debug("got vocab item")
    current_app.logger.debug(pformat(vocab_item.data))
    # Temporarily set flag to mock signal subscriber
    # We want to test the signal subscriber with an existing record
    monkeypatch.setenv("MOCK_SIGNAL_SUBSCRIBER", "True")

    # Set up minimal record to update after search provisioning
    service = current_rdm_records.records_service
    record = service.create(admin.identity, minimal_record)
    published_record = service.publish(admin.identity, record.id)
    read_record = service.read(admin.identity, published_record.id)
    assert read_record.data["metadata"]["title"] == "A Romans Story"
    assert os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "rdm_record|publish"

    # Now switch to live signal subscriber to test its behaviour
    monkeypatch.delenv("MOCK_SIGNAL_SUBSCRIBER")

    # Mock remote API response
    mock_response = {
        "_internal_id": read_record.data["id"],
        "_id": "2E9SqY0Bdd2QL-HGeUuA",
        "title": "A Romans Story 2",
        "primary_url": f"http://works.kcommons.org/records/{read_record.data['id']}",
    }
    resp_url = list(
        app.config["REMOTE_API_PROVISIONER_EVENTS"]["rdm_record"].keys()
    )[0]
    requests_mock.post(
        resp_url,
        json=mock_response,
        headers={"Authorization ": "Bearer 12345"},
    )

    # Trigger signal
    owner = {
        "id": "1",
        "email": "admin@inveniosoftware.org",
        "username": "myuser",
        "name": "My User",
        "orcid": "888888",
    }
    events = [
        {
            "service_type": "rdm_record",
            "service_method": "publish",
            "request_url": "https://search.hcommons-dev.org/api/v1/documents",
            "http_method": "POST",
            "payload_object": format_commons_search_payload(
                admin.identity, data=read_record.data, owner=owner
            ),
            "record_id": read_record.data["id"],
            "draft_id": read_record.data["id"],
            "request_headers": {"Authorization": "Bearer 12345"},
        }
    ]
    current_queues.queues["remote-api-provisioning-events"].publish(events)
    remote_api_provisioning_triggered.send(current_app._get_current_object())

    # Check that the remote API was called correctly
    assert (
        requests_mock.call_count == 2
    )  # 1 for user update at token login, 1 for remote API
    h = requests_mock.request_history
    assert h[1].url == resp_url
    assert h[1].method == "POST"
    assert h[1].headers["Authorization"] == "Bearer 12345"
    publish_payload = {
        "_internal_id": read_record.data["id"],
        "content": "",
        "content_type": "work",
        "contributors": [
            {"name": "Troy Brown", "role": ""},
            {"name": "Troy Inc.", "role": ""},
        ],
        "description": "",
        "modified_date": arrow.utcnow().format("YYYY-MM-DD"),
        "network_node": "works",
        "other_urls": [],
        "owner": {
            "name": "",
            "owner_username": None,
            "url": "http://hcommons.org/profiles/None",
        },
        "primary_url": f"http://works.kcommons.org/records/{read_record.data['id']}",
        "publication_date": "2020-06-01",
        "thumbnail_url": "",
        "title": "A Romans Story",
    }
    assert json.loads(h[1].body) == publish_payload

    # Check that the record was updated with the remote API info and timestamp
    current_app.logger.debug(f"Reading final record {read_record.data['id']}")
    final_read_record = service.read(admin.identity, read_record.data["id"])
    assert (
        final_read_record.data["custom_fields"]["kcr:commons_search_recid"]
        == "2E9SqY0Bdd2QL-HGeUuA"
    )
    assert arrow.get(
        final_read_record.data["custom_fields"]["kcr:commons_search_updated"]
    ) >= arrow.utcnow().shift(seconds=-10)


def test_ext_on_remote_api_provisioning_triggered_community(
    app,
    admin,
    superuser_role_need,
    minimal_community,
    location,
    search,
    search_clear,
    db,
    monkeypatch,
    requests_mock,
    create_communities_custom_fields,
    community_type_v,
):
    assert admin.user.roles
    admin.identity.provides.add(superuser_role_need)

    # Temporarily set flag to mock signal subscriber
    # We want to test the signal subscriber with an existing record
    # monkeypatch.setenv("MOCK_SIGNAL_SUBSCRIBER", "True")

    # Mock remote API response
    mock_response = {
        "_internal_id": "",
        "_id": "2E9SqY0Bdd2QL-HGeUuA",
        "title": "My Community",
        "primary_url": "http://works.kcommons.org/collections/my-community",
    }
    resp_url = list(
        app.config["REMOTE_API_PROVISIONER_EVENTS"]["community"].keys()
    )[0]
    requests_mock.post(
        resp_url,
        json=mock_response,
        headers={"Authorization ": "Bearer 12345"},
    )

    # Set up minimal record to update after search provisioning
    service = current_communities.service
    record = service.create(admin.identity, minimal_community)
    read_record = service.read(admin.identity, record.id)
    assert read_record.data["metadata"]["title"] == "My Community"
    # assert os.getenv("MOCK_SIGNAL_SUBSCRIBER") == "community|create"

    # Check that the remote API was called correctly
    assert (
        requests_mock.call_count == 2
    )  # 1 for user update at token login, 1 for remote API
    h = requests_mock.request_history
    assert h[1].url == resp_url
    assert h[1].method == "POST"
    assert h[1].headers["Authorization"] == "Bearer 12345"
    publish_payload = {
        "_internal_id": "",
        "content": "",
        "content_type": "works_collection",
        "contributors": [],
        "description": "",
        "modified_date": arrow.utcnow().format("YYYY-MM-DD"),
        "network_node": "works",
        "other_urls": [],
        "owner": {
            "name": "",
            "owner_username": None,
            "url": "",
        },
        "primary_url": "http://works.kcommons.org/collections/my-collection",
        "publication_date": arrow.utcnow().format("YYYY-MM-DD"),
        "thumbnail_url": "",
        "title": "My Community",
    }
    assert json.loads(h[1].body) == publish_payload

    # Now switch to live signal subscriber to test its behaviour
    # monkeypatch.delenv("MOCK_SIGNAL_SUBSCRIBER")

    # Trigger signal again
    owner = {
        "id": "1",
        "email": "admin@inveniosoftware.org",
        "username": "myuser",
        "name": "My User",
        "orcid": "888888",
    }
    events = [
        {
            "service_type": "community",
            "service_method": "update",
            "request_url": f"https://search.hcommons-dev.org/api/v1/documents/{read_record.data['custom_fields']['kcr:commons_search_recid']}",
            "http_method": "PUT",
            "payload_object": format_commons_search_collection_payload(
                admin.identity, data=read_record.data, owner=owner
            ),
            "record_id": read_record.data["id"],
            "draft_id": read_record.data["id"],  # FIXME: is this right?
            "request_headers": {"Authorization": "Bearer 12345"},
        }
    ]
    current_queues.queues["remote-api-provisioning-events"].publish(events)
    remote_api_provisioning_triggered.send(current_app._get_current_object())

    # Check that the remote API was called correctly
    assert (
        requests_mock.call_count == 2
    )  # 1 for user update at token login, 1 for remote API
    h = requests_mock.request_history
    assert h[1].url == resp_url
    assert h[1].method == "POST"
    assert h[1].headers["Authorization"] == "Bearer 12345"
    publish_payload = {
        "_internal_id": read_record.data["id"],
        "content": "",
        "content_type": "work",
        "contributors": [
            {"name": "Troy Brown", "role": ""},
            {"name": "Troy Inc.", "role": ""},
        ],
        "description": "",
        "modified_date": arrow.utcnow().format("YYYY-MM-DD"),
        "network_node": "works",
        "other_urls": [],
        "owner": {
            "name": "",
            "owner_username": None,
            "url": "http://hcommons.org/profiles/None",
        },
        "primary_url": f"http://works.kcommons.org/records/{read_record.data['id']}",
        "publication_date": "2020-06-01",
        "thumbnail_url": "",
        "title": "A Romans Story",
    }
    assert json.loads(h[1].body) == publish_payload

    # Check that the record was updated with the remote API info and timestamp
    current_app.logger.debug(f"Reading final record {read_record.data['id']}")
    final_read_record = service.read(admin.identity, read_record.data["id"])
    assert (
        final_read_record.data["custom_fields"]["kcr:commons_search_recid"]
        == "2E9SqY0Bdd2QL-HGeUuA"
    )
    assert arrow.get(
        final_read_record.data["custom_fields"]["kcr:commons_search_updated"]
    ) >= arrow.utcnow().shift(seconds=-10)
