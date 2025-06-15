from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, get_flashed_messages, flash
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, HiddenField
from wtforms.validators import DataRequired
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os, requests
import re
import time
from bson import ObjectId
from flask_wtf.csrf import CSRFProtect, CSRFError
from shop_data import SHOP_ITEMS
from markupsafe import escape
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# MongoDB


# Discord
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

STAFF_ROLES = {
    1018204467524546591: "Owner",
    1307838468788846652: "Co-Owner",
    1228215782312509531: "Head Admin",
    1086135543110303794: "Moderator",
    1086135499787345920: "Trial Moderator",
    1234364432252145674: "Verifier",
    1251737546770088028: "Giveaway Staff",
}

# Rate limiting
limiter = Limiter(get_remote_address, app=app, default_limits=["10 per minute"])

# CSRF protection
csrf = CSRFProtect(app)

# Session lifetime
app.permanent_session_lifetime = timedelta(days=7)


STAFF_ROLE_IDS = {"1307838468788846652"}
ROLE_ID_TO_NAME = {
    "123456789012345678": "Admin",
    "234567890123456789": "Moderator",
    "345678901234567890": "Booster",
    # Add your role ID to name mappings here
}
def parse_duration(duration_str):
    time_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    match = re.match(r"(\d+)([smhd])", duration_str.strip().lower())
    if match:
        num, unit = match.groups()
        return int(num) * time_map[unit]
    return 600  # fallback: 10m

def is_staff(roles):
    return any(role_id in STAFF_ROLE_IDS for role_id in roles or [])

def get_mongo_client():
    mongo_uri = os.getenv("MONGO_URI")
    return MongoClient(mongo_uri)

def serialize_auction(auction):
    auction["_id"] = str(auction["_id"])
    auction["end_time"] = auction.get("end_time").isoformat() if auction.get("end_time") else None

    # Pick fields to expose safely
    return {
        "id": auction["_id"],
        "item": auction.get("item", "Unknown"),
        "quantity": auction.get("quantity", 1),
        "current_bid": auction.get("current_bid", 0),
        "highest_bidder": auction.get("highest_bidder"),  # user ID
        "display_name": None,  # to fill below
        "bidder_tag": None,
        "end_time": auction["end_time"],
    }

def fetch_role_mapping(guild_id):
    url = f"https://discord.com/api/guilds/{guild_id}/roles"
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    roles = response.json()

    # Create a dict with role ID mapped to name, color, position
    return {
        role["id"]: {
            "name": role["name"],
            "color": f"#{int(role['color']):06x}" if role["color"] != 0 else "#888",
            "position": role["position"]
        }
        for role in roles
    }

def calculate_achievements(xp, message_count, coins, streak, auctions_won=0, top_bidder_count=0, mentions=0):
    achievements = []

    # 📬 Message Milestones
    if message_count >= 10:
        achievements.append({"label": "💬 10 Messages", "tooltip": "Send 10 messages in the server"})
    if message_count >= 100:
        achievements.append({"label": "💬 100 Messages", "tooltip": "Send 100 messages in the server"})
    if message_count >= 500:
        achievements.append({"label": "💬 500 Messages", "tooltip": "Send 500 messages in the server"})
    if message_count >= 1_000:
        achievements.append({"label": "💬 1,000 Messages", "tooltip": "Send 1,000 messages in the server"})
    if message_count >= 5_000:
        achievements.append({"label": "💬 5,000 Messages", "tooltip": "Send 5,000 messages in the server"})
    if message_count >= 10_000:
        achievements.append({"label": "💬 10,000 Messages", "tooltip": "Send 10,000 messages in the server"})
    if message_count >= 25_000:
        achievements.append({"label": "💬 25,000 Messages", "tooltip": "Send 25,000 messages in the server"})
    if message_count >= 50_000:
        achievements.append({"label": "💬 50,000 Messages", "tooltip": "Send 50,000 messages in the server"})
    if message_count >= 100_000:
        achievements.append({"label": "💬 100,000 Messages", "tooltip": "Send 100,000 messages in the server"})

    # 💰 Coin Achievements
    if coins >= 100:
        achievements.append({"label": "🟡 First 100 Coins", "tooltip": "Earn 100 coins"})
    if coins >= 1_000:
        achievements.append({"label": "🟡 Coin Collector", "tooltip": "Earn 1,000 coins"})
    if coins >= 10_000:
        achievements.append({"label": "💸 Rolling in Coins (10k+)", "tooltip": "Earn 10,000 coins"})
    if coins >= 50_000:
        achievements.append({"label": "💰 Treasure Stacker (50k+)", "tooltip": "Earn 50,000 coins"})
    if coins >= 100_000:
        achievements.append({"label": "🤑 Rich Farmer (100k+)", "tooltip": "Earn 100,000 coins"})
    if coins >= 250_000:
        achievements.append({"label": "🏦 Vault Builder (250k+)", "tooltip": "Earn 250,000 coins"})
    if coins >= 500_000:
        achievements.append({"label": "💶 Coin Tycoon (500k+)", "tooltip": "Earn 500,000 coins"})
    if coins >= 1_000_000:
        achievements.append({"label": "👑 Millionaire Status", "tooltip": "Earn 1,000,000 coins"})

    # 🔥 Streaks
    if streak >= 2:
        achievements.append({"label": "🔥 Daily Habit (2+ days)", "tooltip": "Log in 2 days in a row"})
    if streak >= 5:
        achievements.append({"label": "🔥🔥 Consistent Farmer (5+ days)", "tooltip": "Log in 5 days in a row"})
    if streak >= 7:
        achievements.append({"label": "📅 Weekly Warrior (7+ days)", "tooltip": "Maintain a 7-day login streak"})
    if streak >= 14:
        achievements.append({"label": "🌾 Biweekly Beast (14+ days)", "tooltip": "Maintain a 14-day login streak"})
    if streak >= 30:
        achievements.append({"label": "🎯 1 Month Grind!", "tooltip": "Maintain a 30-day login streak"})
    if streak >= 60:
        achievements.append({"label": "🏆 2 Months Streak", "tooltip": "Maintain a 60-day login streak"})
    if streak >= 90:
        achievements.append({"label": "👑 Daily Legend (90+ days)", "tooltip": "Maintain a 90-day login streak"})

    # 🏅 Auctions
    if auctions_won >= 1:
        achievements.append({"label": "🏅 Auction Winner", "tooltip": "Win at least 1 auction"})
    if top_bidder_count >= 5:
        achievements.append({"label": "🎯 Top Bidder", "tooltip": "Be top bidder in 5+ auctions"})

    # 🤝 Trades (Mentions)
    if mentions >= 15:
        achievements.append({"label": "🔴 15+ safe trades!", "tooltip": "Complete 15 valid trades"})
    if mentions >= 30:
        achievements.append({"label": "🔴 30+ safe trades!", "tooltip": "Complete 30 valid trades"})
    if mentions >= 50:
        achievements.append({"label": "🔴 50+ Professional Trader", "tooltip": "Complete 50 valid trades"})
    if mentions >= 100:
        achievements.append({"label": "🟠 Master Of Trades 100+", "tooltip": "Complete 100 valid trades"})
    if mentions >= 200:
        achievements.append({"label": "🟠 Trade-a-saurus rex 200+", "tooltip": "Complete 200 valid trades"})
    if mentions >= 300:
        achievements.append({"label": "🟡 Bullish Banana 300+", "tooltip": "Complete 300 valid trades"})
    if mentions >= 400:
        achievements.append({"label": "🟡 Stocky McTradeface 400+", "tooltip": "Complete 400 valid trades"})
    if mentions >= 500:
        achievements.append({"label": "🟢 Profit Piranha 500+", "tooltip": "Complete 500 valid trades"})
    if mentions >= 600:
        achievements.append({"label": "🟢 Deal-a-whale 600+", "tooltip": "Complete 600 valid trades"})
    if mentions >= 700:
        achievements.append({"label": "🟢 Chart Chimp 700+", "tooltip": "Complete 700 valid trades"})
    if mentions >= 800:
        achievements.append({"label": "🔵 Market Munchkin 800+", "tooltip": "Complete 800 valid trades"})
    if mentions >= 900:
        achievements.append({"label": "🔵 Penny Pincher 900+", "tooltip": "Complete 900 valid trades"})
    if mentions >= 1000:
        achievements.append({"label": "🛡️ 1k Trades??? ur crazy", "tooltip": "Complete 1,000 valid trades"})

    return achievements





