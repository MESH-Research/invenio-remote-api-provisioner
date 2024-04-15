# invenio-groups

Copyright 2024 Mesh Research
Contributors: Ian Scott

Social groups integration between the InvenioRDM repository system and a Knowledge Commons instance as a part of *Knowledge Commons Works*.

The package provides the InvenioRDM data structures and service to store metadata about groups created on a Commons instance (such as Knowledge Commons or MLA Commons).

The package also provides integration between Commons groups and InvenioRDM collections. It exposes a `group_collections` API endpoint that can be used for automatic creation of an InvenioRDM record collection linked to a Commons group. Updates to Commons Search for group collection events is not handled in this package but rather in the invenio_remote_api_provisioner package.

(Note: The Knowledge Commons Works instance of InvenioRDM uses the term "collection" in place of the default term "community" employed in standard InvenioRDM installations.)

## Installation

From your InvenioRDM instance directory:

```shell
    pipenv install invenio-groups
```

This will add the package to your Pipfile and install it in your InvenioRDM instance's virtual environment.

## Group Collections Endpoint Usage

```http
https://example.org/api/group_collections
```

The `group_collections` REST API endpoint allows a Commons instance to create, read, modify, or delete a collection in Invenio owned by a Commons group. This endpoint is not configured to receive all of the metadata required to create or modify group collections. Rather, the `group_collections` endpoint receives minimal signals from a Commons Instance and then obtains the full required metadata via an API callback to the Commons instance.

### Endpoint configuration

The configuration variable `GROUP_COLLECTIONS_METADATA_ENDPOINTS` must be provided in the `invenio.cfg` file in order to use this endpoint. This variable should hold a dictionary whose keys are Commons instance names. The value for each key is a dictionary containing the following keys:

| key | value type | required | value |
| --- | ---------- | ----- | ----- |
| `url` | str | Y | The url on the Commons instance where a GET request can retrieve the metadata for a group. The url should include the placeholder `{id}` where the Commons instance id for the requested group should be placed. |
| `token_name` | str (upper case) | Y | The name of the environment variable that will hold the authentication token for requests to the Commons instance url for retrieving group metadata. |
| `placeholder_avatar` | str | N | The filename or last url component that identifies a placeholder avatar in the avatar image url supplied for the Commons group avatar. |

A typical configuration might look like the following:

```python
GROUP_COLLECTIONS_METADATA_ENDPOINTS = {
    "knowledgeCommons": {
            "url": "https://hcommons-dev.org/wp-json/commons/v1/groups/{id}",
            "token_name": "COMMONS_API_TOKEN",
            "placeholder_avatar": "mystery-group.png",
    },
}
```

### Retrieving Group Collection Metadata (GET)

A GET request to this endpoint will retrieve metadata on Invenio collections
that are owned by a Commons group. A request to the bare endpoint without a
group ID or collection slug will return a list of all collections owned by
all Commons groups. (Commons Works collections not linked to a Commons group will not be included. If you wish to query all groups, please use the `communities` API endpoint.)

#### Query parameters

Four optional query parameters can be used to filter the results:

| Parameter name | Description |
| ---------------|------------ |
| `commons_instance` | the name of the Commons instance to which the group belongs. If this parameter is provided, the response will only include collections owned by groups in that instance. |
| `commons_group_id` | the ID of the Commons group. If this parameter is provided, the response will only include collections owned by that group. |
| `collection` | the slug of the collection. If this parameter is provided, the response will include only metadata for that collection. |
| `page` | the page number of the results |
| `size` | the number of results to include on each page |
| `sort` | the kind of sorting applied to the returned results |

###### Sorting

The `sort` parameter can be set to one of the following sort types:

| Field name | Description |
| -----------|-------------|
| newest | Descending order based on `created` date |
| oldest | Ascending order based on `created` date |
| updated-desc | Descending order based on `updated` date |
| updated-asc | Ascending order based on `updated` date |

By default the results are sorted by `updated-desc`

###### Pagination

