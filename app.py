from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
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

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# MongoDB


# Discord
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Rate limiting
limiter = Limiter(get_remote_address, app=app, default_limits=["10 per minute"])

# CSRF protection
csrf = CSRFProtect(app)

# Session lifetime
app.permanent_session_lifetime = timedelta(hours=2)


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

@app.route("/api/live-auctions")
def live_auctions():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["hayday"]
        auctions = list(db["auctions"].find({"status": "active"}))
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
                json={"message_id": auction_id_int},
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






@app.route("/production")
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

@app.route("/login")
def login():
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

    guild_id = "959220051427340379"
    try:
        role_mapping = fetch_role_mapping(guild_id)
    except Exception as e:
        print("Failed to fetch roles:", e)
        role_mapping = {}

    user_roles = session.get("roles", [])

    # Fetch valid roles with metadata
    enriched_roles = [
        {
            "id": rid,
            "name": role_mapping[rid]["name"],
            "color": role_mapping[rid]["color"],
            "position": role_mapping[rid]["position"]
        }
        for rid in user_roles if rid in role_mapping
    ]

    # Sort by highest position
    sorted_roles = sorted(enriched_roles, key=lambda r: r["position"], reverse=True)
    highest_role = sorted_roles[0] if sorted_roles else None

    return render_template(
        "profile.html",
        username=session.get("username"),
        display_name=session.get("display_name"),
        discord_id=session.get("discord_id"),
        avatar_hash=session.get("avatar_hash"),
        roles=sorted_roles,
        highest_role=highest_role
    )






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
        print("Discord token response:", r.text)  # <- add this for debug
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


        print("User object:", user)  # <- add this too

        return redirect(url_for("profile"))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"<h1>❌ Error:</h1><pre>{e}</pre>", 500



@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

class SubmitForm(FlaskForm):
    hay_day_id = StringField("Hay Day ID", validators=[DataRequired()])
    discord_id = StringField("Discord ID", validators=[DataRequired()])
    fingerprint = HiddenField("Fingerprint")
    # You can later add a `captcha_response = HiddenField()` here

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
    return render_template("privacy.html")


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
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