@app.template_filter('format')
def format_number(n):
    return f"{n:,}" if isinstance(n, int) else n

@app.route("/shop", methods=["GET", "POST"])
def shop():
    discord_id = session.get("discord_id")
    coins = None
    owned_items = []

    if discord_id:
        with MongoClient(os.getenv("MONGO_URI")) as client:
            eco_user = client["Economy"]["Users"].find_one({"_id": int(discord_id)}) or {}
            coins = eco_user.get("coins", 0)
            owned_items = eco_user.get("owned_items", [])

    return render_template("shop.html", items=SHOP_ITEMS, coins=coins, owned_items=owned_items)


@app.route("/send-reply", methods=["POST"])
def send_reply():
    if not is_staff(session.get("roles", [])):
        return "Unauthorized", 403

    channel_id = request.form["channel_id"]
    message = request.form["message"]

    # Use requests.post to tell your bot server to send message
    requests.post("http://localhost:5000/api/send-message", json={
        "channel_id": channel_id,
        "message": message
    })
    return redirect("/active-tickets")

from datetime import datetime, timezone

@app.route("/remove-featured-achievement", methods=["POST"])
def remove_featured_achievement():
    if "discord_id" not in session:
        return redirect("/login")

    with MongoClient(os.getenv("MONGO_URI")) as client:
        users = client["Website"]["users"]
        users.update_one(
            {"_id": session["discord_id"]},
            {"$unset": {"featured_achievement": ""}}
        )

    return redirect("/profile")

@csrf.exempt
@app.route("/api/friend-action", methods=["POST"])
def friend_action():
    if "discord_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    user_id = session["discord_id"]
    target_id = request.form.get("target_id")
    action = request.form.get("action", "").strip().lower()

    if not target_id or action not in {"add", "remove", "block", "unblock"}:
        return jsonify({"success": False, "error": "Invalid action"}), 400

    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["Website"]["FriendRequests"]

        if action == "add":
            col.update_one({"_id": target_id}, {"$addToSet": {"pending": user_id}}, upsert=True)

        elif action == "remove":
            col.update_one({"_id": user_id}, {"$pull": {"friends": target_id, "pending": target_id}})
            col.update_one({"_id": target_id}, {"$pull": {"friends": user_id, "pending": user_id}})

        elif action == "block":
            col.update_one({"_id": user_id}, {"$addToSet": {"blocked": target_id}}, upsert=True)
            # remove any existing friendship/pending
            col.update_one({"_id": user_id}, {"$pull": {"friends": target_id, "pending": target_id}})
            col.update_one({"_id": target_id}, {"$pull": {"friends": user_id, "pending": user_id}})

        elif action == "unblock":
            col.update_one({"_id": user_id}, {"$pull": {"blocked": target_id}})

        else:
            return jsonify({"success": False, "error": "Invalid action"}), 400

    return jsonify(success=True)



@app.route("/api/friend-status")
def friend_status():
    if "discord_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    viewer = session["discord_id"]
    target = request.args.get("target")

    if not target:
        return jsonify({"error": "Missing target"}), 400

    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["Website"]["FriendRequests"]
        viewer_doc = col.find_one({"_id": viewer}) or {}
        target_doc = col.find_one({"_id": target}) or {}

        is_friend = target in viewer_doc.get("friends", [])
        sent_pending = viewer in target_doc.get("pending", [])
        received_pending = target in viewer_doc.get("pending", [])

    return jsonify({
        "is_friend": is_friend,
        "sent_pending": sent_pending,
        "received_pending": received_pending
    })


@csrf.exempt
@app.route("/update-bio", methods=["POST"])
def update_bio():
    if "discord_id" not in session:
        return redirect(url_for("login"))

    new_bio = request.form.get("bio", "").strip()
    if len(new_bio) > 300:
        flash("❌ Bio must be under 300 characters.", "error")
        return redirect(url_for("profile"))

    safe_bio = escape(new_bio)  # prevent injection

    with MongoClient(os.getenv("MONGO_URI")) as client:
        users = client["Website"]["users"]
        users.update_one(
            {"_id": session["discord_id"]},
            {"$set": {"bio": safe_bio}}
        )

    flash("✅ Bio updated successfully!", "success")
    return redirect(url_for("profile"))


@csrf.exempt
@app.route("/set-featured-achievement", methods=["POST"])
def set_featured_achievement():
    if "discord_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 403

    new_badge = request.form.get("badge")
    if not new_badge:
        return jsonify({"success": False, "error": "Missing badge"}), 400

    with MongoClient(os.getenv("MONGO_URI")) as client:
        users = client["Website"]["users"]
        users.update_one(
            {"_id": session["discord_id"]},
            {"$set": {"featured_achievement": new_badge}}
        )

    return jsonify({"success": True})