Long result sets will be paginated. The response will include urls for the `first`, `last`, `previous`, and `next` pages of results in the `link` property of the response body. A url for the current page of results will also be included in the list as a `self` link. By default the page size is 25, but this can be changed by providing a value for the `size` query parameter.

#### Requesting all collections

###### Request

```http
GET https://example.org/api/group_collections HTTP/1.1
```

###### Successful Response Status Code

`200 OK`

###### Successful response body

```json
{
    "aggregations": {
        "type": {
            "buckets": [
                {
                    "doc_count": 50,
                    "is_selected": False,
                    "key": "event",
                    "label": "Event",
                },
                {
                    "doc_count": 50,
                    "is_selected": False,
                    "key": "organization",
                    "label": "Organization",
                },
            ],
            "label": "Type",
        },
        "visibility": {
            "buckets": [
                {
                    "doc_count": 100,
                    "is_selected": False,
                    "key": "public",
                    "label": "Public",
                }
            ],
            "label": "Visibility",
        },
    },
    "hits": {
        "hits": [
            {
                "id": "5402d72b-b144-4891-aa8e-1038515d68f7",
                "access": {
                    "member_policy": "open",
                    "record_policy": "open",
                    "review_policy": "closed",
                    "visibility": "public",
                },
                "children": {"allow": False},
                "created": "2024-01-01T00:00:00Z",
                "updated": "2024-01-01T00:00:00Z",
                "links": {
                    "self": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7",
                    "self_html": "https://example.org/communities/panda-group-collection",
                    "settings_html": "https://example.org/communities/panda-group-collection/settings",
                    "logo": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/logo",
                    "rename": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/rename",
                    "members": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/members",
                    "public_members": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/members/public",
                    "invitations": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/invitations",
                    "requests": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/requests",
                    "records": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/records",
                    "featured": "https://example.org/api/"
                                "communities/"
                                "5402d72b-b144-4891-aa8e-1038515d68f7/"
                                "featured",
                },
                "revision_id": 1,
                "slug": "panda-group-collection",
                "metadata": {
                    "title": "The Panda Group Collection",
                    "curation_policy": "Curation policy",
                    "page": "Information for the panda group collection",
                    "description": "This is a collection about pandas.",
                    "website": "https://example.org/pandas",
                    "organizations": [
                        {
                            "name": "Panda Research Institute",
                        }
                    ],
                    "size": 100,
                },
                "deletion_status": {
                    "is_deleted": False,
                    "status": "P",
                },
                "custom_fields": {
                    "kcr:commons_instance": "knowledgeCommons",
                    "kcr:commons_group_description": "This is a group for panda research.",
                    "kcr:commons_group_id": "12345",
                    "kcr:commons_group_name": "Panda Research Group",
                    "kcr:commons_group_visibility": "public",
                },
                "access": {
                    "visibility": "public",
                    "member_policy": "closed",
                    "record_policy": "open",
                    "review_policy": "open",
                }
            },
            /* ... */
        ],
        "total": 100,
    },
    "links": {
        "self": "https://example.org/api/group_collections",
        "first": "https://example.org/api/group_collections?page=1",
        "last": "https://example.org/api/group_collections?page=10",
        "prev": "https://example.org/api/group_collections?page=1",
        "next": "https://example.org/api/group_collections?page=2",
    }
    "sortBy": "newest",
    "order": "ascending",
}
```

###### Successful Response Headers

| Header name | Header value |
| ------------|-------------- |
| Content-Type | `application/json` |

#### Requesting collections for a Commons instance

###### Request

```http
GET https://example.org/api/group_collections?commons_instance=knowledgeCommons&sort=updated-asc HTTP/1.1
```

###### Successful response status code

`200 OK`

###### Successful Response Body:

```json
{
    "aggregations": {
        "type": {
            "buckets": [
                {
                    "doc_count": 45,
                    "is_selected": False,
                    "key": "event",
                    "label": "Event",
                },
                {
                    "doc_count": 45,
                    "is_selected": False,
                    "key": "organization",
                    "label": "Organization",
                },
            ],
            "label": "Type",
        },
        "visibility": {
            "buckets": [
                {
                    "doc_count": 90,
                    "is_selected": False,
                    "key": "public",
                    "label": "Public",
                }
            ],
            "label": "Visibility",
        },
    },
    "hits": {
        "hits": [
            {
                "id": "5402d72b-b144-4891-aa8e-1038515d68f7",
                "access": {
                    "member_policy": "open",
                    "record_policy": "open",
                    "review_policy": "closed",
                    "visibility": "public",
                },
                "children": {"allow": False},
                "created": "2024-01-01T00:00:00Z",
                "updated": "2024-01-01T00:00:00Z",
                "links": {
                    "self": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7",
                    "self_html": "https://example.org/communities/panda-group-collection",
                    "settings_html": "https://example.org/communities/panda-group-collection/settings",
                    "logo": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/logo",
                    "rename": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/rename",
                    "members": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/members",
                    "public_members": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/members/public",
                    "invitations": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/invitations",
                    "requests": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/requests",
                    "records": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/records",
                    "featured": "https://example.org/api/"
                                "communities/"
                                "5402d72b-b144-4891-aa8e-1038515d68f7/"
                                "featured",
                },
                "revision_id": 1,
                "slug": "panda-group-collection",
                "metadata": {
                    "title": "The Panda Group Collection",
                    "curation_policy": "Curation policy",
                    "page": "Information for the panda group collection",
                    "description": "This is a collection about pandas.",
                    "website": "https://example.org/pandas",
                    "organizations": [
                        {
                            "name": "Panda Research Institute",
                        }
                    ],
                    "size": 100,
                },
                "deletion_status": {
                    "is_deleted": False,
                    "status": "P",
                },
                "custom_fields": {
                    "kcr:commons_instance": "knowledgeCommons",
                    "kcr:commons_group_description": "This is a group for panda research.",
                    "kcr:commons_group_id": "12345",
                    "kcr:commons_group_name": "Panda Research Group",
                    "kcr:commons_group_visibility": "public",
                },
                "access": {
                    "visibility": "public",
                    "member_policy": "closed",
                    "record_policy": "open",
                    "review_policy": "open",
                }
            },
            ...
        ],
        "total": 90,
    },
    "links": {
        "self": "https://example.org/api/group_collections?commons_instance=knowledgeCommons",
        "first": "https://example.org/api/group_collections?commons_instance=knowledgeCommons&page=1",
        "last": "https://example.org/api/group_collections?commons_instance=knowledgeCommons&page=9",
        "prev": "https://example.org/api/group_collections?commons_instance=knowledgeCommons&page=1",
        "next": "https://example.org/api/group_collections?commons_instance=knowledgeCommons&page=2",
    }
    "sortBy": "updated-asc",
}
```

###### Successful response headers

| Header name | Header value |
| ------------|-------------- |
| Content-Type | `application/json` |
| Link | `<https://example.org/api/group_collections?commons_instance=knowledgeCommons&page=1>; rel="first", <https://example.org/api/group_collections?commons_instance=knowledgeCommons&page=9>; rel="last", <https://example.org/api/group_collections?commons_instance=knowledgeCommons&page=1>; rel="prev", <https://example.org/api/group_collections?commons_instance=knowledgeCommons&page=2>; rel="next"` |


#### Requesting collections for a specific group

Note that if you specify a `commons_group_id` value, you must *also* provide a `commons_instance` value. This is to avoid confusion if different Commons instances use the same internal id for groups.

###### Request

```http
GET https://example.org/api/group_collections?commons_instance=knowledgeCommons&commons_group_id=12345 HTTP/1.1
```

###### Successful response status code

`200 OK`

###### Successful Response Body:

```json
{
    "aggregations": {
        "type": {
            "buckets": [
                {
                    "doc_count": 2,
                    "is_selected": False,
                    "key": "event",
                    "label": "Event",
                },
                {
                    "doc_count": 2,
                    "is_selected": False,
                    "key": "organization",
                    "label": "Organization",
                },
            ],
            "label": "Type",
        },
        "visibility": {
            "buckets": [
                {
                    "doc_count": 4,
                    "is_selected": False,
                    "key": "public",
                    "label": "Public",
                }
            ],
            "label": "Visibility",
        },
    },
    "hits": {
        "hits": [
            {
                "id": "5402d72b-b144-4891-aa8e-1038515d68f7",
                "access": {
                    "member_policy": "open",
                    "record_policy": "open",
                    "review_policy": "closed",
                    "visibility": "public",
                },
                "children": {"allow": False},
                "created": "2024-01-01T00:00:00Z",
                "updated": "2024-01-01T00:00:00Z",
                "links": {
                    "self": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7",
                    "self_html": "https://example.org/communities/panda-group-collection",
                    "settings_html": "https://example.org/communities/panda-group-collection/settings",
                    "logo": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/logo",
                    "rename": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/rename",
                    "members": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/members",
                    "public_members": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/members/public",
                    "invitations": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/invitations",
                    "requests": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/requests",
                    "records": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/records",
                    "featured": "https://example.org/api/"
                                "communities/"
                                "5402d72b-b144-4891-aa8e-1038515d68f7/"
                                "featured",
                },
                "revision_id": 1,
                "slug": "panda-group-collection",
                "metadata": {
                    "title": "The Panda Group Collection",
                    "curation_policy": "Curation policy",
                    "page": "Information for the panda group collection",
                    "description": "This is a collection about pandas.",
                    "website": "https://example.org/pandas",
                    "organizations": [
                        {
                            "name": "Panda Research Institute",
                        }
                    ],
                    "size": 2,
                },
                "deletion_status": {
                    "is_deleted": False,
                    "status": "P",
                },
                "custom_fields": {
                    "kcr:commons_instance": "knowledgeCommons",
                    "kcr:commons_group_description": "This is a group for panda research.",
                    "kcr:commons_group_id": "12345",
                    "kcr:commons_group_name": "Panda Research Group",
                    "kcr:commons_group_visibility": "public",
                },
                "access": {
                    "visibility": "public",
                    "member_policy": "closed",
                    "record_policy": "open",
                    "review_policy": "open",
                }
            },
            ...
        ],
        "total": 4,
    },
    "links": {
        "self": "https://example.org/api/group_collections",
        "first": "https://example.org/api/group_collections?page=1",
        "last": "https://example.org/api/group_collections?page=1",
        "prev": "https://example.org/api/group_collections?page=1",
        "next": "https://example.org/api/group_collections?page=1",
    }
    "sortBy": "newest",
}
```

###### Successful response headers

| Header name | Header value |
| ------------|-------------- |
| Content-Type | `application/json` |

#### Requesting a specific collection

While other kinds of requests require query parameters, a request for metadata on a specific Commons Works collection can be made by simply adding the community's slug to the end of the url path. Once again, this will only succeed for collections that are linked to a Commons instance group. Collections that exist independently on Knowledge Commons Works will not be found at the `group_collections` endpoint and should be requested at the `communities` endpoint instead.

###### Request

```http
GET https://example.org/api/group_collections/my-collection-slug HTTP/1.1
```

###### Successful Response Status Code

`200 OK`

###### Successful Response Body:

```json
{
    "id": "5402d72b-b144-4891-aa8e-1038515d68f7",
    "created": "2024-01-01T00:00:00Z",
    "updated": "2024-01-01T00:00:00Z",
    "links": {
        "self": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7",
        "self_html": "https://example.org/communities/panda-group-collection",
        "settings_html": "https://example.org/communities/panda-group-collection/settings",
        "logo": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/logo",
        "rename": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/rename",
        "members": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/members",
        "public_members": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/members/public",
        "invitations": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/invitations",
        "requests": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/requests",
        "records": "https://example.org/api/communities/5402d72b-b144-4891-aa8e-1038515d68f7/records",
        "featured": "https://example.org/api/"
                    "communities/"
                    "5402d72b-b144-4891-aa8e-1038515d68f7/"
                    "featured",
    },
    "revision_id": 1,
    "slug": "panda-group-collection",
    "metadata": {
        "title": "The Panda Group Collection",
        "curation_policy": "Curation policy",
        "page": "Information for the panda group collection",
        "description": "This is a collection about pandas.",
        "website": "https://example.org/pandas",
        "organizations": [
            {
                "name": "Panda Research Institute",
            }
        ],
        "size": 100,
    },
    "deletion_status": {
        "is_deleted": False,
        "status": "P",
    },
    "custom_fields": {
        "kcr:commons_instance": "knowledgeCommons",
        "kcr:commons_group_description": "This is a group for pandas research.",
        "kcr:commons_group_id": "12345",
        "kcr:commons_group_name": "Panda Research Group",
        "kcr:commons_group_visibility": "public",
    },
    "access": {
        "visibility": "public",
        "member_policy": "closed",
        "record_policy": "open",
        "review_policy": "open",
    }
}
```


### Creating a Collection for a Group (POST)

A POST request to this endpoint creates a new collection in Invenio owned by the specified Commons group. If the collection is successfully created, the response status code will be 201 Created, and the response body will be a JSON object containing the URL slug for the newly created collection.

The POST request will trigger a callback to the Commons instance to get the metadata for the specified group, using the configuration dictionary declared in the `GROUP_COLLECTIONS_METADATA_ENDPOINTS` config variable, under the key matching the Commons instance's SAML IDP provider name (declared in the `SSO_SAML_IDPS` config variable). This callback request will be sent to the "url" specified in the configuration dictionary (e.g., `GROUP_COLLECTIONS_METADATA_ENDPOINTS["knowledgeCommons"]["url"]`). This request will be authenticated using the environment variable whose name matches the `token_name` from the same configuration dictionary. The metadata from this callback request will then be used to populate the collection metadata in Invenio.

If the metadata returned from the Commons instance includes a url for an avatar, that avatar will be downloaded and stored in the Invenio instance's file storage. Since we do not want to use a placeholder avatar for the group, the instance's configuration can include a `placeholder_avatar` key. If the file name or last segment of the supplied avatar url matches this `placeholder_avatar` value, it will be ignored.

#### Handling collection name collisions

It is possible for two groups on Commons instances to share the same human readable name, even though their ids are different. Knowledge Commons Works *will* allow multiple collections to share identical human readable names, but group url *slugs* must be unique across all KCW collections. So where group names collide, only the first of the identically-named collections will have its slug generated normally. Susequent collections with the same name will have a numerical disambiguator appended to the end of their slugs. So if we have three groups named "Panda Studies," the first collection created for one of the groups will have the slug `panda-studies`. The other collections created by these groups will be assigned the slugs `panda-studies-1` and `panda-studies-2`, in order of their creation in Knowledge Commons Works.

#### Request

```http
POST https://example.org/api/group_collections HTTP/1.1
```

#### Request body

```json
{
    "commons_instance": "knowledgeCommons",
    "commons_group_id": "12345",
    "commons_group_name": "Panda Research Group",
    "commons_group_visibility": "public",
}
```

#### Successful response status code

`201 Created`

#### Successful response body

```json
{
    "commons_group_id": "12345",
    "collection_slug": "new-collection-slug"
}
```

#### Unsuccessful response codes

- 400 Bad Request: The request body is missing required fields or contains
    invalid data.
- 404 Not Found: The specified group could not be found by the callback to the Commons instance.
- 403 Forbidden: The request is not authorized to modify the collection.
- 409 Conflict: A collection already exists in Knowledge Commons Works linked to the specified group.

### Changing the Group Ownership of a Collection (PATCH)

[!WARNING]
PATCH requests to change group ownership of the collection are not yet implemented.

