# FORK: tests for the advanced list API endpoints — smart rules,
# collaborators, reorder, recommendations, and activity.
from http import HTTPStatus as HTTP  # noqa: N814

from django.test import SimpleTestCase

from api.schema_contract import generate_schema_contract
from app.models import MediaTypes
from lists.models import (
    CustomList,
    CustomListItem,
    ListActivity,
    ListRecommendation,
)

from .base import FloppyApiTestCase


class SmartRulesTests(FloppyApiTestCase):
    """GET/PUT smart-rules and POST smart-sync."""

    def setUp(self):
        """Create a smart list matching the user's movies."""
        super().setUp()
        self.smart_list = CustomList.objects.create(
            name="Smart Movies",
            owner=self.user1,
            is_smart=True,
            smart_media_types=[MediaTypes.MOVIE.value],
        )

    def test_get_rules(self):
        """The smart configuration is returned."""
        response = self.call_api(
            "get",
            "api_list_smart_rules",
            args=(self.smart_list.id,),
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.OK)
        self.assertTrue(response.json()["is_smart"])

    def test_put_rules_syncs_membership(self):
        """PUT normalizes rules and syncs items into the list."""
        response = self.call_api(
            "put",
            "api_list_smart_rules",
            args=(self.smart_list.id,),
            payload={"media_types": [MediaTypes.MOVIE.value]},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.OK)
        # The base fixtures track three movies for user1.
        self.assertEqual(response.json()["items_count"], 3)

    def test_put_rules_accepts_episode_media_type(self):
        """Episode is a first-class smart-rule media type and round-trips."""
        response = self.call_api(
            "put",
            "api_list_smart_rules",
            args=(self.smart_list.id,),
            payload={"media_types": [MediaTypes.EPISODE.value]},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.OK)
        self.assertEqual(
            response.json()["rules"]["media_types"],
            [MediaTypes.EPISODE.value],
        )

        self.smart_list.refresh_from_db()
        self.assertEqual(
            self.smart_list.smart_media_types,
            [MediaTypes.EPISODE.value],
        )

    def test_put_on_regular_list_rejected(self):
        """PUT smart-rules on a non-smart list returns 400."""
        regular = self.lists_by_name["favorites"]
        response = self.call_api(
            "put",
            "api_list_smart_rules",
            args=(regular.id,),
            payload={"media_types": []},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.BAD_REQUEST)

    def test_smart_sync(self):
        """POST smart-sync repopulates membership."""
        response = self.call_api(
            "post",
            "api_list_smart_sync",
            args=(self.smart_list.id,),
            payload={},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.OK)
        self.assertEqual(response.json()["items_count"], 3)

    def test_other_users_list_not_found(self):
        """Another user's private list 404s."""
        response = self.call_api(
            "get",
            "api_list_smart_rules",
            args=(self.lists_by_name["user2_private"].id,),
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.NOT_FOUND)


class CollaboratorTests(FloppyApiTestCase):
    """GET/PUT collaborators."""

    def test_get_collaborators(self):
        """The shared fixture list reports its collaborator."""
        response = self.call_api(
            "get",
            "api_list_collaborators",
            args=(self.lists_by_name["shared"].id,),
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.OK)
        payload = response.json()
        self.assertEqual(payload["owner"], self.user1.username)
        self.assertIn(self.user2.username, payload["collaborators"])

    def test_put_replaces_collaborators(self):
        """PUT sets the collaborator list and logs activity."""
        favorites = self.lists_by_name["favorites"]
        response = self.call_api(
            "put",
            "api_list_collaborators",
            args=(favorites.id,),
            payload={"usernames": [self.user2.username]},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.OK)
        self.assertEqual(response.json()["collaborators"], [self.user2.username])
        self.assertTrue(
            ListActivity.objects.filter(
                custom_list=favorites,
                activity_type="collaborator_added",
            ).exists(),
        )

        cleared = self.call_api(
            "put",
            "api_list_collaborators",
            args=(favorites.id,),
            payload={"usernames": []},
            headers=self.auth_headers,
        )
        self.assertEqual(cleared.json()["collaborators"], [])

    def test_unknown_username_rejected(self):
        """Unknown usernames return 404 with the missing names."""
        response = self.call_api(
            "put",
            "api_list_collaborators",
            args=(self.lists_by_name["favorites"].id,),
            payload={"usernames": ["nobody-here"]},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.NOT_FOUND)
        self.assertEqual(response.json()["missing"], ["nobody-here"])