@app.route("/giveaways")
def giveaways_page():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Giveaway"]
        user_db = client["hayday"]["level"]
        raw_giveaways = list(db["current_giveaways"].find({"ended": False}))

        # Step 1: Collect all unique user + host IDs
        user_ids = set()
        for g in raw_giveaways:
            user_ids.update(g.get("participants", {}).keys())
            if "host_id" in g:
                user_ids.add(str(g["host_id"]))

        users = user_db.find({"_id": {"$in": list(user_ids)}})
        user_map = {str(u["_id"]): u for u in users}

        giveaways = []
        now = datetime.now(timezone.utc)

        for g in raw_giveaways:
            end = g.get("end_time")
            if not end:
                continue
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            # ✅ Skip if the end time has already passed
            if end < now:
                continue

            g["end_time_str"] = f"<t:{int(end.timestamp())}:R>"
            g["end_time_ts"] = int(end.timestamp())
            g["entry_count"] = sum(g.get("participants", {}).values())
            g["participants_percent"] = []
            g["participant_info"] = []

            host_id = str(g.get("host_id"))
            host = user_map.get(host_id)
            g["host_display"] = host.get("username") if host else f"User {host_id}"
            g["host_avatar"] = f"https://cdn.discordapp.com/avatars/{host_id}/{host.get('avatar_hash')}.png" if host and host.get("avatar_hash") else None

            total_entries = g["entry_count"]
            for uid, count in g.get("participants", {}).items():
                percent = round((count / total_entries) * 100, 2) if total_entries else 0
                u = user_map.get(uid)
                username = u.get("username") if u else f"User {uid}"
                avatar_hash = u.get("avatar_hash") if u else None

                g["participants_percent"].append({
                    "id": uid,
                    "count": count,
                    "percent": percent
                })
                g["participant_info"].append({
                    "id": uid,
                    "count": count,
                    "percent": percent,
                    "name": username,
                    "avatar": f"https://cdn.discordapp.com/avatars/{uid}/{avatar_hash}.png" if avatar_hash else None
                })

            giveaways.append(g)

        return render_template(
            "giveaways.html",
            giveaways=giveaways,
            discord_id=session.get("discord_id"),
            year=datetime.now().year
        )
    
@app.route("/api/live-giveaways")
def api_live_giveaways():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Giveaway"]
        user_db = client["hayday"]["level"]

        raw_giveaways = list(db["current_giveaways"].find({"ended": False}))

        # Gather all unique user IDs for host lookup
        user_ids = {str(g.get("host_id")) for g in raw_giveaways if "host_id" in g}
        user_map = {str(u["_id"]): u for u in user_db.find({"_id": {"$in": list(user_ids)}})}

        giveaways = []
        now = datetime.utcnow()

        for g in raw_giveaways:
            end = g.get("end_time")
            if not end or end < now:
                continue

            host_id = str(g.get("host_id"))
            host_doc = user_map.get(host_id, {})
            host_display = host_doc.get("username", "Anonymous")
            avatar_url = (
                f"https://cdn.discordapp.com/avatars/{host_id}/{host_doc.get('avatar_hash')}.png"
                if host_doc.get("avatar_hash") else None
            )

            giveaways.append({
                "prize": g.get("prize", "Unknown"),
                "host_display": host_display,
                "host_avatar": avatar_url,
                "end_time_ts": int(end.timestamp()),
            })

        return jsonify(giveaways)
@csrf.exempt
@app.route("/api/friend-respond", methods=["POST"])
def friend_respond():
    if "discord_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    user_id = session["discord_id"]
    target_id = request.form.get("target_id")
    action = request.form.get("action")  # accept / reject / block / unblock

    if not target_id or action not in {"accept", "reject", "block", "unblock"}:
        return jsonify({"success": False, "error": "Invalid action"}), 400

    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["Website"]["FriendRequests"]

        if action == "accept":
            col.update_one({"_id": user_id}, {
                "$pull": {"pending": target_id},
                "$addToSet": {"friends": target_id}
            }, upsert=True)
            col.update_one({"_id": target_id}, {
                "$addToSet": {"friends": user_id}
            }, upsert=True)
        elif action == "reject":
            col.update_one({"_id": user_id}, {"$pull": {"pending": target_id}})
        elif action == "block":
            col.update_one({"_id": user_id}, {
                "$pull": {"pending": target_id, "friends": target_id},
                "$addToSet": {"blocked": target_id}
            })
            col.update_one({"_id": target_id}, {
                "$pull": {"friends": user_id, "pending": user_id}
            })
        elif action == "unblock":
            col.update_one({"_id": user_id}, {"$pull": {"blocked": target_id}})

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True})
    else:
        return redirect("/friends")



@app.route("/api/friends")
def api_friends():
    if "discord_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    discord_id = session["discord_id"]

    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["Website"]["FriendRequests"]
        doc = col.find_one({"_id": discord_id}) or {}

        # 🟡 Get sent pending by finding where this user appears in others' pending
        sent_pending_ids = [d["_id"] for d in col.find({"pending": discord_id})]

    return jsonify({
        "pending_requests": doc.get("pending", []),     # received
        "sent_requests": sent_pending_ids,              # sent
        "friends": doc.get("friends", []),
        "blocked": doc.get("blocked", [])
    })



@app.route("/api/friend-usernames")
def api_friend_usernames():
    ids = request.args.getlist("id")

    with MongoClient(os.getenv("MONGO_URI")) as client:
        users_col = client["Website"]["users"]
        results = users_col.find({"_id": {"$in": ids}})
        users = {
            doc["_id"]: {
                "username": doc.get("username", "Unknown"),
                "discriminator": doc.get("username", "0000").split("#")[1] if "#" in doc.get("username", "") else "0000",
                "display_name": doc.get("display_name") or doc.get("username")
            }
            for doc in results
        }

    return jsonify(users)




@app.route("/api/live-bids-feed")
def live_bids_feed():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["hayday"]
        auctions = db["auctions"].find({"status": "active"})

        live_bids = []
        for auction in auctions:
            item = auction.get("item")
            quantity = auction.get("quantity", 1)
            bid_logs = auction.get("bid_logs", [])

            for bid in bid_logs:
                user_id = bid.get("user_id")
                amount = bid.get("amount")
                timestamp = bid.get("timestamp")

                # Lookup user display/tag from your cached collection or fallback to user id
                user_doc = db["UserCache"].find_one({"_id": user_id})
                bidder_tag = user_doc.get("display_name") if user_doc and "display_name" in user_doc else f"User {user_id}"

                live_bids.append({
                    "item": item,
                    "quantity": quantity,
                    "amount": amount,
                    "bidder_tag": bidder_tag,
                    "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
                })

        # Sort by timestamp descending (newest first) and limit to 20
        live_bids_sorted = sorted(live_bids, key=lambda x: x["timestamp"], reverse=True)[:20]

        return jsonify(live_bids_sorted)