A PATCH request to this endpoint modifies an existing collection in Invenio by changing the Commons group to which it belongs. This is the *only* modification that can be made to a collection via this endpoint. Other modifications to Commons group metadata should be handled by signalling the Invenio webhook for commons group metadata updates. Modifications to internal metadata or settings for the Invenio collection should be made view the Invenio "communities" API or the collection settings UI.

Note that the collection memberships in Invenio will be automatically transferred to the new Commons group. The corporate roles for the old Commons group will be removed from the collection and corporate roles for the new Commons group will be added to its membership with appropriate permissions. But any individual memberships that have been granted through the Invenio UI will be left unchanged. If the new collection administrators wish to change these individual memberships, they will need to do so through the Invenio UI.

#### Request

```http
PATCH https://example.org/api/group_collections/my-collection-slug HTTP/1.1
```

#### Successful request body

```json
{
    "commons_instance": "knowledgeCommons",
    "old_commons_group_id": "12345",
    "new_commons_group_id": "67890",
    "new_commons_group_name": "My Group",
    "new_commons_group_visibility": "public",
}
```

#### Successful response status code

`200 OK`

#### Successful response body

```json
{
    "collection": "my-collection-slug"
    "old_commons_group_id": "12345",
    "new_commons_group_id": "67890",
}
```

#### Unsuccessful response codes

- 400 Bad Request: The request body is missing required fields or contains
    invalid data.
- 404 Not Found: The collection does not exist.
- 403 Forbidden: The request is not authorized to modify the collection.
- 304 Not Modified: The collection is already owned by the specified
    Commons group.

### Deleting a Group's Collection (DELETE)

A DELETE request to this endpoint deletes a collection in Invenio owned by the specified Commons group. Note that the request must include all of:

- the collection slug as the url path parameter
- the identifier of the Commons instance to which the group belongs, in the `commons_instance` query parameter
- the Commons identifier of the group which owns the collection, in the `commons_group_id` query parameter

If any of these is missing the request will fail with a `400 Bad Request` error. This is to ensure that collections are not deleted accidentally or by agents without authorization.

If the collection is successfully deleted, the response status code will be 204 No Content.

[!NOTE]
Once a group collection has been deleted, its former URL slug is still registered in Invenio's PID store and reserved for the (now deleted) collection. Subsequent requests to create a collection for the same group cannot re-use the same URL slug. Instead the new slug will have a numerical disambiguator added to the end, exactly as in cases of group name collision. E.g., if the group `panda-studies` were deleted earlier, a request to create a new collection for the "Panda Studies" group would be assigned the URL slug `panda-studies-1`.

[!NOTE]
Group collections are soft deleted and can in principle be restored within a short period after the delete signal has been sent. Eventually, though, the soft deleted collection records will be
automatically purged entirely from the database. There is also no API mechanism for restoring them. So delete operations should be regarded as permanent and irrevocable.

#### Request

```http
DELETE https://example.org/api/group_collections/my-collection-slug?commons_instance=knowledgeCommons&commons_group_id=12345 HTTP/1.1
```

#### Successful response status code

`204 No Content`

#### Unsuccessful response codes

- 400 Bad Request: The request did not include the required parameters or the parameters are not well formed.
- 403 Forbidden: The requesting agent is not authorized to delete the collection. The collection may not belong to the Commons instance making the request, or it may not belong to the specified Commons group.
- 404 Not Found: The collection does not exist.
- 422 UnprocessableEntity: The deletion could not be performed because the

### Logging

The module will log each POST, PATCH, or DELETE request to the `group_collections` endpoint (as well as any errors) in a dedicated log file, `logs/invenio-group-collections.log`.

### Endpoint security

The endpoint is secured by a token that must be obtained by the Commons instance administrator from the Knowledge Commons Works administrator. The token must be provided in the "Authorization" request header.


## Versions

This repository follows [calendar versioning](https://calver.org/):

`2021.06.18` is both a valid semantic version and an indicator of the year-month corresponding to the loaded FAST terms.
