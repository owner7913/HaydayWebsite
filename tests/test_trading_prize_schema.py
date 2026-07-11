import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch


os.environ["MONGO_URI"] = "mongodb://localhost:27017"
os.environ["TRADING_MONGO_URI"] = "mongodb://localhost:27017"
os.environ["R2_ACCESS_KEY_ID"] = "test"
os.environ["R2_SECRET_ACCESS_KEY"] = "test"
os.environ["R2_S3_ENDPOINT"] = "https://example.com"
os.environ["R2_BUCKET"] = "test"
os.environ["WARM_THUMBS"] = "0"

import app as website


def trading_maps():
    return (
        {"butter": "Butter"},
        {"butter": "butter"},
        {"butter": "butter.png"},
        {"butter": None},
        {},
    )


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def sort(self, *_args):
        return self

    def limit(self, value):
        self.rows = self.rows[:value]
        return self

    def __iter__(self):
        return iter(self.rows)


class FakeTicks:
    def __init__(self):
        self.aggregate_calls = []
        self.find_calls = []

    def aggregate(self, pipeline):
        self.aggregate_calls.append(pipeline)
        match = pipeline[0]["$match"]
        group = next((stage["$group"] for stage in pipeline if "$group" in stage), {})
        if match.get("price_type") == "market":
            return [{"_id": "butter", "min_mp": 5, "max_mp": 8, "mp_posts": 2}]
        if "first_price" in group:
            return [{
                "_id": {"k": "butter", "t": "sell"},
                "first_price": 100,
                "last_price": 120,
            }]
        if "avg_price" in group:
            return [{
                "_id": {"d": datetime(2026, 7, 10, tzinfo=timezone.utc), "t": "sell"},
                "avg_price": 110,
                "posts": 2,
                "qty": 20,
            }]
        return [{
            "item_key": "butter",
            "post_type": "sell",
            "sum_qty": 10,
            "sum_value": 1000,
            "posts": 1,
            "price_posts": 1,
            "sum_unit_price": 100,
        }]

    def find(self, match):
        self.find_calls.append(match)
        return FakeCursor([{
            "_id": "tick-1",
            "guild_id": website.TRADING_GUILD_ID,
            "message_id": 123,
            "post_type": "sell",
            "created_at": datetime(2026, 7, 10, tzinfo=timezone.utc),
            "qty": 10,
            "unit_price": 100,
        }])


class FakePosts:
    def find(self, _match, _projection):
        return [{"message_id": 123, "raw_text": "Selling Butter 100 each"}]


class TradingPrizeSchemaTests(unittest.TestCase):
    def setUp(self):
        self.ticks = FakeTicks()
        self.posts = FakePosts()

    def collection(self, name):
        return self.posts if name == "posts" else self.ticks

    def test_overview_uses_accepted_prize_ticks_for_coins_and_market(self):
        with patch.object(website, "get_trading_collection", side_effect=self.collection), patch.object(
            website, "_trading_maps_with_overrides", side_effect=trading_maps
        ), website.app.test_request_context("/api/trading/overview?days=7&type=all"):
            response = website.api_trading_overview()

        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["items"][0]["item_key"], "butter")
        self.assertEqual(payload["items"][0]["xmp_min"], 5)
        self.assertEqual(payload["items"][0]["xmp_max"], 8)

        matches = [call[0]["$match"] for call in self.ticks.aggregate_calls]
        self.assertTrue(all(match["status"] == "accepted" for match in matches))
        self.assertTrue(all("created_at" in match for match in matches))
        self.assertEqual({match["price_type"] for match in matches}, {"coins", "market"})

        coin_group = self.ticks.aggregate_calls[0][1]["$group"]
        self.assertIn("$multiply", coin_group["sum_value"]["$sum"]["$cond"][1])

    def test_history_groups_coin_ticks_by_created_at(self):
        with patch.object(website, "get_trading_collection", return_value=self.ticks), patch.object(
            website, "_trading_maps_with_overrides", side_effect=trading_maps
        ), website.app.test_request_context("/api/trading/item/butter/history?range=30"):
            response = website.api_trading_item_history("butter")

        payload = response.get_json()
        self.assertEqual(payload["sell"], [110.0])
        pipeline = self.ticks.aggregate_calls[0]
        self.assertEqual(pipeline[0]["$match"]["status"], "accepted")
        self.assertEqual(pipeline[0]["$match"]["price_type"], "coins")
        date_expression = pipeline[1]["$group"]["_id"]["d"]["$dateTrunc"]["date"]
        self.assertEqual(date_expression, "$created_at")

    def test_post_details_preserve_frontend_shape(self):
        with patch.object(website, "get_trading_collection", side_effect=self.collection), patch.object(
            website, "_trading_maps_with_overrides", side_effect=trading_maps
        ), website.app.test_request_context(
            "/api/trading/item/butter/posts?bucket=day&at=2026-07-10&type=sell"
        ):
            response = website.api_trading_item_posts("butter")

        post = response.get_json()["posts"][0]
        self.assertEqual(post["qty"], 10)
        self.assertEqual(post["unit_price"], 100)
        self.assertEqual(post["total_value"], 1000)
        self.assertNotIn("raw_text", post)
        self.assertEqual(post["ts"], "2026-07-10T00:00:00+00:00")
        self.assertEqual(self.ticks.find_calls[0]["status"], "accepted")
        self.assertEqual(self.ticks.find_calls[0]["price_type"], "coins")


if __name__ == "__main__":
    unittest.main()