@app.route("/friends")
def friends_page():
    if "discord_id" not in session:
        return redirect(url_for("login"))

    user_id = session["discord_id"]

    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["Website"]["FriendRequests"]
        users = client["Website"]["users"]

        doc = col.find_one({"_id": user_id}) or {}

        friends = doc.get("friends", [])
        pending_incoming = doc.get("pending", [])
        blocked = doc.get("blocked", [])

        # Find users you sent friend requests to
        pending_sent = [d["_id"] for d in col.find({"pending": user_id})]
        sent_users = list(users.find({"_id": {"$in": pending_sent}}))

        def enrich_user(u):
            roles = u.get("roles", [])
            u["staff_badges"] = [STAFF_ROLES[int(rid)] for rid in roles if int(rid) in STAFF_ROLES]
            level_doc = client["hayday"]["level"].find_one({"_id": u["_id"]})
            u["level"] = level_doc.get("level") if level_doc else None
            return u

        friend_users = [enrich_user(u) for u in users.find({"_id": {"$in": friends}})]
        pending_users = [enrich_user(u) for u in users.find({"_id": {"$in": pending_incoming}})]
        blocked_users = [enrich_user(u) for u in users.find({"_id": {"$in": blocked}})]
        sent_request_users = [enrich_user(u) for u in sent_users]

    return render_template("friends.html",
        friend_users=friend_users,
        pending_users=pending_users,
        blocked_users=blocked_users,
        sent_requests=sent_request_users,  # ✅ fix this key
        discord_id=user_id
    )




@app.route("/api/live-auctions")
def live_auctions():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["hayday"]
        auctions = list(db["auctions"].find({
        "status": "active",
        "current_bid": {"$exists": True, "$gt": 0},
        "last_bid": {"$exists": True}
        }))
        user_cache = db.database["UserCache"]  # or wherever you store user data

        results = []
        for auction in auctions:
            data = serialize_auction(auction)
            # Lookup bidder display name/tag from user_cache if available
            bidder_id = data.get("highest_bidder")
            if bidder_id:
                user_doc = user_cache.find_one({"user_id": bidder_id})
                if user_doc:
                    data["display_name"] = user_doc.get("display_name") or user_doc.get("username")
                    data["bidder_tag"] = user_doc.get("discord_tag")
            results.append(data)

    return jsonify(results)

@csrf.exempt
@app.route("/api/bid", methods=["POST"])
def api_bid():
    print("API BID endpoint called!")
    print("Request content-type:", request.content_type)
    print("Request data:", request.data)
    print("Request form:", request.form)
    print("Request args:", request.args)

    user_id = session.get("discord_id")
    if not user_id:
        return jsonify({"success": False, "message": "Not logged in via Discord"}), 401

    try:
        data = request.get_json(force=True)
        print("Received data from frontend:", data)
    except Exception as e:
        print("❌ JSON decode error:", e)
        return jsonify({"success": False, "message": "Invalid JSON"}), 400

    auction_id = data.get("auction_id")
    amount = data.get("amount")
    print(f"auction_id: {auction_id} (type: {type(auction_id)})")
    print(f"amount: {amount} (type: {type(amount)})")

    try:
        amount = int(amount)
        auction_id_int = int(auction_id)
    except (TypeError, ValueError):
        print("Failed to cast amount or auction_id to int!")
        return jsonify({"success": False, "message": "Invalid input (amount or auction_id)"}), 400

    print(f"🔍 Incoming bid: auction_id={auction_id_int}, amount={amount}, user_id={user_id}")

    if amount <= 0:
        print("amount <= 0")
        return jsonify({"success": False, "message": "Invalid input"}), 400

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["hayday"]
        auction = db["auctions"].find_one({"message_id": auction_id_int, "status": "active"})

        if not auction:
            print("Auction not found or already ended")
            return jsonify({"success": False, "message": "Auction not found or already ended"}), 404

        now = datetime.now(timezone.utc)
        end_time = auction["end_time"]
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        if end_time <= now:
            return jsonify({"success": False, "message": "Auction already expired"}), 410
        
        # Step 2: Bid validation
        current_bid = auction.get("current_bid", 0)
        min_increment = auction.get("min_increment") or 1
        if amount < current_bid + min_increment:
            print("Bid too low")
            return jsonify({
                "success": False,
                "message": f"Bid must be at least {min_increment:,} higher than the current bid."
            }), 400

        # Step 3: Update auction
        db["auctions"].update_one(
            {"_id": auction["_id"]},
            {"$set": {
                "current_bid": amount,
                "highest_bidder": int(user_id),
                "last_bid": {
                    "user_id": int(user_id),
                    "amount": amount,
                    "timestamp": datetime.utcnow()
                }
            },
            "$push": {
                "bid_logs": {
                    "user_id": int(user_id),
                    "amount": amount,
                    "timestamp": datetime.utcnow()
                }
            }}
        )

        try:
            requests.post(
                "https://discord-mega-bot.fly.dev/refresh_auction",
                json={"message_id": auction_id_int, "notify": True},
                headers={"X-Webhook-Key": os.getenv("BOT_WEBHOOK_KEY")},
                timeout=2
            )
        except Exception as e:
            print(f"Failed to ping bot webhook: {e}")

    return jsonify({"success": True, "message": "Bid placed!"})


@app.route("/submit_bid", methods=["POST"])
def submit_bid():
    data = request.json
    message_id = int(data.get("message_id"))
    amount = int(data.get("amount"))
    user_id = int(session.get("discord_id"))

    if not user_id:
        return jsonify({"error": "Not authenticated"}), 403

    # Save bid in MongoDB
    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["hayday"]
        auction = db["auctions"].find_one({"message_id": message_id, "status": "active"})
        if not auction:
            return jsonify({"error": "Auction not found or already ended"}), 404

        # Basic validation (same as bot)
        base_bid = auction["current_bid"] if auction["current_bid"] > 0 else auction["starting_bid"]
        min_inc = auction.get("min_increment", 1)
        if amount <= base_bid or (amount - base_bid) < min_inc:
            return jsonify({"error": "Invalid bid amount"}), 400

        db["auctions"].update_one(
            {"_id": auction["_id"]},
            {"$set": {
                "current_bid": amount,
                "highest_bidder": user_id,
                "last_bid": {
                    "user_id": user_id,
                    "amount": amount,
                    "timestamp": datetime.utcnow()
                }
            }}
        )

    # Optional: notify the bot via a webhook or a background task (ideal)
    try:
        requests.post(os.getenv("BOT_SYNC_URL"), json={
            "action": "refresh_auction",
            "message_id": message_id
        })
    except:
        pass

    return jsonify({"success": True})

