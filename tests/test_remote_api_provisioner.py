from invenio_rdm_records.proxies import current_rdm_records
import pytest  # noqa
import requests  # noqa


def test_extension(app, search_clear):
    assert "invenio-remote-api-provisioner" in app.extensions


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


def test_component(
    app,
    minimal_record,
    superuser_identity,
    location,
    resource_type_v,
    search_clear,
    minimal_record_create_result,
    minimal_record_update_result,
    minimal_record_publish_result,
    db,
    requests_mock,
):
    """Test draft creation.

    This should not prompt any remote API operations.
    """

    requests_mock.post("https://hcommons.org/api/v1/search_update", text="OK")
    service = current_rdm_records.records_service

    # No remote API operations should be prompted
    draft = service.create(superuser_identity, minimal_record)
    actual_draft = draft.data
    assert actual_draft["metadata"]["title"] == "A Romans Story"
    db.session.commit()

    # No remote API operations should be prompted
    minimal_edited = minimal_record.copy()
    minimal_edited["metadata"]["title"] = "A Romans Story 2"
    edited_draft = service.update_draft(
        superuser_identity, draft.id, minimal_record
    )
    actual_edited = edited_draft.data
    assert actual_edited["metadata"]["title"] == "A Romans Story 2"
    db.session.commit()

    # Now this should prompt a remote API operation
    record = service.publish(superuser_identity, edited_draft.id)
    actual_published = record.data
    assert actual_published["metadata"]["title"] == "A Romans Story 2"

    db.session.commit()

    # new version

    # deleted_record = service.delete(superuser_identity, record.id)

    # assert deleted_record == {}

    # restored_record = service.restore_record(superuser_identity, record.id)

    # assert restored_record == {}