class ReorderTests(FloppyApiTestCase):
    """Reorder endpoints."""

    def _ordered_item_ids(self, custom_list):
        return [
            entry.item_id
            for entry in CustomListItem.objects.filter(
                custom_list=custom_list,
            ).order_by("date_added", "id")
        ]

    def test_reorder_action_moves_item(self):
        """POST reorder moves an item to the front."""
        favorites = self.lists_by_name["favorites"]
        original = self._ordered_item_ids(favorites)
        if len(original) < 2:
            self.skipTest("Fixture list has fewer than two items")
        response = self.call_api(
            "post",
            "api_list_items_reorder",
            args=(favorites.id,),
            payload={"item_id": original[-1], "action": "first"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.NO_CONTENT)
        reordered = self._ordered_item_ids(favorites)
        self.assertEqual(reordered[0], original[-1])

    def test_full_order_replacement(self):
        """PUT order applies a full custom order."""
        favorites = self.lists_by_name["favorites"]
        original = self._ordered_item_ids(favorites)
        if len(original) < 2:
            self.skipTest("Fixture list has fewer than two items")
        desired = list(reversed(original))
        response = self.call_api(
            "put",
            "api_list_items_order",
            args=(favorites.id,),
            payload={"item_ids": desired},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.NO_CONTENT)
        self.assertEqual(self._ordered_item_ids(favorites), desired)

    def _put_order(self, custom_list, payload, headers=None):
        return self.call_api(
            "put",
            "api_list_items_order",
            args=(custom_list.id,),
            payload=payload,
            headers=headers or self.auth_headers,
        )

    def _post_reorder(self, custom_list, payload):
        return self.call_api(
            "post",
            "api_list_items_reorder",
            args=(custom_list.id,),
            payload=payload,
            headers=self.auth_headers,
        )

    def test_full_order_subset_keeps_other_items_in_place(self):
        """A subset takes the slots it occupies; the other items do not move."""
        favorites = self.lists_by_name["favorites"]
        first, middle, last = self._ordered_item_ids(favorites)

        response = self._put_order(favorites, {"item_ids": [last, first]})

        self.assertEqual(response.status_code, HTTP.NO_CONTENT)
        self.assertEqual(self._ordered_item_ids(favorites), [last, middle, first])

    def test_full_order_accepts_numeric_strings(self):
        """Ids sent as numeric strings are the same ids."""
        favorites = self.lists_by_name["favorites"]
        original = self._ordered_item_ids(favorites)

        response = self._put_order(
            favorites,
            {"item_ids": [str(item_id) for item_id in reversed(original)]},
        )

        self.assertEqual(response.status_code, HTTP.NO_CONTENT)
        self.assertEqual(self._ordered_item_ids(favorites), original[::-1])

    def test_full_order_rejects_bad_ids_without_changing_the_list(self):
        """Duplicates, unknown, foreign-list and malformed ids change nothing."""
        favorites = self.lists_by_name["favorites"]
        original = self._ordered_item_ids(favorites)
        foreign = self._ordered_item_ids(self.lists_by_name["watching"])[0]
        cases = {
            "missing": {},
            "empty": {"item_ids": []},
            "not a list": {"item_ids": original[0]},
            "not integers": {"item_ids": ["abc"]},
            "unknown id": {"item_ids": [original[2], 999999, original[0]]},
            "foreign list id": {"item_ids": [original[2], foreign]},
            "duplicate": {"item_ids": [original[2], original[2], original[0]]},
        }
        for label, payload in cases.items():
            with self.subTest(label):
                response = self._put_order(favorites, payload)

                self.assertEqual(response.status_code, HTTP.BAD_REQUEST)
                self.assertIn("detail", response.json())
                self.assertEqual(self._ordered_item_ids(favorites), original)

    def test_full_order_unknown_list_or_no_access_is_not_found(self):
        """A list the caller cannot see answers 404."""
        response = self._put_order(
            self.lists_by_name["favorites"],
            {"item_ids": [1]},
            headers={"HTTP_X_API_KEY": self.user2.token},
        )

        self.assertEqual(response.status_code, HTTP.NOT_FOUND)

    def test_reorder_action_is_case_insensitive(self):
        """The action is accepted in any case with surrounding spaces."""
        favorites = self.lists_by_name["favorites"]
        original = self._ordered_item_ids(favorites)

        response = self._post_reorder(
            favorites,
            {"item_id": str(original[-1]), "action": " First "},
        )

        self.assertEqual(response.status_code, HTTP.NO_CONTENT)
        self.assertEqual(self._ordered_item_ids(favorites)[0], original[-1])

    def test_reorder_rejects_invalid_requests(self):
        """A missing, malformed or unknown field is 400; an outside item 404."""
        favorites = self.lists_by_name["favorites"]
        original = self._ordered_item_ids(favorites)
        foreign = self._ordered_item_ids(self.lists_by_name["watching"])[0]
        bad_requests = {
            "no action": {"item_id": original[0]},
            "no item": {"action": "first"},
            "bad action": {"item_id": original[0], "action": "top"},
            "bad item": {"item_id": "abc", "action": "first"},
        }
        for label, payload in bad_requests.items():
            with self.subTest(label):
                response = self._post_reorder(favorites, payload)

                self.assertEqual(response.status_code, HTTP.BAD_REQUEST)
                self.assertIn("errors", response.json())

        response = self._post_reorder(favorites, {"item_id": foreign, "action": "first"})

        self.assertEqual(response.status_code, HTTP.NOT_FOUND)
        self.assertEqual(self._ordered_item_ids(favorites), original)


class ReorderSchemaTests(SimpleTestCase):
    """The published schema describes both reorder request bodies."""

    @classmethod
    def setUpClass(cls):
        """Generate the schema served at /api/schema/ once."""
        super().setUpClass()
        cls.schema = generate_schema_contract().schema

    def _operation(self, path, method):
        return self.schema["paths"][f"/api/v1/lists/{{list_id}}/items/{path}/"][method]

    def _request_schema(self, operation):
        content = operation["requestBody"]["content"]["application/json"]
        name = content["schema"]["$ref"].rsplit("/", 1)[-1]
        return self.schema["components"]["schemas"][name]

    def test_order_request_body_requires_a_nonempty_list_of_ids(self):
        """PUT order documents item_ids and how they are interpreted."""
        operation = self._operation("order", "put")
        body = self._request_schema(operation)

        self.assertEqual(body["required"], ["item_ids"])
        item_ids = body["properties"]["item_ids"]
        self.assertEqual(item_ids["type"], "array")
        self.assertEqual(item_ids["items"]["type"], "integer")
        self.assertEqual(item_ids["minItems"], 1)
        for phrase in ("subset", "once", "belong to this list", "400"):
            self.assertIn(phrase, item_ids["description"])
        self.assertIn("204", operation["responses"])
        for status in ("400", "401", "403", "404"):
            self.assertIn(status, operation["responses"])

    def test_reorder_request_body_requires_item_id_and_action(self):
        """POST reorder documents item_id and the allowed actions."""
        operation = self._operation("reorder", "post")
        body = self._request_schema(operation)
        action = body["properties"]["action"]
        action_enum = self.schema["components"]["schemas"][
            action["allOf"][0]["$ref"].rsplit("/", 1)[-1]
        ]

        self.assertEqual(sorted(body["required"]), ["action", "item_id"])
        self.assertEqual(body["properties"]["item_id"]["type"], "integer")
        self.assertEqual(action_enum["enum"], ["first", "back", "next", "last"])
        self.assertIn("204", operation["responses"])
        for status in ("400", "401", "403", "404"):
            self.assertIn(status, operation["responses"])


class RecommendationTests(FloppyApiTestCase):
    """Recommendation submit/list/approve/deny and activity."""

    def setUp(self):
        """Make the favorites list public with recommendations enabled."""
        super().setUp()
        self.rec_list = self.lists_by_name["favorites"]
        self.rec_list.visibility = "public"
        self.rec_list.allow_recommendations = True
        self.rec_list.save(update_fields=["visibility", "allow_recommendations"])
        self.candidate = self.items_by_type[MediaTypes.MOVIE.value][2]
        CustomListItem.objects.filter(
            custom_list=self.rec_list,
            item=self.candidate,
        ).delete()

    def _submit(self, headers=None):
        return self.call_api(
            "post",
            "api_list_recommendations",
            args=(self.rec_list.id,),
            payload={
                "media_id": self.candidate.media_id,
                "media_type": self.candidate.media_type,
                "source": self.candidate.source,
                "note": "you would like this",
            },
            headers=headers or self.auth_headers2,
        )

    def test_submit_list_and_approve(self):
        """A recommendation can be submitted, listed, and approved."""
        submitted = self._submit()
        self.assertEqual(submitted.status_code, HTTP.CREATED)
        rec_id = submitted.json()["id"]

        listed = self.call_api(
            "get",
            "api_list_recommendations",
            args=(self.rec_list.id,),
            headers=self.auth_headers,
        )
        self.assertEqual(listed.status_code, HTTP.OK)
        self.assertEqual(len(listed.json()["results"]), 1)

        approved = self.call_api(
            "post",
            "api_list_recommendation_decision",
            args=(self.rec_list.id, rec_id, "approve"),
            payload={},
            headers=self.auth_headers,
        )
        self.assertEqual(approved.status_code, HTTP.OK)
        self.assertTrue(approved.json()["added"])
        self.assertTrue(
            self.rec_list.items.filter(id=self.candidate.id).exists(),
        )
        self.assertFalse(ListRecommendation.objects.filter(id=rec_id).exists())

    def test_deny_removes_recommendation(self):
        """Denying deletes the recommendation without adding the item."""
        rec_id = self._submit().json()["id"]
        denied = self.call_api(
            "post",
            "api_list_recommendation_decision",
            args=(self.rec_list.id, rec_id, "deny"),
            payload={},
            headers=self.auth_headers,
        )
        self.assertEqual(denied.status_code, HTTP.OK)
        self.assertFalse(self.rec_list.items.filter(id=self.candidate.id).exists())

    def test_duplicate_submission_conflict(self):
        """Submitting the same item twice returns 409."""
        self._submit()
        response = self._submit()
        self.assertEqual(response.status_code, HTTP.CONFLICT)

    def test_recommendations_disabled_rejected(self):
        """Lists without recommendations enabled reject submissions."""
        self.rec_list.allow_recommendations = False
        self.rec_list.save(update_fields=["allow_recommendations"])
        response = self._submit()
        self.assertEqual(response.status_code, HTTP.BAD_REQUEST)

    def test_activity_log(self):
        """Approvals appear in the activity log."""
        rec_id = self._submit().json()["id"]
        self.call_api(
            "post",
            "api_list_recommendation_decision",
            args=(self.rec_list.id, rec_id, "approve"),
            payload={},
            headers=self.auth_headers,
        )
        response = self.call_api(
            "get",
            "api_list_activity",
            args=(self.rec_list.id,),
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, HTTP.OK)
        types = [row["activity_type"] for row in response.json()["results"]]
        self.assertIn("recommendation_approved", types)