@app.route("/auctions")
def auctions_page():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["hayday"]
        auctions = list(db["auctions"].find({"status": "active"}).sort("end_time", 1))
        user_cache = list(client["Website"]["UserCache"].find())
        user_map = {str(u["_id"]): u for u in user_cache}

        # Ensure all owners are in the user_map
        owner_ids = {str(a['owner_id']) for a in auctions}
        # Optionally, fetch missing users and add to user_map if needed

    now = datetime.now(timezone.utc)
    for auc in auctions:
        end_time = auc.get("end_time")
        if not end_time:
            continue
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        auc["time_remaining"] = str(end_time - now).split(".")[0]

        bidder_id = str(auc.get("highest_bidder"))
        user_info = user_map.get(bidder_id, {})
        auc["bidder_tag"] = user_info.get("tag") or f"User {bidder_id}"
        auc["display_name"] = user_info.get("display_name")
        auc["avatar"] = user_info.get("avatar")

        # Also add owner user info for Jinja
        owner_id = str(auc.get("owner_id"))
        owner_info = user_map.get(owner_id, {})
        auc["owner_display_name"] = owner_info.get("display_name")
        auc["owner_tag"] = owner_info.get("tag")
        auc["owner_avatar"] = owner_info.get("avatar")


    discord_id = session.get("discord_id")  # ✅ Add this
    return render_template("auctions.html", auctions=auctions, year=now.year, discord_id=discord_id)


@app.route("/send-ticket-message", methods=["POST"])
def send_ticket_message():
    if "discord_id" not in session or not is_staff(session.get("roles", [])):
        return redirect(url_for("home"))

    channel_id = request.form["channel_id"]
    message = request.form["message"]
    staff_tag = f"{session.get('username')}#{session.get('discriminator')}"
    avatar_url = f"https://cdn.discordapp.com/avatars/{session.get('discord_id')}/{session.get('avatar')}.png"

    requests.post("http://localhost:5000/api/send-message", json={
        "channel_id": channel_id,
        "message": message,
        "staff_tag": staff_tag,
        "avatar_url": avatar_url
    })

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Support"]
        ticket = db["active_tickets"].find_one({"_id": channel_id})
        client.close()

    return redirect(f"/ticket/{channel_id}" if ticket else "/active-tickets")



@app.route("/active-tickets")
def active_tickets():
    if "discord_id" not in session or not is_staff(session.get("roles", [])):
        return redirect(url_for("home"))

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Support"]
        tickets = list(db["active_tickets"].find({"status": "open"}))
        client.close()

    return render_template("active_tickets.html", tickets=tickets)


@app.route("/ticket/<channel_id>")
def view_ticket(channel_id):
    if "discord_id" not in session or not is_staff(session.get("roles", [])):
        return redirect(url_for("home"))

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Support"]
        ticket = db["active_tickets"].find_one({"_id": channel_id})
        transcript_doc = db["transcripts"].find_one({"_id": channel_id})
        client.close()

    if not ticket:
        return "Ticket not found", 404

    html_chat = transcript_doc["html"] if transcript_doc else "<p>No transcript available.</p>"

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return f'<div id="transcript-container">{html_chat}</div>'

    return render_template("ticket_view.html", ticket=ticket, html_chat=html_chat)





@app.route("/current-bans")
def current_bans():
    search = request.args.get("search", "").lower()
    page = int(request.args.get("page", 1))
    per_page = 12

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Moderation"]
        bans_cursor = db["ban_list"].find()
        bans = list(bans_cursor)

    print(f"[Ban Debug] Found {len(bans)} total bans from DB")

    if search:
        bans = [
            b for b in bans
            if search in b.get("name", "").lower() or search in b.get("reason", "").lower()
        ]

    print(f"[Ban Debug] Filtered to {len(bans)} after search")

    total = len(bans)
    start = (page - 1) * per_page
    end = start + per_page
    bans_paginated = bans[start:end]

    if request.args.get("ajax") == "1":
        return render_template(
            "partials/ban_cards.html",
            bans=bans_paginated,
            is_staff=is_staff(session.get("roles", []))  # ✅ fix here
        )


    return render_template(
        "current_bans.html",
        bans=bans_paginated,
        page=page,
        total_pages=(total + per_page - 1) // per_page,
        search=search,
        is_staff=is_staff  # ✅ this makes it available inside Jinja
    )

@app.route("/mod-action", methods=["POST"])
def mod_action():
    if "discord_id" not in session or not is_staff(session.get("roles", [])):
        return redirect(url_for("home"))

    user_input = request.form.get("user_input")
    action = request.form.get("action")
    duration_raw = request.form.get("duration", "")
    reason = request.form.get("reason", "No reason provided")

    try:
        target_user_id = str(user_input).strip("<@!>")
        target_user_id = int(target_user_id)

        with MongoClient(os.getenv("MONGO_URI")) as client:
            db = client["Moderation"]
            collection = db["mute"]
            now = int(time.time())

        if action == "mute":
            mute_end = now + parse_duration(duration_raw)
            result = collection.update_one(
                {"_id": str(target_user_id)},
                {
                    "$set": {
                        "end_time": mute_end,
                        "reason": reason,
                        "moderator": session["display_name"],
                        "moderator_id": session["discord_id"],
                        "muted": True
                    },
                    "$inc": {"mute_count": 1}
                },
                upsert=True
            )
            flash("✅ Mute added to the database.", "success")

        elif action == "unmute":
            result = collection.update_one(
                {"_id": str(target_user_id)},
                {
                    "$set": {"muted": False}
                }
            )
            flash("✅ Unmute request added to DB. Bot will process shortly.", "success")

        elif action in {"kick", "ban", "warn"}:
            action_doc = {
                "user_id": str(target_user_id),
                "action": action,
                "reason": reason,
                "timestamp": now,
                "moderator": session["display_name"],
                "moderator_id": session["discord_id"],
                "executed": False
            }
            db["web_actions"].insert_one(action_doc)
            flash(f"✅ {action.capitalize()} queued. Bot will process it shortly.", "success")

        elif action == "unban":
            db["web_actions"].insert_one({
                "user_id": str(target_user_id),
                "action": "unban",
                "reason": reason,
                "timestamp": now,
                "moderator": session["display_name"],
                "moderator_id": session["discord_id"],
                "executed": False
            })
            flash("✅ Unban request queued.", "success")

        else:
            flash("❌ Unknown action selected.", "error")

    except Exception as e:
        print(f"[mod_action] Error: {e}")
        flash("❌ Failed to perform action.", "error")

    return redirect("/staff-panel")


@app.route("/api/news")
def api_news():
    from pymongo import MongoClient
    mongo_uri = os.getenv("MONGO_URI")
    with MongoClient(mongo_uri) as client:
        collection = client["hayday"]["NewsFeed"]
        items = list(collection.find().sort("_id", -1).limit(5))
        return jsonify([
            {
                "title": item.get("title", "Untitled"),
                "url": item.get("_id", "#"),
                "timestamp": item.get("timestamp") or datetime.utcnow().isoformat(),
                "source": item.get("source", "unknown"),
                "thumbnail": item.get("thumbnail")  # ✅ ensure this field is populated by your bot
            }
            for item in items
        ])





@app.route("/production_guide")
def production():
    return render_template("production_guide.html")

@app.route("/staff-panel")
def staff_tools():
    if "discord_id" not in session or not is_staff(session.get("roles", [])):
        return redirect(url_for("home"))

    with MongoClient(os.getenv("MONGO_URI")) as client:
        support_db = client["Support"]
        active_tickets = list(support_db["active_tickets"].find({"status": "open"}))

    return render_template(
        "staff_panel.html",
        display_name=session.get("display_name"),
        avatar=session.get("avatar_hash"),
        discord_id=session.get("discord_id"),
        guild_name=session.get("guild_name", "HayDay 🍀"),
        tickets=active_tickets
    )


@app.route("/scam-ids")
def scam_ids():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        collection = client["Scam"]["Banned"]

        # Collect all IDs
        all_ids = []
        for doc in collection.find():
            ids = doc.get("id", [])
            if isinstance(ids, list):
                all_ids.extend(ids)
            else:
                all_ids.append(ids)
        all_ids = sorted(set(all_ids), key=str.upper)
        # Pagination setup
        page = int(request.args.get("page", 1))
        per_page = 30
        total_pages = (len(all_ids) + per_page - 1) // per_page
        paginated_ids = all_ids[(page - 1) * per_page : page * per_page]
    
    return render_template(
        "scam_ids.html",
        scam_ids=paginated_ids,
        current_page=page,
        total_pages=total_pages,
        year=datetime.now().year
    )


@app.route("/")
def home():
    year = datetime.now(timezone.utc).year
    return render_template("index.html", year=year)

@app.route("/login-page")
def login_page():
    return render_template("login.html", sitekey=os.getenv("HCAPTCHA_SITEKEY"))

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash("⚠️ CAPTCHA must be completed before logging in.", "error")
    return redirect(url_for("login_page"))

@app.route("/verify-captcha", methods=["POST"])
def verify_captcha():
    if not request.form.get("agree_terms"):
        flash("❌ You must agree to the Terms of Service.", "error")
        return redirect(url_for("login_page"))

    token = request.form.get("h-captcha-response")
    if not token:
        flash("❌ CAPTCHA must be completed before logging in.", "error")
        return redirect(url_for("login_page"))

    verify = requests.post(
        "https://hcaptcha.com/siteverify",
        data={
            "response": token,
            "secret": os.getenv("HCAPTCHA_SECRET")
        }
    ).json()

    if verify.get("success"):
        return redirect(url_for("login"))  # Redirect to Discord OAuth
    else:
        flash("❌ CAPTCHA validation failed.", "error")
        return redirect(url_for("login_page"))

@app.route("/login")
def login():
    next_page = request.args.get("next", "/")
    session["next_page"] = next_page  # ✅ good
    return redirect(
        f"https://discord.com/oauth2/authorize?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds.members.read"
        f"&guild_id=959220051427340379"
        f"&prompt=consent"
    )





@app.route("/profile")
def profile():
    if "discord_id" not in session:
        return redirect(url_for("login"))

    discord_id = session["discord_id"]

    # Fetch role info
    guild_id = "959220051427340379"
    try:
        role_mapping = fetch_role_mapping(guild_id)
    except Exception as e:
        print("Failed to fetch roles:", e)
        role_mapping = {}

    user_roles = session.get("roles", [])
    enriched_roles = [
        {
            "id": rid,
            "name": role_mapping[rid]["name"],
            "color": role_mapping[rid]["color"],
            "position": role_mapping[rid]["position"]
        }
        for rid in user_roles if rid in role_mapping
    ]
    sorted_roles = sorted(enriched_roles, key=lambda r: r["position"], reverse=True)
    user_roles = session.get("roles", [])

    highest_role = sorted_roles[0] if sorted_roles else None

    # Fetch level data and calculate progress
    with MongoClient(os.getenv("MONGO_URI")) as client:
        level_col = client["hayday"]["level"]
        level_doc = level_col.find_one({"_id": discord_id})
        all_users = list(level_col.find().sort("xp", -1))  # used for rank
        users_collection = client["Website"]["users"]
        user = users_collection.find_one({"_id": discord_id}) or {}
        eco_user = client["Economy"]["Users"].find_one({"_id": int(discord_id)}) or {}
        coins = eco_user.get("coins", 0)
        streak = eco_user.get("streak", 0)
        mention_count = 0
        mention_col = client["Mentions"]["Amount"]
        mention_doc = mention_col.find_one({"id": int(discord_id)})
        friend_doc = client["Website"]["FriendRequests"].find_one({"_id": discord_id}) or {}
        friend_count = len(friend_doc.get("friends", []))
        if mention_doc:
            mention_count = mention_doc.get("Mentions", 0)

    user_roles = user.get("roles", [])
    staff_badges = [STAFF_ROLES[int(rid)] for rid in user_roles if int(rid) in STAFF_ROLES]

    level = xp = message_count = 0
    boost_time_left = None
    rank = "?"
    progress_percent = 0
    current_xp = required_xp = 0
    current_xp_formatted = required_xp_formatted = "0"

    if level_doc:
        level = level_doc.get("level", 1)
        xp = level_doc.get("xp", 0)
        message_count = level_doc.get("message_count", 0)

        # XP Boost
        boost_until = level_doc.get("xp_boost_until")
        if boost_until:
            now = datetime.utcnow()
            boost_until = boost_until if isinstance(boost_until, datetime) else boost_until.to_datetime()
            if boost_until > now:
                boost_time_left = str(boost_until - now).split(".")[0]

        # XP Progress Calculation
        def calc_required_xp(lvl):
            return 100 * (lvl ** 2) + 100 * lvl + 100

        prev_xp = calc_required_xp(level - 1) if level > 1 else 0
        next_xp = calc_required_xp(level)
        current_xp = xp - prev_xp
        required_xp = next_xp - prev_xp
        progress_percent = int((current_xp / required_xp) * 100)

        current_xp_formatted = f"{current_xp:,}"
        required_xp_formatted = f"{required_xp:,}"

        # Rank
        rank = next((i + 1 for i, u in enumerate(all_users) if u["_id"] == discord_id), "?")
    achievements = calculate_achievements(
        xp=xp,
        message_count=message_count,
        coins=coins,
        streak=streak,
        auctions_won=user.get("auctions_won", 0),
        top_bidder_count=user.get("top_bidder_count", 0),
        mentions=mention_count
    )


    return render_template(
        "profile.html",
        username=session.get("username"),
        display_name=session.get("display_name"),
        discord_id=discord_id,
        avatar_hash=session.get("avatar_hash"),
        roles=sorted_roles,
        highest_role=highest_role,
        level=level,
        xp=xp,
        message_count=message_count,
        boost_time_left=boost_time_left,
        progress_percent=progress_percent,
        current_xp_formatted=current_xp_formatted,
        required_xp_formatted=required_xp_formatted,
        rank=rank,
        mention_count=mention_count,
        is_owner=True, 
        user=user,
        staff_badges=staff_badges,
        streak=streak,
        coins=coins,
        achievements=achievements,
        friend_count=friend_count
    )

@app.route("/test-flash")
def test_flash():
    flash("✅ This is a test message!", "success")
    print("Flashed:", get_flashed_messages(with_categories=True))
    return redirect(url_for("profile"))


@csrf.exempt
@app.route("/toggle-privacy", methods=["POST"])
def toggle_privacy():
    if "discord_id" not in session:
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("login"))

    discord_id = session["discord_id"]
    users_collection = MongoClient(os.getenv("MONGO_URI"))["Website"]["users"]
    user = users_collection.find_one({"_id": discord_id})

    if user:
        new_value = not user.get("public_profile", True)
        users_collection.update_one(
            {"_id": discord_id},
            {"$set": {"public_profile": new_value}}
        )
        flash("✅ Profile visibility updated.", "success")

    return redirect(url_for("profile"))



@app.route("/leaderboard")
def leaderboard():
    page = int(request.args.get("page", 1))
    limit = 15
    skip = (page - 1) * limit

    with MongoClient(os.getenv("MONGO_URI")) as client:
        level_col = client["hayday"]["level"]
        users = list(level_col.find().sort("xp", -1).skip(skip).limit(limit))
        total_users = level_col.count_documents({})

    for i, user in enumerate(users):
        user["rank"] = skip + i + 1
        user["xp_formatted"] = f"{user.get('xp', 0):,}"
        user["level"] = user.get("level", 1)

    total_pages = (total_users + limit - 1) // limit

    return render_template("leaderboard.html", users=users, page=page, total_pages=total_pages)



#@app.route("/link")
#def link_page():
#    if "discord_id" not in session:
#        return render_template("link_login.html")  # or show login button
#    return render_template("link.html", discord_id=session["discord_id"], username=session["username"])



@app.route("/callback")
def callback():
    try:
        code = request.args.get("code")
        if not code:
            return "❌ Missing code from Discord redirect", 400

        data = {
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_REDIRECT_URI,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
        r.raise_for_status()
        access_token = r.json()["access_token"]

        user = requests.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"}
        ).json()

        GUILD_ID = "959220051427340379"  # Replace with your actual server ID

        member_res = requests.get(
            f"https://discord.com/api/users/@me/guilds/{GUILD_ID}/member",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        guild_data = requests.get(
            f"https://discord.com/api/guilds/{GUILD_ID}",
            headers={"Authorization": f"Bot {BOT_TOKEN}"}
        ).json()
        session.permanent = True
        session["guild_name"] = guild_data.get("name", "HayDay 🍀")
        if member_res.status_code == 200:
            member_data = member_res.json()
            session["display_name"] = member_data.get("nick") or user["username"]
            session["roles"] = member_data.get("roles", [])
        else:
            session["display_name"] = user["username"]
            session["roles"] = []

        session["discord_id"] = user["id"]
        session["username"] = user["username"] + "#" + user["discriminator"]
        session["avatar_hash"] = user["avatar"]

        with MongoClient(os.getenv("MONGO_URI")) as client:
            users_collection = client["Website"]["users"]

            users_collection.update_one(
                {"_id": user["id"]},
                {"$set": {
                    "username": user["username"] + "#" + user["discriminator"],
                    "display_name": member_data.get("nick") or user["username"],
                    "avatar_hash": user["avatar"],
                    "hay_day_id": None,  # Will be filled after linking
                    "linked_at": datetime.utcnow(),
                    "public_profile": True
                }},
                upsert=True
            )

        next_page = session.pop("next_page", url_for("profile"))
        print("User object:", user)  # <- add this too

        return redirect(next_page)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"<h1>❌ Error:</h1><pre>{e}</pre>", 500

@app.route("/directory")
def public_directory():
    query = request.args.get("q", "").lower()
    page = int(request.args.get("page", 1))
    page_size = 12

    users_collection = MongoClient(os.getenv("MONGO_URI"))["Website"]["users"]

    query_filter = {"public_profile": True}
    if query:
        query_filter["$or"] = [
            {"username": {"$regex": query, "$options": "i"}},
            {"hay_day_id": {"$regex": query, "$options": "i"}},
        ]

    total = users_collection.count_documents(query_filter)
    users = (
        users_collection.find(query_filter)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    return render_template("directory.html",
                           users=list(users),
                           page=page,
                           total_pages=(total // page_size) + 1,
                           query=query)

@app.route("/profile-directory")
def profile_directory():
    search = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 12

    users_collection = MongoClient(os.getenv("MONGO_URI"))["Website"]["users"]

    query = {}
    if search:
        query["$or"] = [
            {"username": {"$regex": search, "$options": "i"}},
            {"display_name": {"$regex": search, "$options": "i"}}
        ]
    if search:
        query["$or"] = [
            {"username": {"$regex": search, "$options": "i"}},
            {"display_name": {"$regex": search, "$options": "i"}}
        ]

    total = users_collection.count_documents(query)
    raw_users = list(
        users_collection.find(query)
        .sort("display_name", 1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    users = []
    for user in raw_users:
        roles = user.get("roles", [])
        staff_badges = [STAFF_ROLES[int(rid)] for rid in roles if int(rid) in STAFF_ROLES]
        user["staff_badges"] = staff_badges
        users.append(user)



    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "profile_directory.html",
        users=users,
        search=search,
        page=page,
        total_pages=total_pages
    )



@app.route("/profile/<discord_id>")
def public_profile(discord_id):
    # Defaults
    level = xp = message_count = boost_time_left = None
    progress_percent = current_xp_formatted = required_xp_formatted = rank = None
    session_friends = session_pending = session_blocked = []
    is_friend = is_pending_received = is_pending_sent = is_blocked = False

    viewer_id = session.get("discord_id")
    is_owner = viewer_id == discord_id

    with MongoClient(os.getenv("MONGO_URI")) as client:
        users_collection = client["Website"]["users"]
        user = users_collection.find_one({"_id": discord_id})

        if not user or not user.get("public_profile", False):
            return "🚫 This profile is private or does not exist.", 404

        # Always fetch target_doc
        target_doc = client["Website"]["FriendRequests"].find_one({"_id": discord_id}) or {}

        if viewer_id:
            viewer_doc = client["Website"]["FriendRequests"].find_one({"_id": viewer_id}) or {}

            # ❌ viewer is blocked BY target user
            if viewer_id in target_doc.get("blocked", []):
                return "🚫 This user has blocked you.", 403

            session_friends = viewer_doc.get("friends", [])
            session_pending = viewer_doc.get("pending", [])
            session_blocked = viewer_doc.get("blocked", [])

            sent_pending = [d["_id"] for d in client["Website"]["FriendRequests"].find({"pending": viewer_id})]

            is_friend = discord_id in session_friends
            is_pending_received = discord_id in session_pending
            is_pending_sent = discord_id in sent_pending
            is_blocked = discord_id in session_blocked

        user_roles = user.get("roles", [])
        staff_badges = [STAFF_ROLES[int(rid)] for rid in user_roles if int(rid) in STAFF_ROLES]

        eco_user = client["Economy"]["Users"].find_one({"_id": int(discord_id)}) or {}
        coins = eco_user.get("coins", 0)
        streak = eco_user.get("streak", 0)

        level_col = client["hayday"]["level"]
        level_doc = level_col.find_one({"_id": discord_id})

        mention_col = client["Mentions"]["Amount"]
        mention_doc = mention_col.find_one({"id": int(discord_id)})
        mention_count = mention_doc.get("Mentions", 0) if mention_doc else 0

        friend_doc = client["Website"]["FriendRequests"].find_one({"_id": discord_id}) or {}
        friend_count = len(friend_doc.get("friends", []))

        if level_doc:
            level = level_doc.get("level", 1)
            xp = level_doc.get("xp", 0)
            message_count = level_doc.get("message_count", 0)

            def calc_required_xp(lvl):
                return 100 * (lvl ** 2) + 100 * lvl + 100

            prev_xp = calc_required_xp(level - 1) if level > 1 else 0
            next_xp = calc_required_xp(level)
            current_xp = xp - prev_xp
            required_xp = next_xp - prev_xp
            progress_percent = int((current_xp / required_xp) * 100)

            current_xp_formatted = f"{current_xp:,}"
            required_xp_formatted = f"{required_xp:,}"

            all_users = list(level_col.find().sort("xp", -1))
            rank = next((i + 1 for i, u in enumerate(all_users) if u["_id"] == discord_id), "?")

    return render_template("profile.html",
        discord_id=user["_id"],
        display_name=user.get("display_name", "Unknown"),
        avatar_hash=user.get("avatar_hash", ""),
        user=user,
        staff_badges=staff_badges,
        level=level,
        xp=xp,
        message_count=message_count,
        mention_count=mention_count,
        boost_time_left=boost_time_left,
        progress_percent=progress_percent,
        current_xp_formatted=current_xp_formatted,
        required_xp_formatted=required_xp_formatted,
        rank=rank,
        roles=[],
        highest_role=None,
        coins=coins,
        streak=streak,
        friend_count=friend_count,
        session_friends=session_friends,
        session_pending=session_pending,
        session_blocked=session_blocked,
        is_friend=is_friend,
        is_pending_received=is_pending_received,
        is_pending_sent=is_pending_sent,
        is_blocked=is_blocked,
        is_owner=is_owner
    )


@csrf.exempt
@app.route("/buy", methods=["POST"])
def buy_item():
    if "discord_id" not in session:
        flash("⚠️ You need to log in to make a purchase.", "error")
        return redirect(url_for("login"))

    item_id = request.form.get("item_id")

    if not item_id or item_id not in SHOP_ITEMS:
        flash("❌ Unknown item.", "error")
        return redirect(url_for("shop_page"))

    user_id = int(session["discord_id"])
    with MongoClient(os.getenv("MONGO_URI")) as client:
        eco = client["Economy"]["Users"]
        user = eco.find_one({"_id": user_id}) or {}

        coins = user.get("coins", 0)
        item = SHOP_ITEMS[item_id]
        price = item["price"]

        if coins < price:
            flash("❌ You don't have enough coins for that.", "error")
            return redirect(url_for("shop_page"))

        eco.update_one({"_id": user_id}, {"$inc": {"coins": -price}})
        client["Economy"]["Purchases"].insert_one({
            "user_id": user_id,
            "item": item_id,
            "name": item["name"],
            "price": price,
            "timestamp": datetime.utcnow()
        })

    flash(f"✅ You bought {item['name']} for {price:,} coins!", "success")
    return redirect(url_for("shop_page"))

@app.route("/logout")
def logout():
    next_page = request.args.get("next", "/")
    session.clear()
    return redirect(next_page)



class SubmitForm(FlaskForm):
    hay_day_id = StringField("Hay Day ID", validators=[DataRequired()])
    discord_id = StringField("Discord ID", validators=[DataRequired()])
    fingerprint = HiddenField("Fingerprint")
    # You can later add a `captcha_response = HiddenField()` here

@app.route("/terms")
def terms_page():
    year = datetime.now().year
    return render_template("terms.html", year=year)


@app.route('/submit', methods=['POST'])
@limiter.limit("5 per minute")
def submit():
    form = SubmitForm()
    if form.validate_on_submit():
        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent')
        now = datetime.now(timezone.utc)

        data = {
            "_id": form.discord_id.data,
            "hay_day_id": form.hay_day_id.data,
            "fingerprint": form.fingerprint.data,
            "ip": ip,
            "user_agent": user_agent,
            "submitted_at": now,
            "consented": True,
            "over_13": True
        }
        with MongoClient(os.getenv("MONGO_URI")) as client:
            client["Website"]["super_trusted"].update_one({"_id": form.discord_id.data}, {"$set": data}, upsert=True)
            return "✅ Your Hay Day ID has been linked successfully!"

    return "❌ Invalid submission.", 400


@app.route("/privacy")
def privacy_page():
    year = datetime.now().year
    return render_template("privacy.html", year=year)



@app.route("/staff")
def staff_panel():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        staff = list(client["Website"]["Staff"].find())
    year = datetime.now(timezone.utc).year
    return render_template("staff.html", staff=staff, year=year)



@app.route('/consent-log')
def consent_log():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        users = list(client["Website"]["super_trusted"].find({"consented": True}))
    html = "<h1>Consent Log</h1><ul>"
    for user in users:
        html += f"<li>Discord ID: {user['_id']} | Hay Day ID: {user['hay_day_id']} | IP: {user['ip']} | Fingerprint: {user['fingerprint']} | Date: {user['submitted_at']}</li>"
    html += "</ul>"
    return html

if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 8080))
    env = os.getenv("FLASK_ENV", "prod")

    if env == "dev":
        # Local dev with livereload
        from livereload import Server
        import logging

        logging.getLogger("livereload").setLevel(logging.WARNING)

        server = Server(app)
        server.watch('templates/')
        server.watch('static/')
        server.serve(host='127.0.0.1', port=port)
    else:
        # Production for Fly.io
        app.run(host="0.0.0.0", port=port)
