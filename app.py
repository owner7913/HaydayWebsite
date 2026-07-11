from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, get_flashed_messages,send_file, flash, Response, make_response, abort, stream_with_context
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, HiddenField
from wtforms.validators import DataRequired
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient, ReturnDocument
from datetime import datetime, timedelta, timezone, date
from dotenv import load_dotenv
import os, requests
import re
import time
from bson import ObjectId
from flask_wtf.csrf import CSRFProtect, CSRFError
from shop_data import SHOP_ITEMS
from markupsafe import escape
import csv
from io import StringIO
from markupsafe import Markup
from pytz import timezone as pytz_timezone
from functools import lru_cache
import nest_asyncio
nest_asyncio.apply()
import traceback
from livereload import Server
import logging
import redis
from limits.storage import RedisStorage
from collections import defaultdict
load_dotenv()
import flask_limiter
import unicodedata
from werkzeug.middleware.proxy_fix import ProxyFix
import secrets
import uuid
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import send_from_directory
import json, re, unicodedata
from itsdangerous import URLSafeSerializer, BadSignature
from bs4 import BeautifulSoup 
import email.utils as eut
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib, mimetypes
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError
import boto3
from botocore.client import Config
import io
import gzip
import shutil
import subprocess
import tempfile
import certifi
from botocore.config import Config
import socket as _socket
from calendar import monthrange
from zoneinfo import ZoneInfo
from pymongo.errors import DuplicateKeyError
from math import ceil
import random
from bson.errors import InvalidId
import math
from urllib.parse import urlparse
from flask_session import Session
print("[DEBUG] Flask-Limiter version:", flask_limiter.__version__)

R2_PUBLIC_HOST = os.getenv("R2_PUBLIC_HOST", "")  # e.g. img.hayday.info
WORKER_UPLOAD_URL = os.getenv("WORKER_UPLOAD_URL")
WORKER_UPLOAD_SECRET = os.getenv("WORKER_UPLOAD_SECRET")

BANNED_IPS_LOADED_AT = 0
BANNED_IPS_REFRESH_SECONDS = 300
PAGEVIEW_BUFFER = defaultdict(int)
PAGEVIEW_LOCK = threading.Lock()

if os.getenv("FORCE_IPV4", "0") == "1":
    import socket
    _orig_getaddrinfo = socket.getaddrinfo
    def _getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        res = _orig_getaddrinfo(host, port, family, type, proto, flags)
        only4 = [r for r in res if r[0] == socket.AF_INET]
        return only4 or res
    socket.getaddrinfo = _getaddrinfo_ipv4_only
    print("✅ IPv4-only mode enabled (FORCE_IPV4=1)")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "changeme")
SESSION_TYPE = os.getenv("SESSION_TYPE", "redis").lower()
app.config["SESSION_TYPE"] = SESSION_TYPE
if SESSION_TYPE == "redis":
    app.config["SESSION_REDIS"] = redis.from_url(os.environ["REDIS_URL"])
elif SESSION_TYPE == "filesystem":
    app.config["SESSION_FILE_DIR"] = os.getenv(
        "SESSION_FILE_DIR",
        str(Path(app.root_path) / "output" / "flask_session"),
    )
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_KEY_PREFIX"] = "hayday_session:"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_DOMAIN"] = ".hayday.info"
app.config["SESSION_COOKIE_NAME"] = "hayday_session"
Session(app)
oauth_state_serializer = URLSafeSerializer(app.secret_key, salt="discord-oauth-state")


MONGO_URI = os.getenv("MONGO_URI")
TRADING_MONGO_URI = os.getenv("TRADING_MONGO_URI") or MONGO_URI
TRADING_DB_NAME = os.getenv("TRADING_DB_NAME", "hayday")
TRADING_COLLECTIONS = {
    "posts": os.getenv(
        "TRADING_PRIZES_POSTS_COLLECTION",
        os.getenv("TRADING_POSTS_COLLECTION", "auctions.Trading.prize_posts"),
    ),
    "ticks": os.getenv(
        "TRADING_PRIZES_TICKS_COLLECTION",
        os.getenv("TRADING_TICKS_COLLECTION", "auctions.Trading.prize_ticks"),
    ),
    "items": os.getenv("TRADING_ITEMS_COLLECTION", "auctions.Trading.items"),
    "config": os.getenv("TRADING_CONFIG_COLLECTION", "auctions.Trading.config"),
}
LIVE_GIVEAWAYS_CACHE = {
    "expires": 0,
    "payload": None,
}
PRODUCTION_DATA_CACHE = {
    "expires": 0,
    "payload": None,
}
COMP_RESULTS_CACHE = {}
COMP_RESULTS_CACHE_TTL = 60  # seconds
COMP_SUBMIT_REWARD = 10_000
COMP_VOTE_REWARD = 3_000

MONGO_CLIENT_OPTIONS = dict(
    maxPoolSize=100,
    minPoolSize=5,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=10000,
)

mongo_client = MongoClient(MONGO_URI, **MONGO_CLIENT_OPTIONS)
trading_mongo_client = (
    mongo_client
    if TRADING_MONGO_URI == MONGO_URI
    else MongoClient(TRADING_MONGO_URI, **MONGO_CLIENT_OPTIONS)
)

def get_db(db_name=None):
    if db_name:
        return mongo_client[db_name]
    return mongo_client

def get_trading_db():
    return trading_mongo_client[TRADING_DB_NAME]

def get_trading_collection(name):
    return get_trading_db()[TRADING_COLLECTIONS[name]]

# VERY TEMP storage just to see things working locally
COMP_ENTRIES = {}  # comp_id -> list of {image_url, username, caption, created_at}
USER_SUBMITTED = {}  # (comp_id, user_id) -> True

# Allow up to ~6 MB uploads (PNG/JPG up to 5 MB + overhead)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXT = {"png", "jpg", "jpeg"}
UPLOAD_ROOT = os.path.join(app.root_path, "static", "uploads")  # served by Flask static

THEMES = {
    1:  {"title": "Winter Warmth",     "desc": "Cozy up your farm with fireplaces, snowmen, and frosty barns."},
    2:  {"title": "Valentine's Farm",  "desc": "Hearts, roses, and love-filled decorations everywhere."},
    3:  {"title": "Spring Awakening",  "desc": "Flowers, sprouts, and colorful renewal after winter."},
    4:  {"title": "Easter Garden",     "desc": "Eggs, bunnies, and pastel farm vibes."},
    5:  {"title": "Flower Festival",   "desc": "Transform your farm into a field of color."},
    6:  {"title": "Summer Harvest",    "desc": "Lush crops and long sunny days on the farm."},
    7:  {"title": "Berry Season",      "desc": "Strawberries, picnics, and outdoor fun."},
    8:  {"title": "Tropical Farm",     "desc": "Palms, sunshine, and vacation vibes."},
    9:  {"title": "Rustic Revival",    "desc": "Simple, traditional farm life returning after summer."},
    10: {"title": "Halloween Harvest", "desc": "Pumpkins, scarecrows, and spooky fun."},
    11: {"title": "Harvest Festival",  "desc": "Celebrate abundance with cozy autumn colors."},
    12: {"title": "Christmas Cheer",   "desc": "Festive lights, gifts, and holiday sparkle."},
}

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

INDEX_PATH = Path(__file__).with_name("index.json")  # put index.json next to app.py

with INDEX_PATH.open("r", encoding="utf-8") as f:
    _INDEX = json.load(f)

# Only allow real items we control
INDEX_ITEMS = [
    d for d in _INDEX
    if d.get("key")
    and d.get("name")
    and (d.get("category") in {"item", "set"} or d.get("key") == "help")
]

DISPLAY_MAP = {d["key"]: d["name"] for d in INDEX_ITEMS}

ALLOWED_IMAGE_HOSTS = {
    "static.wikia.nocookie.net",
    "vignette.wikia.nocookie.net",
    "hayday.fandom.com",
}

# Search / alias mapping (you can expand this later)
ALIAS_TO_KEY = {}
for d in INDEX_ITEMS:
    ALIAS_TO_KEY[_norm(d["name"])] = d["key"]
    ALIAS_TO_KEY[_norm(d["key"].replace("_", " "))] = d["key"]

# Image filename + fallback image url
KEY_TO_FILENAME = {d["key"]: f'{d["key"]}.png' for d in INDEX_ITEMS}
KEY_TO_SOURCE_URL = {d["key"]: d.get("source_url") for d in INDEX_ITEMS}

# --- Trading item overrides (for items seen in DB but missing from index.json) ---
# Stored in Mongo: Website.trading_item_overrides
def _trading_maps_with_overrides():
    # Start from index.json maps
    display_map = dict(DISPLAY_MAP)
    alias_to_key = dict(ALIAS_TO_KEY)
    key_to_filename = dict(KEY_TO_FILENAME)
    key_to_source_url = dict(KEY_TO_SOURCE_URL) 
    key_to_image_url = {}                         


    try:
        c = get_db()
        col = c["Website"]["trading_item_overrides"]
        for doc in col.find({}):
            k = (doc.get("_id") or "").strip().lower()
            if not k:
                continue

            name = (doc.get("name") or "").strip()
            if name:
                display_map[k] = name
                alias_to_key[_norm(name)] = k

            # always allow searching by key too
            alias_to_key[_norm(k.replace("_", " "))] = k

            img = (doc.get("image_file") or "").strip()
            if img:
                key_to_filename[k] = img

            src = (doc.get("source_url") or "").strip()
            if src:
                key_to_source_url[k] = src

            img_url = (doc.get("image_url") or "").strip()
            if img_url:
                key_to_image_url[k] = img_url

            aliases = doc.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [aliases]
            for a in aliases:
                a = (a or "").strip()
                if a:
                    alias_to_key[_norm(a)] = k
    except Exception:
        # Never break trading pages if overrides DB has issues
        pass

    return display_map, alias_to_key, key_to_filename, key_to_source_url, key_to_image_url

def _theme_for(comp_id: str):
    """Pick theme by comp_id 'YYYY-MM'. Falls back to current month if parsing fails."""
    try:
        _, m = comp_id.split("-")
        month = int(m)
    except Exception:
        month = datetime.now(timezone.utc).month
    return THEMES.get(month, {"title": "Farm Design", "desc": ""})

def flush_pageview_buffer():
    while True:
        time.sleep(10)

        with PAGEVIEW_LOCK:
            if not PAGEVIEW_BUFFER:
                continue
            snapshot = dict(PAGEVIEW_BUFFER)
            PAGEVIEW_BUFFER.clear()

        try:
            col = get_db("Website")["PageViews"]
            for path, count in snapshot.items():
                col.update_one(
                    {"_id": path},
                    {"$inc": {"count": count}},
                    upsert=True
                )
        except Exception as e:
            print("[pageviews] flush failed:", e)

def page_meta(title=None, description=None, image=None, url=None):
    return {
        "title": title or "HayDay 🐰 - Community Tools & Competitions",
        "description": description or "Join events, verify accounts, and explore community tools for Hay Day.",
        "image": image or url_for("static", filename="img/share.jpg", _external=True),
        "url": url or "https://hayday.info/",
    }

def _phase_today():
    # Use Danish local time for cutoff (handles DST automatically)
    now = datetime.now(ZoneInfo("Europe/Copenhagen"))
    y, m, d = now.year, now.month, now.day
    last_day = monthrange(y, m)[1]

    # Submissions: day 1-25
    # Voting: day 26-last_day - 1)
    # Results: last_day (end-of-month)
    if 1 <= d <= 25:
        phase = "submit"
    elif 26 <= d < last_day:
        phase = "voting"
    else:
        phase = "results"  # runs on the final calendar day

    # Manual override (optional)
    FORCE_PHASE = None  # e.g. "voting", "submit", "results"
    if FORCE_PHASE:
        phase = FORCE_PHASE

    comp_id = f"{y}-{m:02d}"
    return phase, comp_id

def _bot_auth_ok(req):
    return req.headers.get("Authorization") == os.getenv("BOT_WEBHOOK_KEY")

def _prev_comp_id(comp_id: str) -> str:
    y, m = map(int, comp_id.split("-"))
    m -= 1
    if m == 0:
        y -= 1
        m = 12
    return f"{y}-{m:02d}"

def _vote_counts_for(comp_id: str, client: MongoClient) -> dict[str, int]:
    """Return {entry_id: vote_count} for a competition."""
    col = client["Website"]["CompVotes"]          # <-- your votes collection
    pipeline = [
        {"$match": {"comp_id": comp_id}},
        {"$group": {"_id": "$entry_id", "n": {"$sum": 1}}},
    ]
    return {str(d["_id"]): int(d["n"]) for d in col.aggregate(pipeline)}


def _competition_reward_claims_col():
    return get_db("Website")["CompRewardClaims"]


def _competition_reward_claim_id(comp_id: str, user_id: str, action: str) -> str:
    return f"{comp_id}:{action}:{user_id}"


def _competition_has_reward_claim(comp_id: str, user_id: str, action: str) -> bool:
    if not user_id:
        return False
    return _competition_reward_claims_col().find_one(
        {"_id": _competition_reward_claim_id(comp_id, str(user_id), action)},
        {"_id": 1},
    ) is not None


def _competition_try_grant_reward(comp_id: str, user_id: str, action: str, amount: int, *, meta=None):
    user_id = str(user_id or "").strip()
    amount = int(amount or 0)
    if not user_id or not user_id.isdigit() or amount <= 0:
        return False, None

    claims_col = _competition_reward_claims_col()
    claim_id = _competition_reward_claim_id(comp_id, user_id, action)
    claim_doc = {
        "_id": claim_id,
        "comp_id": comp_id,
        "user_id": user_id,
        "action": action,
        "amount": amount,
        "claimed_at": datetime.now(timezone.utc),
        "meta": meta or {},
    }
    try:
        claims_col.insert_one(claim_doc)
    except DuplicateKeyError:
        return False, None

    new_balance = _gambling_credit_user(
        int(user_id),
        amount,
        source=f"competition_reward:{action}",
        meta={"comp_id": comp_id, "action": action, **(meta or {})},
    )
    claims_col.update_one(
        {"_id": claim_id},
        {"$set": {
            "balance_after": new_balance,
            "ledger_source": f"competition_reward:{action}",
        }},
    )
    return True, new_balance


COMP_MODERATION_REASONS = {
    "not_decorated": "The submission was removed because it was not a decorated farm design.",
    "troll": "The submission was removed because it looked like a troll or joke entry.",
    "inappropriate": "The submission was removed because it did not follow the contest rules.",
    "other": "The submission was removed because it did not meet this month's contest requirements.",
}


def _competition_bans_col():
    return get_db("Website")["CompSubmissionBans"]


def _competition_ban_id(comp_id: str, user_id: str) -> str:
    return f"{comp_id}:{str(user_id)}"


def _competition_submission_ban(comp_id: str, user_id: str):
    user_id = str(user_id or "").strip()
    if not user_id:
        return None
    return _competition_bans_col().find_one({"_id": _competition_ban_id(comp_id, user_id)})


def _competition_clear_results_cache(comp_id: str):
    for k in list(COMP_RESULTS_CACHE.keys()):
        if f":{comp_id}:" in k or k.startswith(f"results:{comp_id}:"):
            COMP_RESULTS_CACHE.pop(k, None)


def _competition_debit_user_allow_negative(user_id, amount, *, source, meta=None):
    user_id = int(user_id)
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Debit amount must be positive")

    economy_db = get_db("Economy")
    users_col = economy_db["Users"]
    ledger_col = economy_db["coin_ledger"]

    user_doc = users_col.find_one_and_update(
        {"_id": user_id},
        {"$inc": {"coins": -amount}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    new_balance = int((user_doc or {}).get("coins", 0))

    actor_id = session.get("discord_id")
    ledger_col.insert_one({
        "user_id": user_id,
        "type": "debit",
        "amount": amount,
        "balance_after": new_balance,
        "source": source,
        "actor_id": int(actor_id) if str(actor_id).isdigit() else None,
        "related_user_id": None,
        "meta": meta or {},
        "ts": datetime.now(timezone.utc),
    })
    return new_balance


def _competition_revoke_submit_reward(comp_id: str, user_id: str, *, entry_id: str, moderation_id):
    claims_col = _competition_reward_claims_col()
    claim_id = _competition_reward_claim_id(comp_id, str(user_id), "submit")
    claim = claims_col.find_one({"_id": claim_id})
    if not claim or claim.get("revoked_at"):
        return {
            "revoked": False,
            "amount": 0,
            "balance_after": None,
            "claim_id": claim_id,
        }

    amount = int(claim.get("amount") or COMP_SUBMIT_REWARD)
    new_balance = _competition_debit_user_allow_negative(
        user_id,
        amount,
        source="competition_reward:submit_revoke",
        meta={
            "comp_id": comp_id,
            "entry_id": entry_id,
            "claim_id": claim_id,
            "moderation_id": str(moderation_id),
        },
    )
    claims_col.update_one(
        {"_id": claim_id},
        {"$set": {
            "revoked_at": datetime.now(timezone.utc),
            "revoked_by": str(session.get("discord_id") or ""),
            "revoke_reason": "moderated_submission",
            "revoke_moderation_id": str(moderation_id),
            "revoke_balance_after": new_balance,
        }},
    )
    return {
        "revoked": True,
        "amount": amount,
        "balance_after": new_balance,
        "claim_id": claim_id,
    }


def _competition_notify_bot_moderation(payload: dict):
    bot_base = (os.getenv("BOT_WEBHOOK_URL") or "").rstrip("/")
    bot_key = os.getenv("BOT_WEBHOOK_KEY", "")
    if not bot_base or not bot_key:
        return {"ok": False, "error": "Bot webhook is not configured."}

    try:
        res = requests.post(
            f"{bot_base}/webhook/competition/moderation-warning",
            json=payload,
            headers={"Authorization": bot_key},
            timeout=10,
        )
        if 200 <= res.status_code < 300:
            return {"ok": True, "status_code": res.status_code}
        return {
            "ok": False,
            "status_code": res.status_code,
            "error": res.text[:300],
        }
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# Session & cookie hardening
app.config["RATELIMIT_STORAGE_URL"] = os.environ["REDIS_URL"]
app.config["RATELIMIT_DEFAULTS"] = ["50 per minute"]


# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["50 per minute"]
)
limiter.init_app(app)

# Trust proxy headers (needed for HTTPS on Fly.io)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# Discord
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
rate_limit_cache = {}

STAFF_ROLES = {
    1018204467524546591: "Owner",
    1307838468788846652: "Co-Owner",
    1228215782312509531: "Head Admin",
    1086135543110303794: "Moderator",
    1086135499787345920: "Trial Moderator",
    1234364432252145674: "Verifier",
    1251737546770088028: "Giveaway Staff",
}

SCANNER_PATHS = [
    # WordPress core
    "/wp-admin", "/wp-login.php", "/wp-includes", "/wp-content",
    "/xmlrpc.php", "/wp-cron.php", "/wp-config.php", "/wp-trackback.php",

    # WordPress scan files
    "/license.txt", "/readme.html", "/feed", "/blog", "/wordpress", "/wp1", "/wp2",
    "/wp/wp-admin", "/wp/wp-login.php", "/wordpress/wp-admin", "/wordpress/wp-login.php",

    # Other CMSs and config targets
    "/joomla", "/drupal", "/typo3", "/cms", "/site", "/phpmyadmin", "/pma",
    "/config.json", "/config.php", "/.env", "/.env.dev", "/.env.local", "/env",
    "/.git/config", "/.git/HEAD", "/admin.php",

    # Known vulnerable or backdoor files
    "/shell.php", "/cmd.php", "/upload.php", "/file.php", "/alfa.php", "/ws.php",
    "/vendor/phpunit", "/server-status", "/info.php",

    # WordPress manifest + discovery
    "/wlwmanifest.xml", "/robots.txt", "/sitemap.xml",

    # Misc
    "/test", "/test.php", "/temp", "/backup", "/old", "/dev"
]

SCANNER_EXEMPT_PREFIXES = (
    "/admin/backups",
    "/api/admin/backups",
)


banned_ips_loaded = False
BANNED_IPS = set()
ip_hits = defaultdict(list)
SCAN_THRESHOLD = 20  # Max suspicious hits before ban
BAN_TIME = 2592000  # 30 days in seconds
# CSRF protection
csrf = CSRFProtect(app)

# Session lifetime
app.permanent_session_lifetime = timedelta(hours=12)

GUILD_ID = 959220051427340379  # your server ID
UNVERIFIED_ROLE_ID = 959238651999567893
MEMBER_ROLE_ID = 959220051469279296

COPENHAGEN_TZ = pytz_timezone("Europe/Copenhagen")


STAFF_ROLE_IDS = {"1307838468788846652"}
ROLE_ID_TO_NAME = {
    "123456789012345678": "Admin",
    "234567890123456789": "Moderator",
    "345678901234567890": "Booster",
    # Add your role ID to name mappings here
}

# very simple in-memory cache (restart-safe not required here)
_API_CACHE = {}   # key -> (expires_ts, bytes, headers_dict)
_IMG_CACHE = {}   # url -> (expires_ts, bytes, headers_dict)
_TTL_API  = 6 * 60 * 60     # 6h
_TTL_IMG  = 24 * 60 * 60    # 24h

TRADING_GUILD_ID = 959220051427340379
BAD_SUFFIX = re.compile(r"(_ea|_each|_completed|_complete|_done|_checked|_check)+$", re.I)

THUMB_SIZE_DEFAULT = 96
THUMB_ROOT = Path(__file__).parent / "static" / "thumbs"  # use pathlib.Path
GOODS_TITLES_PATH = THUMB_ROOT / "_goods_titles.json"
GOODS_TITLES_TTL = 7 * 24 * 60 * 60  # refresh weekly

def _title_from_slug(slug: str) -> str:
    # "Blueberry_Chutney" -> "Blueberry Chutney"
    return slug.replace("_", " ")

# Optional title exceptions (expand if you find mismatches)
TITLE_EXCEPTIONS = {
    "Tea leaf": "Tea_Leaves",
    # "Plain Yogurt": "Plain_Yogurt",
}

_getaddrinfo_orig = _socket.getaddrinfo
def _getaddrinfo_ipv4_first(host, port, family=0, type=0, proto=0, flags=0):
    res = _getaddrinfo_orig(host, port, family, type, proto, flags)
    res.sort(key=lambda r: 0 if r[0] == _socket.AF_INET else 1)  # IPv4 first
    return res
_socket.getaddrinfo = _getaddrinfo_ipv4_first

S3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",                          # R2 requirement
    endpoint_url=os.environ["R2_S3_ENDPOINT"],   # <- custom domain
    config=Config(s3={"addressing_style": "path"})
)

os.environ.setdefault("AWS_CA_BUNDLE", certifi.where())
os.environ.setdefault("BOTO_DEFAULT_SSL_VERSION", "TLSv1_2")

def clean_key(k: str) -> str:
    k = (k or "").strip().lower()
    k = re.sub(r"[^a-z0-9_]+", "_", k)
    k = re.sub(r"_+", "_", k).strip("_")
    k = BAD_SUFFIX.sub("", k)
    return k

def _clean_name(name: str) -> str:
    s = (name or "").strip()
    # remove "(...)" chunks like (COMPLETED 鈽戯笍)
    s = re.sub(r"\([^)]*\)", "", s).strip()
    # remove stray checkmarks
    s = s.replace("☑️", "").replace("✅", "").strip()
    # remove trailing tokens like "ea"
    s = re.sub(r"\b(ea|each|completed|complete|done)\b", "", s, flags=re.I).strip()
    # collapse spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s

def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        verify=certifi.where(),  # <- important
    )

def r2_put_object(fileobj, key, content_type):
    """Upload file through Cloudflare Worker and return a PUBLIC https URL."""
    if not WORKER_UPLOAD_URL or not WORKER_UPLOAD_SECRET:
        raise RuntimeError("Worker upload not configured")

    fileobj.seek(0)
    url = f"{WORKER_UPLOAD_URL.rstrip('/')}/upload/{key}"
    headers = {
        "x-upload-secret": WORKER_UPLOAD_SECRET,
        "content-type": content_type,
    }
    r = requests.put(url, data=fileobj.read(), headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    # Prefer explicit url; otherwise build it from the returned key
    if isinstance(data, dict):
        if "url" in data and str(data["url"]).startswith("http"):
            return data["url"]
        if "key" in data and R2_PUBLIC_HOST:
            return f"https://{R2_PUBLIC_HOST.rstrip('/')}/{data['key'].lstrip('/')}"
        # Some workers return {host:'...', key:'...'}
        if "host" in data and "key" in data:
            scheme = "https://" if not str(data["host"]).startswith("http") else ""
            return f"{scheme}{data['host'].rstrip('/')}/{data['key'].lstrip('/')}"
    # Fallback (if worker returns a raw string url)
    return str(data)

def resize_to_max_edge(filestorage, max_edge=3000):
    """Resize if needed and return (BytesIO, content_type, ext). Saves as JPEG 85%."""
    filestorage.stream.seek(0)
    try:
        img = Image.open(filestorage.stream).convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Invalid or corrupted image file.") from exc
    w, h = img.size
    if max(w, h) > max_edge:
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    buf.seek(0)
    return buf, "image/jpeg", "jpg"


def _comp_strings_for(comp_id: str, submit_end_day: int = 25, tz: str = "Europe/Copenhagen"):
    """
    Build all display strings/ranges/countdowns for the competition month.
    Reuse across home, gallery, submit pages so everything stays in sync.
    """
    # Parse comp_id like "2025-10"
    y, m = map(int, comp_id.split("-"))
    last_day = monthrange(y, m)[1]

    # Clamp submit end to month end + compute vote start
    submit_end_day = min(submit_end_day, last_day)
    vote_start_day = min(submit_end_day + 1, last_day)

    # Date objects for ranges (for pretty labels)
    d1 = date(y, m, 1)
    d_submit_end_date = date(y, m, submit_end_day)
    d_vote_start_date = date(y, m, vote_start_day)
    d_end_date = date(y, m, last_day)

    # Exact cutoffs with local timezone
    tzinfo = ZoneInfo(tz)
    # Submissions close at 23:59 local on submit_end_day
    d_submit_end = datetime(y, m, submit_end_day, 23, 59, tzinfo=tzinfo)
    # Voting ends at 23:59 local on the last day
    d_end = datetime(y, m, last_day, 23, 59, tzinfo=tzinfo)

    # Nice label like "October 2025"
    month_label = datetime(y, m, 1).strftime("%B %Y")

    # Range strings like "Oct 01-Oct 25, 2025"
    submit_range_str = f"{d1.strftime('%b %d')} - {d_submit_end_date.strftime('%b %d, %Y')}"
    voting_range_str = f"{d_vote_start_date.strftime('%b %d')} - {d_end_date.strftime('%b %d, %Y')}"

    # Countdown helper (local time; shows h/m if under 1 day)
    now = datetime.now(tzinfo)

    def _left_text(target_dt: datetime):
        delta = target_dt - now
        secs = int(delta.total_seconds())
        if secs <= 0:
            return "closed"
        days = secs // 86400
        if days >= 1:
            return f"{days} day{'s' if days != 1 else ''}"
        hours = (secs % 86400) // 3600
        mins = (secs % 3600) // 60
        if hours > 0:
            return f"{hours}h {mins:02d}m"
        return f"{mins}m"

    submit_left_text = _left_text(d_submit_end)
    voting_left_text = _left_text(d_end)

    return {
        "month_label": month_label,
        "submit_range_str": submit_range_str,
        "voting_range_str": voting_range_str,
        "submit_left_text": submit_left_text,   # e.g., "3 days", "12h 05m", "35m", "closed"
        "voting_left_text": voting_left_text,
        # (optionally expose raw day numbers if templates want them)
        "submit_end_day": submit_end_day,
        "vote_start_day": vote_start_day,
        "last_day": last_day,
    }


def _space(s: str) -> str:
    return " ".join(str(s or "").strip().split())

def _snake(s: str) -> str:
    return _space(s).replace(" ", "_")


def fetch_goods_titles(force: bool = False) -> list[str]:
    # use cached file unless forcing or stale
    if GOODS_TITLES_PATH.exists() and not force:
        try:
            if time.time() - GOODS_TITLES_PATH.stat().st_mtime < GOODS_TITLES_TTL:
                return json.loads(GOODS_TITLES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Ask Fandom for rendered HTML of the page
    params = {"action": "parse", "format": "json", "prop": "text", "page": "Goods_List"}
    r = requests.get("https://hayday.fandom.com/api.php", params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    html = data.get("parse", {}).get("text", {}).get("*", "")
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    titles = set()

    # Find the big goods table(s). They're usually 'wikitable' or 'article-table'.
    for tbl in soup.select("table.wikitable, table.article-table"):
        # Expect header includes 'Name'
        headers = [th.get_text(strip=True).lower() for th in tbl.select("thead th, tr th")]
        if headers and "name" not in headers[0].lower():
            # if first col isn't Name, skip
            pass
        for row in tbl.select("tr"):
            cells = row.find_all(["td"])
            if not cells:
                continue
            first = cells[0]
            a = first.find("a", href=True)
            if not a:
                continue
            # Prefer link title (page title) or text
            title = a.get("title") or a.get_text(" ", strip=True)
            title = _space(title)
            # Filter out non-article links (like 'Image')
            if not title or title.lower() in {"image"}:
                continue
            titles.add(title)

    # Persist
    out = sorted(titles)
    GOODS_TITLES_PATH.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out



def normalize_title(name: str) -> str:
    """Convert 'Brown Sugar' -> 'Brown_Sugar', apply exceptions."""
    if not name: return ""
    base = TITLE_EXCEPTIONS.get(name, name)
    return "_".join(str(base).strip().split())

def fandom_imageinfo(title_snake: str, size: int):
    """Ask MediaWiki for a PNG thumb (fallback original) for File:<title>.png/.jpg."""
    def query(ext):
        params = {
            "action": "query", "format": "json",
            "prop": "imageinfo", "iiprop": "url|mime",
            "iiurlwidth": str(size),                 # ask for thumbnail
            "titles": f"File:{title_snake}.{ext}",
        }
        r = requests.get("https://hayday.fandom.com/api.php", params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    for ext in ("png", "jpg"):
        try:
            data = query(ext)
            pages = data.get("query", {}).get("pages", {})
            page  = next(iter(pages.values()), {})
            ii    = (page.get("imageinfo") or [None])[0]
            raw   = ii and (ii.get("thumburl") or ii.get("url"))
            if not raw:
                continue
            # prefer PNG output
            if "format=png" not in raw:
                raw += ("&" if "?" in raw else "?") + "format=png"
            return raw
        except Exception:
            continue
    return None


def _snake(title: str) -> str:
    # "Brown Sugar" -> "Brown_Sugar"
    return normalize_title(title)

def _all_titles_from_db() -> list[str]:
    try:
        c = get_db()
        col = c["hayday"]["ProductionGuide"]
        rows = col.find({}, {"product": 1})
        return sorted({_space(r.get("product", "")) for r in rows if r.get("product")})
    except Exception as e:
        print("[thumbs] mongo read failed:", e)
        return []

def _download_one(slug: str, size: int = THUMB_SIZE_DEFAULT) -> str:
    """
    slug is already snake-cased (e.g., 'Brown_Sugar').
    Writes static/thumbs/<slug>.png if missing.
    Returns status string for logging.
    """
    try:
        path = THUMB_ROOT / f"{slug}.png"
        if path.exists() and path.stat().st_size > 0:
            return "hit"

        url = fandom_imageinfo(slug, size)
        if not url:
            return "miss"

        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if r.ok and r.content:
            path.write_bytes(r.content)
            return "ok"
        return f"fail({r.status_code})"
    except Exception as e:
        return f"err({e})"

def prewarm_thumbs(size: int = THUMB_SIZE_DEFAULT, max_workers: int = 8):
    # gather titles
    db_titles = _all_titles_from_db()
    try:
        goods_titles = fetch_goods_titles(False)  # if you added it; else this excepts
    except Exception:
        goods_titles = []

    all_titles = sorted({ _space(t) for t in (db_titles + goods_titles) if t })
    if not all_titles:
        print("[thumbs] no titles to warm")
        return

    print(f"[thumbs] prewarm start: {len(all_titles)} items, size={size}")

    def resolver(title: str):
        return _download_one(_snake(title), size)

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for status in pool.map(resolver, all_titles):
            done += 1
            if done % 25 == 0:
                print(f"[thumbs] {done}/{len(all_titles)} ({status})")

    print(f"[thumbs] prewarm complete: {done} files")



def _get_cached(d, k):
    v = d.get(k)
    if not v: return None
    exp, body, headers = v
    if exp < time.time():
        d.pop(k, None)
        return None
    return body, headers

def _set_cached(d, k, body, headers, ttl):
    d[k] = (time.time() + ttl, body, headers)

def parse_duration(duration_str):
    time_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    match = re.match(r"(\d+)([smhd])", duration_str.strip().lower())
    if match:
        num, unit = match.groups()
        return int(num) * time_map[unit]
    return 600  # fallback: 10m

def is_staff():
    return session.get("staff_role") is not None

app.jinja_env.globals['is_staff'] = is_staff

def is_admin():
    return session.get("staff_role") in ["Owner", "Co-Owner", "Head Admin"]

def can_manage_verifications():
    return session.get("staff_role") in [
        "Owner",
        "Co-Owner",
        "Head Admin",
        "Moderator",
        "Trial Moderator",
        "Verifier",
    ]

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def contains_identifying_text(text: str, display_name: str | None, username_tag: str | None, discord_id: str | None) -> bool:
    """
    Returns True if `text` appears to include the submitter's identity:
    - display name (nick)
    - username or username#1234
    - raw Discord ID
    - mention forms like <@123> or <@!123>
    """
    if not text:
        return False

    raw = text or ""
    low = raw.lower()

    # 1) Direct mentions like <@123456789012345678> or <@!123...>
    if re.search(r"<@!?\d{15,20}>", raw):
        return True

    # 2) Obvious raw Discord ID
    if discord_id and re.search(rf"\b{re.escape(str(discord_id))}\b", raw):
        return True

    # 3) Username#1234 (full tag) if you store it in session["username"]
    if username_tag and username_tag.lower() in low:
        return True

    # 4) Username without discriminator
    username_base = (username_tag or "").split("#", 1)[0]
    if username_base and username_base.lower() in low:
        return True

    # 5) Display name / nick (normalized to ignore punctuation/accents)
    norm_text = normalize(raw)
    if display_name and normalize(display_name) and normalize(display_name) in norm_text:
        return True
    if username_base and normalize(username_base) and normalize(username_base) in norm_text:
        return True

    # 6) Generic tag patterns like "Name #1234" or "Name - 1234"
    if username_base:
        if re.search(rf"\b{re.escape(username_base.lower())}\s*[#\-\u2013\u2014]?\s*\d{{3,5}}\b", low):
            return True

    return False

# ---- Easter event config ----
EASTER_LIVE = False

EASTER_EVENT = {
    "title": "Hay Day Easter Egg Hunt",
    "subtitle": "A cozy spring giveaway with surprise rewards hidden inside 4 eggs.",
    "starts_at": datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
    "ends_at": datetime(2026, 4, 12, 23, 59, 59, tzinfo=timezone.utc),
    "target_total_opens": 250,
    "egg_scale_factor": 3,
    "eggs": [
        {
            "id": 1,
            "name": "Egg 1",
            "label": "Spring Surprise",
            "day_hint": "Unlocks April 1",
            "unlock_at": datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
        },
        {
            "id": 2,
            "name": "Egg 2",
            "label": "Golden Nest",
            "day_hint": "Unlocks April 4",
            "unlock_at": datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
        },
        {
            "id": 3,
            "name": "Egg 3",
            "label": "Bloom Basket",
            "day_hint": "Unlocks April 7",
            "unlock_at": datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc),
        },
        {
            "id": 4,
            "name": "Egg 4",
            "label": "Grand Egg",
            "day_hint": "Unlocks April 10",
            "unlock_at": datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc),
        },
    ],

    "reserved_prize_inventory": {
        1: {
            "50 Shovels": 8,
            "50 Lobsters": 3,
            "30 Honey": 2,
            "20 Mayo": 1,
            "25 Syrup": 2,
            "25 White Sugar": 2,
            "50 Brown Sugar": 2,
            "50 Milk": 3,
            "100 Eggs": 1,
            "40 Bacon": 1,
            "25 Bread": 2,
            "40 Axes": 8,
        },
        2: {
            "Farm Pass": 1,
            "BEM Set": 2,
            "25 Syrup": 2,
            "25 White Sugar": 2,
            "50 Brown Sugar": 2,
            "25 Goat Cheese": 1,
            "25 Cheese": 1,
            "25 Butter": 1,
            "25 Cream": 1,
            "25 Saws": 1,
            "25 Axes": 1,
            "50 Shovels": 6,
            "50 Lobsters": 2,
            "30 Honey": 2,
            "20 Mayo": 1,
            "25 Bread": 2,
            "40 Axes": 7,
        },
        3: {
            "1M Coins": 2,
            "Farm Pass": 1,
            "100 Lobsters": 1,
            "2 Sets of Your Choice": 1,
            "100 Items of Your Choice": 1,
            "50 Shovels": 8,
            "50 Lobsters": 3,
            "30 Honey": 3,
            "20 Mayo": 2,
            "25 Feathers": 2,
            "30 Fish": 2,
            "BEM Set": 2,
            "25 Syrup": 2,
            "25 White Sugar": 2,
            "50 Brown Sugar": 3,
            "40 Axes": 7,
        },
        4: {
            "1 Month Nitro": 3,
            "1M Coins": 1,
            "200 Lobsters": 1,
            "50 Shovels": 8,
            "50 Lobsters": 4,
            "30 Honey": 3,
            "20 Mayo": 1,
            "25 Feathers": 2,
            "30 Fish": 3,
            "BEM Set": 1,
            "25 Syrup": 2,
            "25 White Sugar": 2,
            "50 Brown Sugar": 3,
            "25 Goat Cheese": 3,
            "25 Cheese": 3,
            "25 Butter": 3,
            "25 Cream": 3,
            "50 Milk": 7,
            "100 Eggs": 2,
            "40 Bacon": 4,
            "25 Bread": 4,
            "25 Saws": 3,
            "25 Axes": 3,
            "40 Axes": 8,
        },
    },

    "soft_loss_rewards": [
        "No prize this time, but the egg was cute 🥚",
        "Nothing inside, just spring vibes 🌷",
        "Empty egg, better luck on the next one!",
        "No reward found, this one was a dud 🥚",
        "Just a shell this time, try another egg!",
        "No win, but you're still in the hunt 🐰",
        "Nothing here, the good stuff is hiding elsewhere 👀",
        "No prize, this egg was just for fun 🎁",
        "Unlucky! This one had no reward 😅",
        "No jackpot, but the next one might have it 💎",
        "Empty egg, the rare ones are still out there!",
        "No reward, this one was a miss 🌼",
        "Just a normal egg, no prize this time",
        "No win, but the hunt continues 🐣",
        "Nothing inside, the big rewards are still hiding!",
        "No reward, try again on the next egg 🥚",
        "This egg was empty, unlucky!",
        "No prize here, keep cracking eggs 🔨",
        "Nothing found, maybe the next one 👀",
        "No win, but you're getting closer 🐰",
    ],
}

EASTER_TESTING = {
    "enabled": False,
    "bypass_unlocks": False,
    "force_result": None,
}

SUMMER_EVENT_ACCESS_CODE = os.getenv("SUMMER_EVENT_ACCESS_CODE", "summer2026").strip().lower()

SUMMER_EVENT = {
    "title": "Hay Day Summer Treasure Hunt",
    "subtitle": "Four summer treasures are washing ashore. Scratch away the sand and see what the tide brought in.",
    "window": "June 21-30",
    "cards": [
        {
            "id": 1,
            "name": "Shoreline Bottle",
            "label": "A sealed bottle rolled in with the morning tide.",
            "unlock_label": "June 21",
            "shape": "bottle",
            "image": "img/summer/items/shoreline-bottle.png",
            "reward": "50 Shovels",
            "rarity": "winner",
            "result_line": "The first tide brought farm supplies.",
        },
        {
            "id": 2,
            "name": "Picnic Cooler",
            "label": "Packed for a bright day at the beach.",
            "unlock_label": "June 24",
            "shape": "cooler",
            "image": "img/summer/items/picnic-cooler.png",
            "reward": "No prize this time",
            "rarity": "bonus",
            "result_line": "Just warm sand in this one.",
        },
        {
            "id": 3,
            "name": "Buried Beach Chest",
            "label": "Half hidden under the dunes and ready to reveal.",
            "unlock_label": "June 27",
            "shape": "chest",
            "image": "img/summer/items/buried-beach-chest.png",
            "reward": "BEM Set",
            "rarity": "winner",
            "result_line": "A proper beach find.",
        },
        {
            "id": 4,
            "name": "Captain's Sun Chest",
            "label": "The final treasure, glowing from under the sand.",
            "unlock_label": "June 30",
            "shape": "sun-chest",
            "image": "img/summer/items/captains-sun-chest.png",
            "reward": "1 Month Nitro",
            "rarity": "winner",
            "result_line": "The grand tide saved this one.",
        },
    ],
}



# add near your easter config
EASTER_PREVIEW_EVENT_ID = "2026_easter_preview"

def _has_easter_preview_access() -> bool:
    return bool(session.get("easter_wins_authed", False)) or is_staff()

def _preview_open_state(discord_id: str | None = None):
    if not discord_id:
        return {}

    col = get_db("Website")["easter_user_opens"]
    doc = col.find_one({"_id": f"{EASTER_PREVIEW_EVENT_ID}:{discord_id}"})
    return (doc or {}).get("opened", {})

def _save_preview_opened_egg(discord_id: str, egg_id: int, reward: str, rarity: str):
    col = get_db("Website")["easter_user_opens"]
    now = datetime.now(timezone.utc)
    col.update_one(
        {"_id": f"{EASTER_PREVIEW_EVENT_ID}:{discord_id}"},
        {
            "$set": {
                "event_id": EASTER_PREVIEW_EVENT_ID,
                "discord_id": str(discord_id),
                f"opened.{egg_id}": {
                    "reward": reward,
                    "rarity": rarity,
                    "opened_at": now.isoformat(),
                },
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True
    )


def _event_open_state(discord_id: str | None = None):
    if not discord_id:
        return {}

    col = get_db("Website")["easter_user_opens"]
    doc = col.find_one({"_id": f"{EASTER_EVENT_ID}:{discord_id}"})
    return (doc or {}).get("opened", {})


def _release_pending_easter_egg(discord_id: str, egg_id: int):
    col = get_db("Website")["easter_user_opens"]
    col.update_one(
        {"_id": f"{EASTER_EVENT_ID}:{discord_id}"},
        {"$unset": {f"opened.{egg_id}": ""}}
    )

def _save_opened_egg(discord_id: str, egg_id: int, reward: str, rarity: str):
    col = get_db("Website")["easter_user_opens"]
    now = datetime.now(timezone.utc)
    col.update_one(
        {"_id": f"{EASTER_EVENT_ID}:{discord_id}"},
        {
            "$set": {
                "event_id": EASTER_EVENT_ID,
                "discord_id": str(discord_id),
                f"opened.{egg_id}": {
                    "reward": reward,
                    "rarity": rarity,
                    "opened_at": now.isoformat(),
                },
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            }
        },
        upsert=True
    )

EASTER_EVENT_ID = "2026_easter"

def _easter_collections():
    db = get_db("Website")
    return {
        "events": db["easter_events"],
        "contributions": db["easter_contributions"],
        "wins": db["easter_wins"],
        "analytics": db["event_analytics"],
        "analytics_log": db["event_analytics_log"],
        "feed": db["easter_feed"],
        "user_opens": db["easter_user_opens"],
        "usernames": db["usernames"],
    }

def _analytics_doc_id(event_id: str) -> str:
    return f"analytics:{event_id}"

def _hour_key(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%H")

def _day_key(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d")

def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""

def _client_session_key() -> str:
    if "analytics_sid" not in session:
        session["analytics_sid"] = secrets.token_hex(16)
        session.modified = True
    return session["analytics_sid"]

def _ensure_event_analytics(event_id: str = EASTER_EVENT_ID):
    cols = _easter_collections()
    analytics_col = cols["analytics"]

    doc = analytics_col.find_one({"_id": _analytics_doc_id(event_id)})
    if doc:
        return doc

    egg_defaults = {
        str(egg["id"]): {
            "views": 0,
            "clicks": 0,
            "open_attempts": 0,
            "successful_opens": 0,
            "wins": 0,
            "losses": 0,
            "already_opened_attempts": 0,
            "locked_attempts": 0,
            "invalid_attempts": 0,
        }
        for egg in EASTER_EVENT["eggs"]
    }

    doc = {
        "_id": _analytics_doc_id(event_id),
        "event_id": event_id,
        "event_type": "easter",
        "event_name": EASTER_EVENT["title"],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "counters": {
            "page_views": 0,
            "unique_page_views": 0,
            "logged_in_views": 0,
            "member_views": 0,
            "banner_views": 0,
            "banner_clicks": 0,
            "banner_closes": 0,
            "cta_clicks": 0,
            "egg_clicks": 0,
            "open_attempts": 0,
            "successful_opens": 0,
            "duplicate_open_attempts": 0,
            "locked_egg_attempts": 0,
            "invalid_egg_attempts": 0,
            "login_gate_hits": 0,
            "admin_tab_clicks": 0,
            "member_gate_hits": 0,
            "event_over_attempts": 0,
            "preview_opens": 0,
            "admin_views": 0,
        },
        "results": {
            "real_wins": 0,
            "soft_losses": 0,
        },
        "eggs": egg_defaults,
        "prizes": {},
        "traffic": {"by_day": {}, "by_hour": {}},
        "users": {"unique_viewers": 0, "unique_openers": 0},
        "performance": {
            "open_requests": 0,
            "open_response_ms_total": 0,
            "last_open_response_ms": 0,
        },
    }
    analytics_col.insert_one(doc)
    return doc

def _analytics_inc(event_id: str, inc_ops: dict, extra_set: dict | None = None):
    cols = _easter_collections()
    analytics_col = cols["analytics"]

    _ensure_event_analytics(event_id)

    update = {
        "$inc": inc_ops,
        "$set": {"updated_at": datetime.now(timezone.utc)},
    }
    if extra_set:
        update["$set"].update(extra_set)

    analytics_col.update_one({"_id": _analytics_doc_id(event_id)}, update)

def _analytics_log(action: str, event_id: str = EASTER_EVENT_ID, **data):
    cols = _easter_collections()
    analytics_log_col = cols["analytics_log"]

    analytics_log_col.insert_one({
        "event_id": event_id,
        "action": action,
        "discord_id": str(session.get("discord_id")) if session.get("discord_id") else None,
        "session_id": _client_session_key(),
        "ip": _client_ip(),
        "user_agent": request.headers.get("User-Agent"),
        "path": request.path,
        "created_at": datetime.now(timezone.utc),
        **data,
    })

def _analytics_track_page_view(access: dict, event_id: str = EASTER_EVENT_ID):
    _ensure_event_analytics(event_id)

    inc = {
        "counters.page_views": 1,
        f"traffic.by_day.{_day_key()}.views": 1,
        f"traffic.by_hour.{_hour_key()}.views": 1,
    }

    if access.get("logged_in"):
        inc["counters.logged_in_views"] = 1
    if access.get("is_member"):
        inc["counters.member_views"] = 1

    # simple unique view per session
    seen_key = f"analytics_seen:{event_id}"
    if not session.get(seen_key):
        inc["counters.unique_page_views"] = 1
        inc["users.unique_viewers"] = 1
        session[seen_key] = True
        session.modified = True

    _analytics_inc(event_id, inc)
    _analytics_log(
        "page_view",
        event_id=event_id,
        logged_in=bool(access.get("logged_in")),
        is_member=bool(access.get("is_member")),
    )

def _analytics_track_open_result(
    egg_id: int,
    result: str,
    reward: str | None = None,
    rarity: str | None = None,
    response_ms: int | None = None,
    event_id: str = EASTER_EVENT_ID,
):
    inc = {
        "counters.open_attempts": 1,
        f"eggs.{egg_id}.open_attempts": 1,
        "performance.open_requests": 1,
        f"traffic.by_day.{_day_key()}.opens": 1,
        f"traffic.by_hour.{_hour_key()}.opens": 1,
    }

    if result == "win":
        inc["counters.successful_opens"] = 1
        inc["results.real_wins"] = 1
        inc[f"eggs.{egg_id}.successful_opens"] = 1
        inc[f"eggs.{egg_id}.wins"] = 1
        inc[f"traffic.by_day.{_day_key()}.wins"] = 1
        inc[f"traffic.by_hour.{_hour_key()}.wins"] = 1
        if reward:
            inc[f"prizes.{reward}.won"] = 1

    elif result == "soft_loss":
        inc["counters.successful_opens"] = 1
        inc["results.soft_losses"] = 1
        inc[f"eggs.{egg_id}.successful_opens"] = 1
        inc[f"eggs.{egg_id}.losses"] = 1

    elif result == "already_opened":
        inc["counters.duplicate_open_attempts"] = 1
        inc[f"eggs.{egg_id}.already_opened_attempts"] = 1

    elif result == "locked":
        inc["counters.locked_egg_attempts"] = 1
        inc[f"eggs.{egg_id}.locked_attempts"] = 1

    elif result == "invalid":
        inc["counters.invalid_egg_attempts"] = 1
        inc[f"eggs.{egg_id}.invalid_attempts"] = 1

    opener_seen_key = f"analytics_opened:{event_id}"
    if result in ("win", "soft_loss") and not session.get(opener_seen_key):
        inc["users.unique_openers"] = 1
        session[opener_seen_key] = True
        session.modified = True

    set_ops = {}
    if response_ms is not None:
        inc["performance.open_response_ms_total"] = int(response_ms)
        set_ops["performance.last_open_response_ms"] = int(response_ms)

    _analytics_inc(event_id, inc, extra_set=set_ops)
    _analytics_log(
        "open_result",
        event_id=event_id,
        egg_id=egg_id,
        result=result,
        reward=reward,
        rarity=rarity,
        response_ms=response_ms,
    )

def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value

def _event_analytics_state(event_id: str = EASTER_EVENT_ID):
    _ensure_event_analytics(event_id)
    cols = _easter_collections()
    return cols["analytics"].find_one({"_id": _analytics_doc_id(event_id)}) or {}

def _recent_event_logs(event_id: str = EASTER_EVENT_ID, limit: int = 50):
    cols = _easter_collections()
    return list(
        cols["analytics_log"].find({"event_id": event_id})
        .sort("created_at", -1)
        .limit(limit)
    )

def _sanitize_easter_reward_text(text: str) -> str:
    text = str(text or "")
    replacements = {
        "鈥?": ", ",
        "鈥揙": "-O",
        "you鈥檙e": "you're",
        "You don鈥檛": "You don't",
        "You鈥檙e": "You're",
        "馃尲": "🌷",
        "馃": "🥚",
        "馃崁": "🐰",
        "馃憖": "👀",
        "馃巵": "🎁",
        "馃槄": "😅",
        "馃拵": "💎",
        "馃尭": "🌼",
        "馃惏": "🐣",
        "馃敤": "🔨",
        "喽□": "🥚",
        "喽荤": "👀",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    text = re.sub(r"\s+", " ", text).strip()
    return text

def _easter_feed_entries(limit: int = 20):
    cols = _easter_collections()
    feed_col = cols["feed"]
    usernames_col = cols["usernames"]

    rows = list(
        feed_col.find({"event_id": EASTER_EVENT_ID})
        .sort("opened_at", -1)
        .limit(limit)
    )

    user_ids = list({
        str(row.get("discord_id"))
        for row in rows
        if row.get("discord_id")
    })

    user_map = {}
    if user_ids:
        for doc in usernames_col.find(
            {"_id": {"$in": user_ids}},
            {"display_name": 1, "username": 1, "avatar": 1}
        ):
            user_map[str(doc["_id"])] = doc

    feed = []
    for row in rows:
        discord_id = str(row.get("discord_id") or "")
        profile = user_map.get(discord_id, {})

        display_name = (
            profile.get("display_name")
            or profile.get("username")
            or row.get("username")
            or (f"User {discord_id[-4:]}" if discord_id else "Unknown")
        )

        feed.append({
            "_id": str(row.get("_id")),
            "discord_id": discord_id,
            "display_name": display_name,
            "avatar": profile.get("avatar"),
            "egg_id": row.get("egg_id"),
            "reward": _sanitize_easter_reward_text(row.get("reward")),
            "rarity": row.get("rarity"),
            "opened_at": row.get("opened_at"),
        })

    return feed


def _insert_easter_feed_entry(discord_id: str, egg_id: int, reward: str, rarity: str):
    cols = _easter_collections()
    feed_col = cols["feed"]

    feed_col.insert_one({
        "event_id": EASTER_EVENT_ID,
        "discord_id": str(discord_id),
        "egg_id": int(egg_id),
        "reward": _sanitize_easter_reward_text(reward),
        "rarity": rarity,
        "opened_at": datetime.now(timezone.utc),
    })

    EASTER_FEED_CACHE["payload"] = None
    EASTER_FEED_CACHE["expires"] = 0

def _has_easter_wins_access() -> bool:
    if is_staff():
        return True
    return bool(session.get("easter_wins_authed", False))

def _ensure_easter_event():
    cols = _easter_collections()
    events_col = cols["events"]

    doc = events_col.find_one({"_id": EASTER_EVENT_ID})
    if not doc:
        reserved_inventory = {
            str(egg_id): pool.copy()
            for egg_id, pool in EASTER_EVENT["reserved_prize_inventory"].items()
        }

        egg_stats = {
            str(egg["id"]): {
                "total_opens": 0,
                "total_real_wins": 0,
                "soft_losses": 0,
            }
            for egg in EASTER_EVENT["eggs"]
        }

        doc = {
            "_id": EASTER_EVENT_ID,
            "title": EASTER_EVENT["title"],
            "created_at": datetime.now(timezone.utc),
            "analytics_enabled": True,
            "prize_pool_by_egg": reserved_inventory,
            "stats": {
                "total_opens": 0,
                "total_real_wins": 0,
                "soft_losses": 0,
                "eggs": egg_stats,
            },
            "rollover_done_from_egg": {},
            "contributors": {}
        }
        events_col.insert_one(doc)

    return doc

def _event_inventory_state():
    doc = _ensure_easter_event()
    return doc.get("prize_pool_by_egg", {})


def _event_stats_state():
    doc = _ensure_easter_event()
    return doc.get("stats", {
        "total_opens": 0,
        "total_real_wins": 0,
        "soft_losses": 0,
        "eggs": {},
    })

def _egg_inventory_state(egg_id: int) -> dict:
    inventory = _event_inventory_state()
    return inventory.get(str(egg_id), {})

def _egg_stats_state(egg_id: int) -> dict:
    stats = _event_stats_state()
    return (stats.get("eggs") or {}).get(str(egg_id), {
        "total_opens": 0,
        "total_real_wins": 0,
        "soft_losses": 0,
    })

def _rollover_unused_stock_to_egg(target_egg_id: int):
    if target_egg_id <= 1:
        return

    cols = _easter_collections()
    events_col = cols["events"]

    doc = events_col.find_one({"_id": EASTER_EVENT_ID}) or {}
    pools = doc.get("prize_pool_by_egg", {}) or {}
    rollover_done = doc.get("rollover_done_from_egg", {}) or {}

    inc_ops = {}
    set_ops = {}
    moved_any = False

    for source_egg_id in range(1, target_egg_id):
        source_key = str(source_egg_id)

        if rollover_done.get(source_key):
            continue

        source_pool = pools.get(source_key, {}) or {}
        for prize_name, qty in source_pool.items():
            qty = int(qty or 0)
            if qty <= 0:
                continue

            inc_ops[f"prize_pool_by_egg.{target_egg_id}.{prize_name}"] = (
                inc_ops.get(f"prize_pool_by_egg.{target_egg_id}.{prize_name}", 0) + qty
            )
            inc_ops[f"prize_pool_by_egg.{source_egg_id}.{prize_name}"] = (
                inc_ops.get(f"prize_pool_by_egg.{source_egg_id}.{prize_name}", 0) - qty
            )
            moved_any = True

        set_ops[f"rollover_done_from_egg.{source_key}"] = True

    if set_ops:
        update = {"$set": set_ops}
        if moved_any:
            update["$inc"] = inc_ops
        events_col.update_one({"_id": EASTER_EVENT_ID}, update)

def _remaining_prizes(inventory: dict) -> int:
    total = 0
    for value in inventory.values():
        if isinstance(value, dict):
            total += _remaining_prizes(value)
        else:
            total += max(0, int(value))
    return total


def _adaptive_win_chance(inventory: dict, stats: dict) -> float:
    remaining_stock = _remaining_prizes(inventory)
    if remaining_stock <= 0:
        return 0.0

    total_opens = max(0, int(stats.get("total_opens", 0)))
    base_target_opens = max(1, int(EASTER_EVENT.get("target_total_opens", 500)))
    scale_factor = max(1, int(EASTER_EVENT.get("egg_scale_factor", 3)))

    scaled_target_opens = max(base_target_opens, total_opens * scale_factor)
    remaining_expected_opens = max(1, scaled_target_opens - total_opens)

    base_chance = remaining_stock / remaining_expected_opens
    return max(0.01, min(0.35, base_chance))


def _should_win(inventory: dict, stats: dict) -> bool:
    chance = _adaptive_win_chance(inventory, stats)
    return random.random() < chance

def add_easter_contribution(contributor_id: str, contributor_name: str, egg_id: int, prizes: dict):
    clean_prizes = {
        str(k): int(v)
        for k, v in prizes.items()
        if str(k).strip() and int(v) > 0
    }
    if not clean_prizes:
        return

    egg_id = int(egg_id)
    if egg_id < 1 or egg_id > len(EASTER_EVENT["eggs"]):
        raise ValueError("Invalid egg_id")

    cols = _easter_collections()
    events_col = cols["events"]
    contributions_col = cols["contributions"]

    inc_fields = {
        f"prize_pool_by_egg.{egg_id}.{k}": v
        for k, v in clean_prizes.items()
    }

    update_doc = {
        "$setOnInsert": {
            "_id": EASTER_EVENT_ID,
            "title": EASTER_EVENT["title"],
            "created_at": datetime.now(timezone.utc),
        },
        "$inc": inc_fields,
        "$set": {
            f"contributors.{contributor_id}.name": contributor_name,
            f"contributors.{contributor_id}.discord_id": contributor_id,
        }
    }

    for prize_name, qty in clean_prizes.items():
        update_doc["$inc"][f"contributors.{contributor_id}.totals.{prize_name}"] = qty

    events_col.update_one(
        {"_id": EASTER_EVENT_ID},
        update_doc,
        upsert=True
    )

    contributions_col.insert_one({
        "event_id": EASTER_EVENT_ID,
        "egg_id": egg_id,
        "contributor_id": contributor_id,
        "contributor_name": contributor_name,
        "prizes": clean_prizes,
        "created_at": datetime.now(timezone.utc),
    })

def _pick_weighted_prize(egg_id: int) -> str | None:
    inventory = _egg_inventory_state(egg_id)
    available = [(name, int(qty)) for name, qty in inventory.items() if int(qty) > 0]
    if not available:
        return None

    total_weight = sum(qty for _, qty in available)
    roll = random.randint(1, total_weight)

    current = 0
    chosen = None
    for name, qty in available:
        current += qty
        if roll <= current:
            chosen = name
            break

    if not chosen:
        return None

    cols = _easter_collections()
    events_col = cols["events"]

    result = events_col.update_one(
        {
            "_id": EASTER_EVENT_ID,
            f"prize_pool_by_egg.{egg_id}.{chosen}": {"$gt": 0}
        },
        {
            "$inc": {
                f"prize_pool_by_egg.{egg_id}.{chosen}": -1
            }
        }
    )
    if result.modified_count == 0:
        return None
    return chosen


def _pick_soft_loss_reward() -> str:
    return random.choice(EASTER_EVENT["soft_loss_rewards"])

def _is_easter_event_over() -> bool:
    ends_at = EASTER_EVENT.get("ends_at")
    if not ends_at:
        return False
    return datetime.now(timezone.utc) > ends_at

def _next_available_eggs():
    if _is_easter_testing_enabled() and EASTER_TESTING.get("bypass_unlocks"):
        return len(EASTER_EVENT["eggs"])

    now = datetime.now(timezone.utc)

    available = 0
    for egg in EASTER_EVENT["eggs"]:
        unlock_at = egg.get("unlock_at")
        if unlock_at and now >= unlock_at:
            available += 1

    return available

def _claim_easter_egg_slot(discord_id: str, egg_id: int) -> bool:
    col = get_db("Website")["easter_user_opens"]
    now = datetime.now(timezone.utc)

    result = col.update_one(
        {
            "_id": f"{EASTER_EVENT_ID}:{discord_id}",
            f"opened.{egg_id}": {"$exists": False},
        },
        {
            "$set": {
                "event_id": EASTER_EVENT_ID,
                "discord_id": str(discord_id),
                f"opened.{egg_id}": {
                    "pending": True,
                    "opened_at": now.isoformat(),
                },
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            }
        },
        upsert=True
    )

    return result.modified_count > 0 or result.upserted_id is not None

def _is_easter_testing_enabled() -> bool:
    return bool(EASTER_TESTING.get("enabled", False))

def _session_role_ids() -> set[str]:
    return {str(r) for r in (session.get("roles") or [])}

def _is_easter_member() -> bool:
    return bool(session.get("is_member", False))

def _easter_access_state() -> dict:
    logged_in = "discord_id" in session
    is_member = _is_easter_member() if logged_in else False
    can_open = logged_in and is_member

    if not logged_in:
        gate_message = "Log in with Discord to open eggs."
    elif not is_member:
        gate_message = "You must be a server member to open eggs."
    else:
        gate_message = None

    return {
        "unlocked": True,
        "logged_in": logged_in,
        "is_member": is_member,
        "can_open": can_open,
        "gate_message": gate_message,
    }


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

def serialize_mongo(obj):
    if isinstance(obj, list):
        return [serialize_mongo(x) for x in obj]
    elif isinstance(obj, dict):
        return {
            k: serialize_mongo(str(v) if isinstance(v, ObjectId) else v)
            for k, v in obj.items()
        }
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj

_ROLE_CACHE = {
    "data": None,
    "expires": 0,
}

def fetch_role_mapping(guild_id, ttl=300):
    now = time.time()
    if _ROLE_CACHE["data"] is not None and now < _ROLE_CACHE["expires"]:
        return _ROLE_CACHE["data"]

    url = f"https://discord.com/api/guilds/{guild_id}/roles"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    roles = response.json()
    mapping = {
        role["id"]: {
            "name": role["name"],
            "color": f"#{int(role['color']):06x}" if role["color"] != 0 else "#888",
            "position": role["position"]
        }
        for role in roles
    }

    _ROLE_CACHE["data"] = mapping
    _ROLE_CACHE["expires"] = now + ttl
    return mapping

WIKI_API = "https://hayday.fandom.com/api.php"
WIKI_USER_AGENT = "HayDay/wiki-products (contact: your-email@example.com)"
WIKI_CACHE_ID = "wiki_products_v1"
WIKI_TTL = 60 * 60 * 24  # 24h


def _mongo():
    return get_db()


BACKUP_R2_BUCKET = os.getenv("BACKUP_R2_BUCKET") or os.getenv("R2_BACKUP_BUCKET") or "mongo-backups"
BACKUP_DB_PREFIX = os.getenv("BACKUP_DB_PREFIX", "db").strip("/")
BACKUP_DISCORD_PREFIX = os.getenv("BACKUP_DISCORD_PREFIX", "discord").strip("/")
BACKUP_RESTORE_TIMEOUT_SECONDS = int(os.getenv("BACKUP_RESTORE_TIMEOUT_SECONDS", "120"))
BACKUP_JOB_TTL_SECONDS = int(os.getenv("BACKUP_JOB_TTL_SECONDS", "900"))

BACKUP_COLLECTION_SPECS = [
    {
        "id": "level",
        "label": "Level / XP",
        "source_db": "hayday",
        "source_collection": "level",
        "target_collection": "hayday_level",
        "id_field": "_id",
        "id_type": "str",
        "restore_fields": {
            "level": "Level",
            "xp": "Total XP",
            "message_count": "Message count",
            "xp_boost_until": "XP boost until",
            "perm_xp_tier": "Permanent XP tier",
        },
    },
    {
        "id": "economy",
        "label": "Economy / Daily / Pet",
        "source_db": "Economy",
        "source_collection": "Users",
        "target_collection": "Economy_Users",
        "id_field": "_id",
        "id_type": "int",
        "restore_fields": {
            "coins": "Coins",
            "streak": "Daily streak",
            "last_daily": "Last daily claim",
            "daily_upgrade_tier": "Daily upgrade tier",
            "passive_income_tier": "Passive income tier",
            "owned_items": "Owned shop items",
            "double_daily_next": "Double daily pending",
            "pet": "Pet data",
        },
    },
    {
        "id": "website_user",
        "label": "Website Profile",
        "source_db": "Website",
        "source_collection": "users",
        "target_collection": "Website_users",
        "id_field": "_id",
        "id_type": "str",
        "restore_fields": {
            "hay_day_id": "Hay Day tag",
            "bio": "Profile bio",
            "public_profile": "Public profile",
            "featured_achievement": "Featured achievement",
            "roles": "Stored role IDs",
            "auctions_won": "Auctions won",
            "top_bidder_count": "Top bidder count",
        },
    },
    {
        "id": "username",
        "label": "Username Cache",
        "source_db": "Website",
        "source_collection": "usernames",
        "target_collection": "Website_usernames",
        "id_field": "_id",
        "id_type": "str",
        "restore_fields": {
            "username": "Username",
            "display_name": "Display name",
            "avatar": "Avatar URL",
            "avatar_hash": "Avatar hash",
            "roles": "Cached role IDs",
        },
    },
    {
        "id": "mentions",
        "label": "Mentions",
        "source_db": "Mentions",
        "source_collection": "Amount",
        "target_collection": "Mentions_Amount",
        "id_field": "id",
        "id_type": "int",
        "restore_fields": {
            "Mentions": "Mention count",
        },
    },
    {
        "id": "birthday",
        "label": "Birthday",
        "source_db": "Birthdays",
        "source_collection": "Users",
        "target_collection": "Birthdays_Users",
        "id_field": "user_id",
        "id_type": "str",
        "restore_fields": {
            "day": "Birthday day",
            "month": "Birthday month",
            "timezone": "Birthday timezone",
        },
    },
]
BACKUP_COLLECTION_SPEC_BY_ID = {spec["id"]: spec for spec in BACKUP_COLLECTION_SPECS}
BACKUP_ADDITIVE_FIELDS = {
    "level": {"xp", "message_count"},
    "economy": {"coins", "streak"},
    "website_user": {"auctions_won", "top_bidder_count"},
    "mentions": {"Mentions"},
}


def _backup_can_add_field(spec_id: str, field: str) -> bool:
    return field in BACKUP_ADDITIVE_FIELDS.get(spec_id, set())


def _backup_required_xp(level: int) -> int:
    level = max(1, int(level))
    return 100 * (level ** 2) + 100 * level + 100


def _backup_level_from_total_xp(total_xp) -> int:
    try:
        xp = max(0, int(total_xp or 0))
    except (TypeError, ValueError):
        xp = 0

    level = 1
    while xp >= _backup_required_xp(level):
        level += 1
    return level


def _backup_numeric_value(value, default=0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        return int(float(stripped))
    raise ValueError("Selected value is not numeric.")


def _backup_add_preview(spec_id: str, field: str, backup_doc: dict | None, live_doc: dict | None) -> str | None:
    if not _backup_can_add_field(spec_id, field) or not _backup_has_field(backup_doc, field):
        return None
    try:
        backup_value = _backup_numeric_value(_backup_get_field(backup_doc, field))
        live_value = _backup_numeric_value(_backup_get_field(live_doc, field), 0)
    except (TypeError, ValueError):
        return None

    added_value = live_value + backup_value
    if spec_id == "level" and field == "xp":
        return f"If added: {live_value:,} + {backup_value:,} = {added_value:,} XP, level {_backup_level_from_total_xp(added_value):,}"
    return f"If added: {live_value:,} + {backup_value:,} = {added_value:,}"


def _backup_normalize_restore_selections(selections: dict | None) -> dict[str, dict[str, str]]:
    cleaned: dict[str, dict[str, str]] = {}
    for spec_id, fields in (selections or {}).items():
        spec = BACKUP_COLLECTION_SPEC_BY_ID.get(spec_id)
        if not spec:
            continue

        if isinstance(fields, dict):
            requested = fields.items()
        elif isinstance(fields, (list, tuple, set)):
            requested = ((field, "replace") for field in fields)
        else:
            continue

        allowed = set(spec["restore_fields"].keys())
        selected_fields: dict[str, str] = {}
        for field, mode in requested:
            if field not in allowed:
                continue
            selected_fields[field] = "add" if mode == "add" and _backup_can_add_field(spec_id, field) else "replace"

        if selected_fields:
            cleaned[spec_id] = selected_fields

    return cleaned


def _backup_env_value(*names):
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


def _backup_jobs_collection():
    return get_db("Website")["backup_jobs"]


def _backup_prune_jobs():
    cutoff = time.time() - BACKUP_JOB_TTL_SECONDS
    cutoff_date = datetime.fromtimestamp(cutoff, tz=timezone.utc)
    _backup_jobs_collection().delete_many({"updated_at": {"$lt": cutoff_date}})


def _backup_set_job(job_id: str, **updates):
    updates["updated_at"] = datetime.now(timezone.utc)
    _backup_jobs_collection().update_one({"_id": job_id}, {"$set": updates})


def _backup_public_job(job_id: str) -> dict | None:
    _backup_prune_jobs()
    job = _backup_jobs_collection().find_one({"_id": job_id})
    if not job:
        return None
    return {
        "job_id": job_id,
        "kind": job.get("kind"),
        "status": job.get("status"),
        "message": job.get("message"),
        "error": job.get("error"),
        "result": job.get("result"),
        "created_at": serialize_mongo(job.get("created_at")),
        "updated_at": serialize_mongo(job.get("updated_at")),
    }


def _backup_start_job(kind: str, message: str, worker):
    job_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    _backup_prune_jobs()
    _backup_jobs_collection().insert_one({
        "_id": job_id,
        "kind": kind,
        "status": "running",
        "message": message,
        "created_at": now,
        "updated_at": now,
        "actor_id": session.get("discord_id"),
    })

    def run_job():
        def update(message_text: str):
            _backup_set_job(job_id, message=message_text)

        try:
            with app.app_context():
                result = worker(update)
            _backup_set_job(job_id, status="done", message="Done", result=result, error=None)
        except Exception as exc:
            app.logger.exception("Backup job %s failed", job_id)
            _backup_set_job(job_id, status="error", message="Failed", error=str(exc))

    threading.Thread(target=run_job, name=f"backup-job-{job_id[:8]}", daemon=True).start()
    return _backup_public_job(job_id)


def _backup_s3_client():
    endpoint = _backup_env_value("BACKUP_R2_S3_ENDPOINT", "S3_ENDPOINT", "R2_S3_ENDPOINT")
    access_key = _backup_env_value("BACKUP_R2_ACCESS_KEY_ID", "S3_KEY", "R2_ACCESS_KEY_ID")
    secret_key = _backup_env_value("BACKUP_R2_SECRET_ACCESS_KEY", "S3_SECRET", "R2_SECRET_ACCESS_KEY")
    missing = [
        label
        for label, value in (
            ("BACKUP_R2_S3_ENDPOINT or S3_ENDPOINT", endpoint),
            ("BACKUP_R2_ACCESS_KEY_ID or S3_KEY", access_key),
            ("BACKUP_R2_SECRET_ACCESS_KEY or S3_SECRET", secret_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Missing backup R2 configuration: " + ", ".join(missing))

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(s3={"addressing_style": "path"}),
    )


def _backup_key_type(key: str) -> str | None:
    key = (key or "").strip()
    if key.startswith(f"{BACKUP_DB_PREFIX}/") and key.endswith(".archive.gz"):
        return "database"
    if key.startswith(f"{BACKUP_DISCORD_PREFIX}/") and key.endswith(".json.gz"):
        return "discord"
    return None


def _backup_validate_key(key: str, expected_type: str | None = None) -> str:
    key = (key or "").strip()
    if not key or key.startswith(("/", "\\")) or ".." in key.replace("\\", "/"):
        raise ValueError("Invalid backup key.")
    key_type = _backup_key_type(key)
    if not key_type:
        raise ValueError("Unsupported backup key.")
    if expected_type and key_type != expected_type:
        raise ValueError(f"Expected a {expected_type} backup key.")
    return key


def _backup_parse_timestamp(key: str) -> datetime | None:
    match = re.search(
        r"(?:backup|discord-backup)-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)",
        key or "",
    )
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _backup_mongorestore_path() -> str | None:
    configured = os.getenv("MONGORESTORE_BIN", "mongorestore")
    found = shutil.which(configured)
    if found:
        return found
    configured_path = Path(configured)
    if configured_path.exists():
        return str(configured_path)
    return None


def _backup_sanitize_process_output(text: str | None) -> str:
    text = text or ""
    if MONGO_URI:
        text = text.replace(MONGO_URI, "<MONGO_URI>")
    return text[-1600:]


def _backup_trim_value(value, depth=0):
    value = serialize_mongo(value)
    if depth > 5:
        return "..."
    if isinstance(value, dict):
        items = list(value.items())
        trimmed = {k: _backup_trim_value(v, depth + 1) for k, v in items[:80]}
        if len(items) > 80:
            trimmed["..."] = f"{len(items) - 80} more fields"
        return trimmed
    if isinstance(value, list):
        trimmed = [_backup_trim_value(v, depth + 1) for v in value[:40]]
        if len(value) > 40:
            trimmed.append(f"... {len(value) - 40} more items")
        return trimmed
    if isinstance(value, str) and len(value) > 1200:
        return value[:1200] + "... truncated"
    return value


def _backup_get_field(doc: dict | None, field: str):
    if not doc:
        return None
    return doc.get(field)


def _backup_has_field(doc: dict | None, field: str) -> bool:
    return bool(doc) and field in doc


def _backup_user_query(spec: dict, user_id: str) -> dict | None:
    raw = str(user_id or "").strip()
    if not raw:
        return None
    if spec["id_type"] == "int":
        if not raw.isdigit():
            return None
        value = int(raw)
    else:
        value = raw
    return {spec["id_field"]: value}


def _backup_live_doc(spec: dict, user_id: str) -> dict | None:
    query = _backup_user_query(spec, user_id)
    if not query:
        return None
    return get_db(spec["source_db"])[spec["source_collection"]].find_one(query)


def _backup_download_to_temp(key: str) -> str:
    key_type = _backup_key_type(key)
    suffix = ".archive.gz" if key_type == "database" else ".json.gz"
    handle = tempfile.NamedTemporaryFile(prefix="hayday-backup-", suffix=suffix, delete=False)
    path = handle.name
    handle.close()
    _backup_s3_client().download_file(BACKUP_R2_BUCKET, key, path)
    return path


def _backup_restore_collection_from_archive(archive_path: str, temp_db_name: str, spec: dict):
    restore_bin = _backup_mongorestore_path()
    if not restore_bin:
        raise RuntimeError(
            "MongoDB Database Tools are not installed. Deploy the updated Docker image so mongorestore is available."
        )
    if not MONGO_URI:
        raise RuntimeError("Missing MONGO_URI; cannot inspect database backup archives.")

    source_ns = f"{spec['source_db']}.{spec['source_collection']}"
    target_ns = f"{temp_db_name}.{spec['target_collection']}"
    cmd = [
        restore_bin,
        f"--uri={MONGO_URI}",
        f"--archive={archive_path}",
        "--gzip",
        f"--nsInclude={source_ns}",
        f"--nsFrom={source_ns}",
        f"--nsTo={target_ns}",
        "--drop",
        "--noIndexRestore",
        "--quiet",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=BACKUP_RESTORE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"mongorestore timed out after {BACKUP_RESTORE_TIMEOUT_SECONDS}s") from exc

    if result.returncode != 0:
        detail = _backup_sanitize_process_output((result.stderr or "") + "\n" + (result.stdout or ""))
        raise RuntimeError(f"mongorestore failed for {source_ns}: {detail}")


def _backup_restore_collections_from_archive(archive_path: str, temp_db_name: str, specs: list[dict]):
    restore_bin = _backup_mongorestore_path()
    if not restore_bin:
        raise RuntimeError(
            "MongoDB Database Tools are not installed. Deploy the updated Docker image so mongorestore is available."
        )
    if not MONGO_URI:
        raise RuntimeError("Missing MONGO_URI; cannot inspect database backup archives.")
    if not specs:
        return

    cmd = [
        restore_bin,
        f"--uri={MONGO_URI}",
        f"--archive={archive_path}",
        "--gzip",
        "--drop",
        "--noIndexRestore",
        "--quiet",
    ]
    for spec in specs:
        source_ns = f"{spec['source_db']}.{spec['source_collection']}"
        target_ns = f"{temp_db_name}.{spec['target_collection']}"
        cmd.extend([
            f"--nsInclude={source_ns}",
            f"--nsFrom={source_ns}",
            f"--nsTo={target_ns}",
        ])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=BACKUP_RESTORE_TIMEOUT_SECONDS * max(1, len(specs)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"mongorestore timed out after {BACKUP_RESTORE_TIMEOUT_SECONDS * max(1, len(specs))}s"
        ) from exc

    if result.returncode == 0:
        return

    detail = _backup_sanitize_process_output((result.stderr or "") + "\n" + (result.stdout or ""))
    app.logger.warning("Single-pass mongorestore failed, falling back to per-collection restore: %s", detail)
    for spec in specs:
        _backup_restore_collection_from_archive(archive_path, temp_db_name, spec)


def _backup_extract_user_documents(
    key: str,
    user_id: str,
    spec_ids: list[str] | None = None,
    target_user_id: str | None = None,
) -> dict:
    key = _backup_validate_key(key, "database")
    source_user_id = str(user_id or "").strip()
    target_user_id = str(target_user_id or source_user_id).strip()
    selected_specs = [
        BACKUP_COLLECTION_SPEC_BY_ID[spec_id]
        for spec_id in (spec_ids or [spec["id"] for spec in BACKUP_COLLECTION_SPECS])
        if spec_id in BACKUP_COLLECTION_SPEC_BY_ID
    ]
    if not selected_specs:
        raise ValueError("No valid backup sections selected.")

    archive_path = None
    temp_db_name = f"bkp_{uuid.uuid4().hex[:20]}"
    docs: dict[str, dict] = {}

    try:
        archive_path = _backup_download_to_temp(key)
        _backup_restore_collections_from_archive(archive_path, temp_db_name, selected_specs)

        temp_db = mongo_client[temp_db_name]
        for spec in selected_specs:
            backup_query = _backup_user_query(spec, source_user_id)
            backup_doc = temp_db[spec["target_collection"]].find_one(backup_query) if backup_query else None
            docs[spec["id"]] = {
                "spec": spec,
                "backup_doc": backup_doc,
                "live_doc": _backup_live_doc(spec, target_user_id),
            }
    finally:
        try:
            mongo_client.drop_database(temp_db_name)
        except Exception as cleanup_error:
            app.logger.warning("Failed to drop temporary backup database %s: %s", temp_db_name, cleanup_error)
        if archive_path:
            try:
                os.remove(archive_path)
            except OSError:
                pass

    return {
        "key": key,
        "type": "database",
        "created_at": _backup_parse_timestamp(key),
        "user_id": source_user_id,
        "source_user_id": source_user_id,
        "target_user_id": target_user_id,
        "docs": docs,
    }


def _backup_database_inspect_payload(key: str, user_id: str, target_user_id: str | None = None) -> dict:
    extracted = _backup_extract_user_documents(key, user_id, target_user_id=target_user_id)
    sections = []
    for spec in BACKUP_COLLECTION_SPECS:
        row = extracted["docs"].get(spec["id"], {})
        backup_doc = row.get("backup_doc")
        live_doc = row.get("live_doc")
        fields = []
        for field, label in spec["restore_fields"].items():
            fields.append({
                "field": field,
                "label": label,
                "available": _backup_has_field(backup_doc, field),
                "additive": _backup_can_add_field(spec["id"], field),
                "add_preview": _backup_add_preview(spec["id"], field, backup_doc, live_doc),
                "backup_value": _backup_trim_value(_backup_get_field(backup_doc, field)),
                "live_value": _backup_trim_value(_backup_get_field(live_doc, field)),
            })
        sections.append({
            "id": spec["id"],
            "label": spec["label"],
            "source": f"{spec['source_db']}.{spec['source_collection']}",
            "found_in_backup": bool(backup_doc),
            "found_live": bool(live_doc),
            "fields": fields,
            "backup_doc": _backup_trim_value(backup_doc),
            "live_doc": _backup_trim_value(live_doc),
        })

    return {
        "ok": True,
        "type": "database",
        "key": extracted["key"],
        "created_at": serialize_mongo(extracted["created_at"]),
        "user_id": extracted["user_id"],
        "source_user_id": extracted["source_user_id"],
        "target_user_id": extracted["target_user_id"],
        "sections": sections,
    }


def _backup_read_discord_snapshot(key: str) -> dict:
    key = _backup_validate_key(key, "discord")
    path = None
    try:
        path = _backup_download_to_temp(key)
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    finally:
        if path:
            try:
                os.remove(path)
            except OSError:
                pass


def _backup_discord_inspect_payload(key: str, user_id: str | None = None, target_user_id: str | None = None) -> dict:
    key = _backup_validate_key(key, "discord")
    snapshot = _backup_read_discord_snapshot(key)
    roles = snapshot.get("roles", []) or []
    role_map = {str(role.get("id")): role for role in roles}
    member = None
    member_roles = []
    member_role_ids = []
    source_user_id = str(user_id or "").strip()
    target_user_id = str(target_user_id or source_user_id).strip()
    if user_id:
        member = next(
            (m for m in snapshot.get("members", []) or [] if str(m.get("id")) == source_user_id),
            None,
        )
        if member:
            member_role_ids = [str(role_id) for role_id in member.get("role_ids", []) or []]
            member_roles = [
                role_map.get(str(role_id), {"id": role_id, "name": str(role_id), "color": None})
                for role_id in member.get("role_ids", []) or []
            ]

    return {
        "ok": True,
        "type": "discord",
        "key": key,
        "created_at": serialize_mongo(_backup_parse_timestamp(key)),
        "meta": snapshot.get("meta", {}),
        "guild": snapshot.get("guild", {}),
        "counts": {
            "roles": len(roles),
            "categories": len(snapshot.get("categories", []) or []),
            "text_channels": len(snapshot.get("text_channels", []) or []),
            "voice_channels": len(snapshot.get("voice_channels", []) or []),
            "forum_channels": len(snapshot.get("forum_channels", []) or []),
            "members": len(snapshot.get("members", []) or []),
            "emojis": len(snapshot.get("emojis", []) or []),
        },
        "member": _backup_trim_value(member),
        "member_roles": _backup_trim_value(member_roles),
        "member_role_ids": _backup_trim_value(member_role_ids),
        "source_user_id": source_user_id,
        "target_user_id": target_user_id,
    }


def _backup_discord_member_role_ids(key: str, user_id: str, target_user_id: str | None = None) -> dict:
    key = _backup_validate_key(key, "discord")
    snapshot = _backup_read_discord_snapshot(key)
    user_id_str = str(user_id or "").strip()
    target_user_id = str(target_user_id or user_id_str).strip()
    if not user_id_str:
        raise ValueError("Enter a Discord user ID before restoring Discord roles.")

    member = next(
        (m for m in snapshot.get("members", []) or [] if str(m.get("id")) == user_id_str),
        None,
    )
    if not member:
        raise ValueError("No member was found for that user ID in this Discord snapshot.")

    role_ids = []
    for role_id in member.get("role_ids", []) or []:
        role_id_str = str(role_id).strip()
        if role_id_str and role_id_str not in role_ids:
            role_ids.append(role_id_str)

    if not role_ids:
        raise ValueError("This member snapshot does not contain any role IDs to restore.")

    return {
        "key": key,
        "created_at": _backup_parse_timestamp(key),
        "user_id": target_user_id,
        "source_user_id": user_id_str,
        "target_user_id": target_user_id,
        "guild": snapshot.get("guild", {}),
        "member": member,
        "role_ids": role_ids,
    }


def _backup_database_member_role_ids(key: str, user_id: str, target_user_id: str | None = None) -> dict:
    key = _backup_validate_key(key, "database")
    user_id_str = str(user_id or "").strip()
    target_user_id = str(target_user_id or user_id_str).strip()
    if not user_id_str:
        raise ValueError("Enter a Discord user ID before restoring Discord roles.")

    extracted = _backup_extract_user_documents(key, user_id_str, ["username", "website_user"], target_user_id)
    role_ids = []
    sources = []

    for spec_id in ("username", "website_user"):
        row = extracted["docs"].get(spec_id, {})
        spec = row.get("spec") or BACKUP_COLLECTION_SPEC_BY_ID.get(spec_id, {})
        backup_doc = row.get("backup_doc") or {}
        roles = backup_doc.get("roles") or []
        if not isinstance(roles, list):
            continue

        source_added = 0
        for role_id in roles:
            role_id_str = str(role_id).strip()
            if not role_id_str or not role_id_str.isdigit() or role_id_str in role_ids:
                continue
            role_ids.append(role_id_str)
            source_added += 1

        if source_added:
            sources.append(f"{spec.get('source_db', 'Website')}.{spec.get('source_collection', spec_id)}")

    if not role_ids:
        raise ValueError("This database backup does not contain cached role IDs for that user.")

    return {
        "key": key,
        "created_at": extracted["created_at"],
        "user_id": target_user_id,
        "source_user_id": user_id_str,
        "target_user_id": target_user_id,
        "guild": {},
        "member": {},
        "role_ids": role_ids,
        "sources": sources,
    }


def _backup_restore_discord_roles(key: str, user_id: str, target_user_id: str | None = None) -> dict:
    key_type = _backup_key_type(key)
    if key_type == "discord":
        snapshot = _backup_discord_member_role_ids(key, user_id, target_user_id)
    elif key_type == "database":
        snapshot = _backup_database_member_role_ids(key, user_id, target_user_id)
    else:
        raise ValueError("Unsupported backup key.")

    bot_base = (os.getenv("BOT_WEBHOOK_URL") or "").rstrip("/")
    bot_key = os.getenv("BOT_WEBHOOK_KEY")
    if not bot_base or not bot_key:
        raise RuntimeError("Missing BOT_WEBHOOK_URL or BOT_WEBHOOK_KEY on the website.")

    response = requests.post(
        f"{bot_base}/webhook/backups/restore-roles",
        headers={"Authorization": bot_key},
        json={
            "user_id": snapshot["user_id"],
            "role_ids": snapshot["role_ids"],
            "backup_key": snapshot["key"],
            "staff_id": session.get("discord_id"),
            "staff_username": session.get("username"),
            "reason": f"Restored from backup dashboard by {session.get('username') or session.get('discord_id') or 'website staff'}",
        },
        timeout=35,
    )
    try:
        bot_result = response.json()
    except ValueError:
        bot_result = {"error": response.text[:1000]}

    if response.status_code >= 400 or bot_result.get("success") is False:
        raise RuntimeError(bot_result.get("error") or f"Bot role restore failed with HTTP {response.status_code}.")

    result = {
        "ok": True,
        "type": "discord_roles",
        "key": snapshot["key"],
        "created_at": serialize_mongo(snapshot["created_at"]),
        "user_id": snapshot["user_id"],
        "source_user_id": snapshot["source_user_id"],
        "target_user_id": snapshot["target_user_id"],
        "role_ids": snapshot["role_ids"],
        "bot": bot_result,
    }

    get_db("Website")["backup_restores"].insert_one({
        "backup_key": snapshot["key"],
        "backup_created_at": snapshot["created_at"],
        "user_id": snapshot["target_user_id"],
        "source_user_id": snapshot["source_user_id"],
        "target_user_id": snapshot["target_user_id"],
        "actor_id": session.get("discord_id"),
        "actor_username": session.get("username"),
        "restore_type": "discord_roles",
        "role_ids": snapshot["role_ids"],
        "bot_result": serialize_mongo(bot_result),
        "created_at": datetime.now(timezone.utc),
    })

    return result


def _backup_list_objects() -> list[dict]:
    s3 = _backup_s3_client()
    backups = []
    for prefix in (f"{BACKUP_DB_PREFIX}/", f"{BACKUP_DISCORD_PREFIX}/"):
        continuation_token = None
        while True:
            kwargs = {"Bucket": BACKUP_R2_BUCKET, "Prefix": prefix, "MaxKeys": 1000}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
            response = s3.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []) or []:
                key = obj.get("Key", "")
                key_type = _backup_key_type(key)
                if not key_type:
                    continue
                created_at = _backup_parse_timestamp(key)
                backups.append({
                    "key": key,
                    "type": key_type,
                    "name": key.split("/")[-1],
                    "size_bytes": obj.get("Size", 0),
                    "size_mb": round((obj.get("Size", 0) or 0) / (1024 * 1024), 2),
                    "last_modified": serialize_mongo(obj.get("LastModified")),
                    "created_at": serialize_mongo(created_at),
                    "date": created_at.date().isoformat() if created_at else None,
                })
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
            if not continuation_token:
                break

    backups.sort(key=lambda row: row.get("created_at") or row.get("last_modified") or "", reverse=True)
    return backups


def _backup_restore_selected_fields(
    key: str,
    user_id: str,
    selections: dict,
    target_user_id: str | None = None,
) -> dict:
    source_user_id = str(user_id or "").strip()
    target_user_id = str(target_user_id or source_user_id).strip()
    cleaned = _backup_normalize_restore_selections(selections)
    if not cleaned:
        raise ValueError("Select at least one restorable field.")

    extracted = _backup_extract_user_documents(key, source_user_id, list(cleaned.keys()), target_user_id)
    updates = []

    for spec_id, field_modes in cleaned.items():
        row = extracted["docs"].get(spec_id, {})
        spec = row.get("spec") or BACKUP_COLLECTION_SPEC_BY_ID[spec_id]
        backup_doc = row.get("backup_doc")
        live_doc = row.get("live_doc")
        query = _backup_user_query(spec, target_user_id)

        if not query or not backup_doc:
            updates.append({
                "section": spec_id,
                "label": spec["label"],
                "status": "skipped",
                "reason": "No matching document found in backup.",
            })
            continue

        set_values = {}
        before_values = {}
        restored_values = {}
        skipped_fields = []
        operations = {}
        operation_details = {}
        recalculate_level_from_added_xp = False

        for field, mode in field_modes.items():
            if not _backup_has_field(backup_doc, field):
                skipped_fields.append(field)
                continue

            backup_value = _backup_get_field(backup_doc, field)
            live_value = _backup_get_field(live_doc, field)
            before_values[field] = _backup_get_field(live_doc, field)

            if mode == "add":
                try:
                    backup_number = _backup_numeric_value(backup_value)
                    live_number = _backup_numeric_value(live_value, 0)
                except (TypeError, ValueError):
                    skipped_fields.append(field)
                    continue

                new_value = live_number + backup_number
                set_values[field] = new_value
                restored_values[field] = new_value
                operations[field] = "add"
                operation_details[field] = {
                    "mode": "add",
                    "backup_value": backup_value,
                    "live_value": live_value,
                    "new_value": new_value,
                }
                if spec_id == "level" and field == "xp":
                    recalculate_level_from_added_xp = True
            else:
                set_values[field] = backup_value
                restored_values[field] = backup_value
                operations[field] = "replace"

        if spec_id == "level" and recalculate_level_from_added_xp and "xp" in set_values:
            new_level = _backup_level_from_total_xp(set_values["xp"])
            set_values["level"] = new_level
            before_values.setdefault("level", _backup_get_field(live_doc, "level"))
            restored_values["level"] = new_level
            operations["level"] = "recalculate_from_added_xp"
            operation_details["level"] = {
                "mode": "recalculate_from_added_xp",
                "xp": set_values["xp"],
                "new_value": new_level,
            }

        if not set_values:
            updates.append({
                "section": spec_id,
                "label": spec["label"],
                "status": "skipped",
                "reason": "Selected fields were not present in backup.",
                "skipped_fields": skipped_fields,
            })
            continue

        collection = get_db(spec["source_db"])[spec["source_collection"]]
        result = collection.update_one(query, {"$set": set_values}, upsert=True)
        updates.append({
            "section": spec_id,
            "label": spec["label"],
            "source": f"{spec['source_db']}.{spec['source_collection']}",
            "status": "restored",
            "fields": list(set_values.keys()),
            "field_labels": {
                field: spec["restore_fields"].get(field, field)
                for field in set_values.keys()
            },
            "skipped_fields": skipped_fields,
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
            "upserted_id": str(result.upserted_id) if result.upserted_id is not None else None,
            "before": _backup_trim_value(before_values),
            "restored": _backup_trim_value(restored_values),
            "operations": operations,
            "operation_details": _backup_trim_value(operation_details),
        })

    get_db("Website")["backup_restores"].insert_one({
        "backup_key": extracted["key"],
        "backup_created_at": extracted["created_at"],
        "user_id": target_user_id,
        "source_user_id": source_user_id,
        "target_user_id": target_user_id,
        "actor_id": session.get("discord_id"),
        "actor_username": session.get("username"),
        "selections": cleaned,
        "updates": serialize_mongo(updates),
        "created_at": datetime.now(timezone.utc),
    })

    return {
        "ok": True,
        "key": extracted["key"],
        "user_id": target_user_id,
        "source_user_id": source_user_id,
        "target_user_id": target_user_id,
        "updates": updates,
    }




# Any template that contains "Infobox" and is not a navbox/template cruft counts as an item page
def looks_like_item_templates(templates: list[str]) -> bool:
    t = " ".join(templates).lower()
    if "infobox" not in t:
        return False
    # exclude common non-item boxes if needed
    return not ("navbox" in t or "sidebar" in t)

_cache_products = {"data": None, "ts": 0}
_CACHE_TTL = 300  # seconds
_CACHE = {"data": None, "ts": 0}
CACHE_FILE = Path("/tmp/wiki_products.json")
CACHE_TTL = 60 * 60  # 1 hour
_build_lock = threading.Lock()
_build_inflight = False

# retries for wiki
_session = requests.Session()
_adapter = requests.adapters.HTTPAdapter(max_retries=3)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)


def _wiki_get(params: dict, timeout=8):
    params = {**params, "format": "json", "redirects": 1}
    r = _session.get(WIKI_API, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _walk_category(root_title: str, max_depth: int = 2):
    """BFS category walk; collect ns=0 pages; follow subcats to max_depth."""
    pages = {}
    seen_cats = set()
    q = [(root_title, 0)]

    while q:
        cat, depth = q.pop(0)
        if cat in seen_cats:
            continue
        seen_cats.add(cat)

        cmcontinue = None
        while True:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": cat,
                "cmlimit": "max",
                "cmtype": "page|subcat",
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue
            data = _wiki_get(params)

            for m in data.get("query", {}).get("categorymembers", []):
                ns = m.get("ns")
                title = m.get("title", "")
                if ns == 0:
                    if title not in HARD_SKIP:
                        pages[m["pageid"]] = title
                elif ns == 14 and depth < max_depth:
                    q.append((title, depth + 1))

            cmcontinue = data.get("continue", {}).get("cmcontinue")
            if not cmcontinue:
                break

    return pages  # {pageid: title}

def _get_category_members(category: str):
    out, cmcontinue = [], None
    while True:
        params = {
            "action": "query", "list": "categorymembers",
            "cmtitle": category, "cmlimit": "max",
            "cmtype": "page", "cmnamespace": "0",
        }
        if cmcontinue: params["cmcontinue"] = cmcontinue
        data = _wiki_get(params)
        out.extend(data.get("query", {}).get("categorymembers", []))
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue: break
    return out  # [{pageid, title}]

_SKIP_TITLE_RE = re.compile(r"\b(list|goods list|products?)\b", re.I)

def _pageimages_for(ids, size=96):
    if not ids:
        return {}
    params = {
        "action": "query", "prop": "pageimages",
        "pithumbsize": str(size),
        "pageids": "|".join(str(i) for i in ids),
    }
    data = _wiki_get(params)
    pages = data.get("query", {}).get("pages", {})
    return {int(pid): pg.get("thumbnail", {}).get("source") for pid, pg in pages.items()}

def _chunk(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def _build_items(depth=2, thumb_size=96):
    # 1) collect pages
    pages = {}
    for root in ROOT_CATEGORIES:
        try:
            pages.update(_walk_category(root, max_depth=depth))
        except Exception as e:
            app.logger.warning("[wiki] walk failed for %s: %s", root, e)

    pids = list(pages.keys())
    # 2) thumbnails in parallel (wiki-friendly fanout)
    thumbs = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_pageimages_for, chunk, thumb_size) for chunk in _chunk(pids, 50)]
        for fut in as_completed(futures):
            try:
                thumbs.update(fut.result())
            except Exception as e:
                app.logger.warning("[wiki] pageimages batch failed: %s", e)

    # 3) assemble
    items = []
    for pid in sorted(pids, key=lambda x: pages[x].lower()):
        title = pages[pid]
        name = title.replace("_", " ")
        raw = thumbs.get(pid)
        img = f"/img-proxy?url={requests.utils.requote_uri(raw)}" if raw else None
        items.append({
            "id": name.lower().replace(" ", "_"),
            "name": name,
            "title": title,
            "img": img,
        })
    return items

def _templates_for(pageids):
    """Return {pid: [Template:Name, ...]}"""
    params = {
        "action": "query", "prop": "templates",
        "tllimit": "max",
        "pageids": "|".join(str(i) for i in pageids),
    }
    data = _wiki_get(params)
    pages = data.get("query", {}).get("pages", {})
    out = {}
    for pid, page in pages.items():
        tmpl_titles = [t.get("title","") for t in page.get("templates", [])]
        out[int(pid)] = tmpl_titles
    return out

def _save_cache(items):
    m= get_db()
    m["Website"]["cache"].update_one(
        {"_id": WIKI_CACHE_ID},
        {"$set": {"items": items, "updated_at": int(time.time())}},
        upsert=True,
    )

def _cache_fresh(doc):
    if not doc or "updated_at" not in doc: return False
    return (time.time() - doc["updated_at"]) < WIKI_TTL



def _load_cache():
    m = get_db()
    doc = m["Website"]["cache"].find_one({"_id": WIKI_CACHE_ID})
    return doc
    
def _req(params):
    params = dict(params)
    params["format"] = "json"
    headers = {"User-Agent": WIKI_USER_AGENT}
    r = requests.get(WIKI_API, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()
    
def _list_category_members(category, limit=500):
    """Yield page dicts: {pageid, title} from a Fandom category."""
    cmcontinue = None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": limit,
            "cmtype": "page",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        data = _req(params)
        for it in data.get("query", {}).get("categorymembers", []):
            yield {"pageid": it["pageid"], "title": it["title"]}
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break

def _get_page_thumb_and_wikitext(pageids):
    """Batch-fetch thumbnails + wikitext."""
    # 1) thumbs
    thumbs = {}
    for i in range(0, len(pageids), 50):
        batch = pageids[i:i+50]
        q = _req({
            "action": "query", "pageids": "|".join(map(str, batch)),
            "prop": "pageimages", "piprop": "thumbnail|name", "pithumbsize": 256
        })
        for pid, page in q.get("query", {}).get("pages", {}).items():
            thumbs[int(pid)] = page.get("thumbnail", {}).get("source")

    # 2) wikitext
    wikis = {}
    for i in range(0, len(pageids), 20):
        batch = pageids[i:i+20]
        # action=parse can take pageid one by one; use revisions for batch content
        q = _req({
            "action": "query", "pageids": "|".join(map(str, batch)),
            "prop": "revisions", "rvprop": "content", "rvslots": "main"
        })
        for pid, page in q.get("query", {}).get("pages", {}).items():
            revs = page.get("revisions") or []
            if revs:
                # MW 1.33+ stores content in slots
                slot = revs[0].get("slots", {}).get("main", {})
                wikis[int(pid)] = slot.get("*") or slot.get("content") or ""
    return thumbs, wikis

_price_line = re.compile(
    r"(?i)^\s*\|\s*(?:sell\s*price|max\s*price|price)\s*=\s*([0-9][0-9,\.]*)", re.M)
_price_anywhere = re.compile(
    r"(?i)(?:sell|max).{0,8}price[^0-9]{0,8}([0-9][0-9,\.]+)")

def _parse_max_price(wikitext):
    if not wikitext: return None
    m = _price_line.search(wikitext)
    if not m:
        m = _price_anywhere.search(wikitext)
    if not m: return None
    s = m.group(1)
    s = s.replace(",", "")
    try:
        return int(float(s))
    except:
        return None

def _title_to_key(title):
    # "Carrot Cake" -> "Carrot_Cake"
    return "_".join(p.capitalize() for p in title.replace("_", " ").split())

def _build_wiki_products(depth=2):
    """
    depth=1 => Products only
    depth=2 => Products + important subcats (e.g., Materials, Crops) - tweak as needed
    """
    categories = ["Products"]
    if depth >= 2:
        categories += ["Crops", "Animal Products", "Materials"]  # add more if you want

    # 1) list pages
    pages = {}
    for cat in categories:
        for p in _list_category_members(cat):
            pages[p["pageid"]] = p["title"]

    # 2) bulk fetch thumbs + wikitext
    pageids = list(pages.keys())
    thumbs, wikis = _get_page_thumb_and_wikitext(pageids)

    # 3) normalize
    items = []
    for pid in pageids:
        title = pages[pid]
        key = _title_to_key(title)          # builder key
        price = _parse_max_price(wikis.get(pid, ""))
        thumb = thumbs.get(pid)

        # If you have an /img-proxy, prefer that to avoid mixed content/CORS:
        if thumb:
            thumb = url_for("img_proxy", _external=False) + f"?url={requests.utils.requote_uri(thumb)}" \
                    if "img_proxy" in {r.rule for r in app.url_map.iter_rules()} else thumb

        items.append({
            "name": title,           # "Carrot Cake"
            "key": key,              # "Carrot_Cake"
            "max_price": price,      # may be None if not found
            "thumb": thumb
        })
    # optional: filter obvious junk
    items = [it for it in items if not re.search(r"(?i)Category:|Template:", it["name"])]
    return items

def _kick_build_async(depth):
    def _do():
        try:
            items = _build_wiki_products(depth=depth)
            _save_cache(items)
        except Exception as e:
            app.logger.exception("wiki build failed: %s", e)
    threading.Thread(target=_do, daemon=True).start()

def _cache(resp: Response, seconds: int = 60*60*24*7):  # default 7 days
    resp.headers["Cache-Control"] = f"public, max-age={seconds}, immutable"
    return resp

IMG_CACHE_DIR = Path("/tmp/img_proxy_cache")
IMG_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _cache_key_for_url(url: str) -> Path:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    # Try to keep an extension for correct content-type
    ext = os.path.splitext(url.split("?")[0])[1].lower() or ".bin"
    # sanitize weird query-extensions
    if len(ext) > 6 or any(ch in ext for ch in ':/\\'):
        ext = ".bin"
    return IMG_CACHE_DIR / f"{h}{ext}"



def calculate_achievements(xp, message_count, coins, streak, auctions_won=0, top_bidder_count=0, mentions=0):
    achievements = []

    # Message Milestones
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

    # Coin Achievements
    if coins >= 100:
        achievements.append({"label": "🪙 First 100 Coins", "tooltip": "Earn 100 coins"})
    if coins >= 1_000:
        achievements.append({"label": "🪙 Coin Collector", "tooltip": "Earn 1,000 coins"})
    if coins >= 10_000:
        achievements.append({"label": "💰 Rolling in Coins (10k+)", "tooltip": "Earn 10,000 coins"})
    if coins >= 50_000:
        achievements.append({"label": "💵 Treasure Stacker (50k+)", "tooltip": "Earn 50,000 coins"})
    if coins >= 100_000:
        achievements.append({"label": "👑 Rich Farmer (100k+)", "tooltip": "Earn 100,000 coins"})
    if coins >= 250_000:
        achievements.append({"label": "🏦 Vault Builder (250k+)", "tooltip": "Earn 250,000 coins"})
    if coins >= 500_000:
        achievements.append({"label": "💸 Coin Tycoon (500k+)", "tooltip": "Earn 500,000 coins"})
    if coins >= 1_000_000:
        achievements.append({"label": "🏆 Millionaire Status", "tooltip": "Earn 1,000,000 coins"})

    # Streaks
    if streak >= 2:
        achievements.append({"label": "🔥 Daily Habit (2+ days)", "tooltip": "Log in 2 days in a row"})
    if streak >= 5:
        achievements.append({"label": "🔥🔥 Consistent Farmer (5+ days)", "tooltip": "Log in 5 days in a row"})
    if streak >= 7:
        achievements.append({"label": "📅 Weekly Warrior (7+ days)", "tooltip": "Maintain a 7-day login streak"})
    if streak >= 14:
        achievements.append({"label": "🌵 Biweekly Beast (14+ days)", "tooltip": "Maintain a 14-day login streak"})
    if streak >= 30:
        achievements.append({"label": "🏅 1 Month Grind!", "tooltip": "Maintain a 30-day login streak"})
    if streak >= 60:
        achievements.append({"label": "🎖️ 2 Months Streak", "tooltip": "Maintain a 60-day login streak"})
    if streak >= 90:
        achievements.append({"label": "🏆 Daily Legend (90+ days)", "tooltip": "Maintain a 90-day login streak"})

    # Auctions
    if auctions_won >= 1:
        achievements.append({"label": "🏷️ Auction Winner", "tooltip": "Win at least 1 auction"})
    if top_bidder_count >= 5:
        achievements.append({"label": "🏅 Top Bidder", "tooltip": "Be top bidder in 5+ auctions"})

    # Trades (Mentions)
    if mentions >= 15:
        achievements.append({"label": "🤝 15+ safe trades!", "tooltip": "Complete 15 valid trades"})
    if mentions >= 30:
        achievements.append({"label": "🤝 30+ safe trades!", "tooltip": "Complete 30 valid trades"})
    if mentions >= 50:
        achievements.append({"label": "🤝 50+ Professional Trader", "tooltip": "Complete 50 valid trades"})
    if mentions >= 100:
        achievements.append({"label": "📈 Master Of Trades 100+", "tooltip": "Complete 100 valid trades"})
    if mentions >= 200:
        achievements.append({"label": "📈 Trade-a-saurus rex 200+", "tooltip": "Complete 200 valid trades"})
    if mentions >= 300:
        achievements.append({"label": "🪙 Bullish Banana 300+", "tooltip": "Complete 300 valid trades"})
    if mentions >= 400:
        achievements.append({"label": "🪙 Stocky McTradeface 400+", "tooltip": "Complete 400 valid trades"})
    if mentions >= 500:
        achievements.append({"label": "💹 Profit Piranha 500+", "tooltip": "Complete 500 valid trades"})
    if mentions >= 600:
        achievements.append({"label": "💹 Deal-a-whale 600+", "tooltip": "Complete 600 valid trades"})
    if mentions >= 700:
        achievements.append({"label": "💹 Chart Chimp 700+", "tooltip": "Complete 700 valid trades"})
    if mentions >= 800:
        achievements.append({"label": "📊 Market Munchkin 800+", "tooltip": "Complete 800 valid trades"})
    if mentions >= 900:
        achievements.append({"label": "📊 Penny Pincher 900+", "tooltip": "Complete 900 valid trades"})
    if mentions >= 1000:
        achievements.append({"label": "🛠️ 1k Trades??? ur crazy", "tooltip": "Complete 1,000 valid trades"})

    return achievements

def log_abuse_attempt(action, details=None):
    """Log a blocked login or callback attempt to the Interaction Logs collection."""
    db = get_db("Website")
    col = db["InteractionLogs"]

    try:
        col.insert_one({
            "action": action,
            "details": details or {},
            "username": session.get("username"),
            "discord_id": session.get("discord_id"),
            "timestamp": datetime.utcnow(),
            "user_agent": request.headers.get("User-Agent", "Unknown"),
            "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        })
    except Exception as e:
        print("[log_abuse_attempt] failed:", e)

def get_settings_collection(client=None):
    if client:
        return client["Website"]["settings"]
    return get_db("Website")["settings"]

_MAINT_BANNER_CACHE = {"data": None, "expires": 0}
def read_maintenance_banner():
    now = time.time()
    if _MAINT_BANNER_CACHE["data"] is not None and now < _MAINT_BANNER_CACHE["expires"]:
        return _MAINT_BANNER_CACHE["data"]

    col = get_db("Website")["settings"]
    doc = col.find_one({"_id": "maintenance_banner"})

    if not doc:
        data = {"enabled": False, "message": "", "require_ack": False}
    else:
        data = {
            "enabled": bool(doc.get("enabled", False)),
            "message": doc.get("message", ""),
            "require_ack": bool(doc.get("require_ack", True)),
        }

    ack_source = json.dumps({
        "message": data["message"],
        "require_ack": data["require_ack"],
    }, sort_keys=True, ensure_ascii=True)
    data["ack_key"] = hashlib.sha1(ack_source.encode("utf-8")).hexdigest()[:12]

    _MAINT_BANNER_CACHE["data"] = data
    _MAINT_BANNER_CACHE["expires"] = now + 30
    return data

@app.context_processor
def inject_maintenance_banner():
    # Inject into all templates
    try:
        banner = read_maintenance_banner()
    except Exception:
        banner = {"enabled": False, "message": "", "require_ack": False, "ack_key": "default"}
    return {
        "maintenance_banner": banner,
        "easter_live": EASTER_LIVE,
    }


def _safe_next_path(value, default="/"):
    value = (value or "").strip()
    if not value.startswith("/"):
        return default
    return value


def _current_request_path(default="/"):
    query = request.query_string.decode("utf-8", errors="ignore")
    current = request.path or default
    if query:
        current = f"{current}?{query}"
    return _safe_next_path(current, default=default)


@app.context_processor
def inject_login_next_path():
    return {"login_next_path": _current_request_path()}

@app.errorhandler(404)
def page_not_found(e):
    return render_template("errors/404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("errors/500.html"), 500

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if request.path.startswith(('/api/', '/admin/')):
        return {"error": "CSRF validation failed"}, 400
    return render_template("errors/csrf.html", reason=e.description), 400


@app.route("/admin/ip-watch")
def ip_watch():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    rows = [
        f"{escape(ip)}: {len(times)} hits"
        for ip, times in sorted(ip_hits.items(), key=lambda x: -len(x[1]))
    ]

    banned = []
    client = get_db()
    for doc in client["Security"]["banned_ips"].find():
        banned.append(f"{escape(doc['_id'])} (internal: {escape(doc.get('internal_ip', 'N/A'))}, reason: {escape(doc.get('reason', 'n/a'))}, hits: {doc.get('hit_count', '?')})")

    return f"""
        <h1>🛠️ IP Scanner Watch</h1>
        <h2>Suspicious Activity</h2>
        {"<br>".join(rows) if rows else "<i>None</i>"}
        <h2>🔥 Banned IPs</h2>
        {"<br>".join(banned) if banned else "<i>None</i>"}
    """


@app.errorhandler(429)
def ratelimit_handler(e):
    user_ip = request.remote_addr
    now = datetime.utcnow().isoformat()

    log_message = f"[RateLimit] {now} - Too many requests from {user_ip} on {request.path}"

    print(log_message)  # log to Fly logs

    # OPTIONAL: Save to MongoDB
    client = get_db()
    client["Website"]["Logs"].insert_one({
        "type": "ratelimit",
        "ip": user_ip,
        "path": request.path,
        "timestamp": now
    })

    return jsonify({
        "error": "Too many requests, slow down.",
        "retry_after": e.description
    }), 429


@app.template_filter('format')
def format_number(n):
    return f"{n:,}" if isinstance(n, int) else n



@app.post("/api/update-setting")
@csrf.exempt
def api_update_setting():
    if not is_staff():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    key = data.get("key")
    value = data.get("value")

    if not key:
        return jsonify({"error": "Missing key"}), 400

    client = get_db()
    col = client["Website"]["settings"]

    # If complex object (dict) is passed for maintenance banner, store as-is
    if key == "maintenance_banner":
        if not isinstance(value, dict):
            return jsonify({"error": "maintenance_banner value must be an object"}), 400
        value = {
            "enabled": bool(value.get("enabled", False)),
            "message": str(value.get("message", "")),
            "require_ack": bool(value.get("require_ack", True)),
        }
        value["_id"] = "maintenance_banner"
        col.update_one({"_id": "maintenance_banner"}, {"$set": value}, upsert=True)
        _MAINT_BANNER_CACHE["data"] = None
        _MAINT_BANNER_CACHE["expires"] = 0
        return jsonify({"message": "Maintenance banner updated"}), 200

    # Fallback for your other scalar settings (e.g., prefix)
    col.update_one({"_id": key}, {"$set": {"_id": key, "value": value}}, upsert=True)
    return jsonify({"message": f"{key} updated"}), 200


@app.route("/send-reply", methods=["POST"])
def send_reply():
    if not is_staff():
        return "Unauthorized", 403

    channel_id = request.form["channel_id"]
    message = request.form["message"]

    # Use requests.post to tell your bot server to send message
    requests.post(
        "http://localhost:5000/api/send-message",
        json={
            "channel_id": channel_id,
            "message": message
        },
        timeout=5
    )
    return redirect("/active-tickets")

@app.route("/api/wiki-products-local")
def api_wiki_products_local():
    items = []
    if THUMB_ROOT.exists():
        for p in THUMB_ROOT.glob("*.png"):
            slug = p.stem
            name = slug.replace("_", " ")
            items.append({
                "id": slug.lower(),
                "name": name,
                "title": name,
                "img": f"/thumb/{slug}.png"
            })
    items.sort(key=lambda x: x["name"].lower())
    return jsonify(items)


@app.get("/img-proxy")
def img_proxy():
    url = request.args.get("url")
    if not url:
        abort(400, "url required")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.netloc not in ALLOWED_IMAGE_HOSTS:
        abort(403, "host not allowed")

    path = _cache_key_for_url(url)
    if not path.exists():
        try:
            r = requests.get(url, timeout=10, stream=True)
            r.raise_for_status()
            # Write atomically
            tmp = path.with_suffix(path.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(64 * 1024):
                    if chunk:
                        f.write(chunk)
            tmp.replace(path)
        except Exception as e:
            abort(502, f"proxy fetch failed: {e}")

    # Serve the cached file with a good content-type and cache headers
    mime, _ = mimetypes.guess_type(str(path))
    resp = make_response(send_file(path, mimetype=mime or "application/octet-stream"))
    return _cache(resp, 60*60*24*14)  # 14 days

@app.route("/api/wiki-products")
def api_wiki_products():
    """Return cached list; refresh in the background when stale or on force=1."""
    depth = int(request.args.get("depth") or 2)
    force = request.args.get("force") == "1"

    cache = None if force else _load_cache()
    if _cache_fresh(cache):
        return jsonify(cache["items"])

    # stale or missing: kick background build and return ASAP
    _kick_build_async(depth)

    # Serve stale cache if available; else 202 to tell client to retry
    if cache and "items" in cache and cache["items"]:
        return jsonify(cache["items"])  # stale-while-revalidate
    return jsonify({"status": "building"}), 202


@app.route("/api/admin-lookup/<identifier>")
def admin_lookup(identifier):
    # Check if user is staff
    if not is_staff():
        return jsonify({"error": "Unauthorized"}), 403

    client = get_db()
    try:
        raw = (identifier or "").strip()
        user_id = None
        tag_used = None

        # Helper to normalize tags like "pc2rlpypy" -> "#PC2RLPYPY"
        def normalize_tag(s: str) -> str:
            core = re.sub(r"[^A-Za-z0-9]", "", (s or "")).upper()
            return f"#{core}" if core else ""

        # 1) Resolve identifier -> user_id
        if raw.isdigit() and 15 <= len(raw) <= 20:
            user_id = raw
        else:
            tag_used = normalize_tag(raw)
            if tag_used:
                # Find the first verify log that contains this tag and extract the Discord ID
                doc = client["log"]["verify"].find_one({
                    "Message content": {"$regex": re.escape(tag_used), "$options": "i"}
                })
                if doc and doc.get("id"):
                    user_id = str(doc["id"])

        if not user_id:
            return jsonify({"error": "No matching user found"}), 404

        # 2) Load collections you already rely on
        mentions = client["Mentions"]["Amount"].find_one({"id": int(user_id)})
        birthday = client["Birthdays"]["Users"].find_one({"user_id": user_id})
        scam_records = list(client["Scam"]["Banned"].find({}, {"id": 1}).limit(5000))
        scam_ids = {val.strip().upper() for rec in scam_records for val in rec.get("id", [])}

        mute_info = list(client["Moderation"]["mute"].find({"user_id": int(user_id)}))
        mute_count = mute_info[0].get("mute_count", 0) if mute_info else 0

        # LIVE ban check via bot internal API with auth header
        banned = None
        ban_reason = None
        try:
            bot_api_url = os.getenv("BOT_WEBHOOK_URL") + f"/internal/is_banned/{user_id}"
            headers = {"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
            resp = requests.get(bot_api_url, headers=headers, timeout=3)
            if resp.ok:
                data = resp.json()
                banned = data.get("banned", False)
                ban_reason = data.get("reason") if banned else None
        except Exception as e:
            print(f"鈿狅笍 Ban check failed: {e}")

        usernames = client["Website"]["usernames"].find_one({"_id": user_id})

        # Find active mute if exists
        active_mute = next(
            (m for m in mute_info if m.get("muted") and m.get("mute_end") and m["mute_end"] > datetime.utcnow()),
            None
        )

        # Fetch logs and name changes
        logs = list(client["Website"]["Logs"].find(
            {"$or": [{"author.id": user_id}, {"user_id": user_id}]}
        ).sort("timestamp", -1).limit(200))
        name_changes = list(
            client["log"]["namechange"].find({"user_id": user_id}).sort("timestamp", -1).limit(50)
        )

        message_edits = [log for log in logs if log.get("type") == "message_edit"]
        message_deletes = [log for log in logs if log.get("type") == "message_delete"]
        commands = [log for log in logs if log.get("type") == "command"]

        # Verifications: by Discord ID and (if provided) by tag text
        verify_or = [{"id": int(user_id)}]
        if tag_used:
            verify_or.append({"Message content": {"$regex": re.escape(tag_used), "$options": "i"}})

        linked_data = list(client["log"]["verify"].find({"$or": verify_or}))
        for entry in linked_data:
            message = entry.get("Message content", "")
            match = re.search(r"HayDay ID:\s*([#A-Z0-9]+)", message, re.I)
            hayday_id = match.group(1).strip().upper() if match else None
            entry["hayday_id"] = hayday_id
            entry["is_scammer"] = (hayday_id in scam_ids) if hayday_id else False

        # Prepare response JSON
        response = {
            "user_summary": {
                "user_id": user_id,
                "mention_count": mentions.get("Mentions") if mentions else 0,
                "birthday": f"{birthday.get('day')}/{birthday.get('month')} {birthday.get('timezone', '')}" if birthday else None,
                "banned": banned,
                "ban_reason": ban_reason,
                "muted": bool(active_mute),
                "mute_reason": active_mute.get("reason") if active_mute else None,
                "mute_end": active_mute.get("mute_end") if active_mute else None,
                "mute_end_str": active_mute["mute_end"].strftime("%Y-%m-%d %H:%M:%S UTC") if active_mute else None,
                "mute_count": mute_count,
                "display_name": usernames.get("display_name") if usernames else None,
                "username": usernames.get("username") if usernames else None,
                "avatar_url": usernames.get("avatar") if usernames else None
            },
            "linked_data": linked_data,
            "scam_records": scam_records,
            "mute_ban_info": mute_info,
            "commands": commands,
            "messages_deleted": message_deletes,
            "messages_edited": message_edits,
            "name_history": name_changes
        }

        return jsonify(serialize_mongo(response))

    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/moderation/mute", methods=["POST"])
def api_mute_user():
    if "discord_id" not in session or not is_staff():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.json
        user_id = str(data.get("user_id"))
        action = data.get("action", "mute")  # mute or unmute
        reason = data.get("reason", "No reason provided")
        staff_id = session["discord_id"]
        guild_id = "959220051427340379"

        if not user_id:
            return jsonify({"error": "Missing user ID"}), 400

        client = get_db()
        collection = client["Moderation"]["mute"]

        if action == "unmute":
            # Update DB
            collection.update_one(
                {"user_id": user_id, "guild_id": guild_id},
                {"$set": {"muted": False}}
            )
            # Trigger bot webhook
            try:
                requests.post(
                    os.getenv("BOT_WEBHOOK_URL") + "/webhook/moderation/unmute",
                    json={
                        "user_id": user_id,
                        "reason": reason,
                        "staff_id": staff_id
                    },
                    headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
                    timeout=5
                )
            except Exception as e:
                print(f"鈿狅笍 Failed to trigger unmute webhook: {e}")

            return jsonify({"success": True})

        # Proceed with mute
        duration_raw = data.get("duration")
        if not duration_raw:
            return jsonify({"error": "Missing duration"}), 400

        duration_seconds = parse_duration(duration_raw)
        if duration_seconds is None:
            return jsonify({"error": "Invalid duration format"}), 400

        mute_end = datetime.utcnow() + timedelta(seconds=duration_seconds)

        # Save to MongoDB
        collection.update_one(
            {"user_id": user_id, "guild_id": guild_id},
            {
                "$set": {
                    "user_id": user_id,
                    "guild_id": guild_id,
                    "mute_end": mute_end,
                    "reason": reason,
                    "muted": True
                },
                "$inc": {"mute_count": 1}
            },
            upsert=True
        )

        # Trigger mute webhook
        try:
            requests.post(
                os.getenv("BOT_WEBHOOK_URL") + "/webhook/moderation/mute",
                json={
                    "user_id": user_id,
                    "duration": duration_raw,
                    "reason": reason,
                    "staff_id": staff_id
                },
                headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
                timeout=5
            )
        except Exception as e:
            print(f"鈿狅笍 Failed to trigger bot mute webhook: {e}")

        return jsonify({"success": True})

    except Exception as e:
        print("[/api/moderation/mute] Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/moderation/kick", methods=["POST"])
def api_kick_user():
    if "discord_id" not in session or not is_staff():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.json
        user_id = int(data.get("user_id"))
        reason = data.get("reason", "No reason provided")
        staff_id = session["discord_id"]

        # Trigger bot webhook
        requests.post(
            os.getenv("BOT_WEBHOOK_URL") + "/webhook/moderation/kick",
            json={
                "user_id": user_id,
                "reason": reason,
                "staff_id": staff_id
            },
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
            timeout=5
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/moderation/scam", methods=["POST"])
def api_scam_action():
    if "discord_id" not in session or not is_staff():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.json
        action = data.get("action")  # "add" or "remove"
        scam_id = data.get("scam_id")
        scam_id = scam_id.strip().upper()
        staff_id = session["discord_id"]

        if action not in ("add", "remove") or not scam_id:
            return jsonify({"error": "Invalid input"}), 400

        # Trigger bot webhook
        requests.post(
            os.getenv("BOT_WEBHOOK_URL") + "/webhook/moderation/scam",
            json={
                "action": action,
                "scam_id": scam_id,
                "staff_id": staff_id
            },
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
            timeout=5
        )

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@limiter.limit("5/minute")
@app.route("/api/moderation/ban", methods=["POST"])
def api_ban_user():
    if "discord_id" not in session or not is_staff():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.json
        user_id = str(data.get("user_id"))
        reason = data.get("reason", "No reason provided")
        action = data.get("action")  # "ban" or "unban"
        staff_id = session["discord_id"]

        if not user_id or action not in ("ban", "unban"):
            return jsonify({"error": "Invalid input"}), 400

        client = get_db()
        ban_col = client["Moderation"]["ban_list"]

        if action == "ban":
            ban_col.update_one(
                {"_id": user_id},
                {"$set": {
                    "banned": True,
                    "reason": reason,
                    "banned_by": staff_id,
                    "timestamp": datetime.utcnow()
                }},
                upsert=True
            )
        else:
            ban_col.delete_one({"_id": user_id})

        # Trigger bot webhook
        try:
            requests.post(
                os.getenv("BOT_WEBHOOK_URL") + "/webhook/moderation/ban",
                json={
                    "user_id": user_id,
                    "reason": reason,
                    "staff_id": staff_id,
                    "action": action
                },
                headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
                timeout=5
            )
        except Exception as e:
            print(f"鈿狅笍 Failed to trigger bot ban webhook: {e}")

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/remove-featured-achievement", methods=["POST"])
def remove_featured_achievement():
    if "discord_id" not in session:
        return redirect("/login")

    client = get_db()
    users = client["Website"]["users"]
    users.update_one(
        {"_id": session["discord_id"]},
        {"$unset": {"featured_achievement": ""}}
    )

    return redirect("/profile")


@app.route("/booster-dashboard", methods=["GET", "POST"])
def booster_dashboard():
    if not is_staff():
        return "鉂?Access denied. You are not staff.", 403

    discord_id = int(session["discord_id"])
    message = None

    client = get_db()
    booster_col = client["hayday"]["Booster"]
    user_col = client["Website"]["usernames"]
    roles_cache = client["Website"]["roles_cache"].find_one({"_id": "live"}) or {}

    # Handle form submission
    if request.method == "POST":
        target_id = int(request.form.get("target_id"))
        role_name = request.form.get("role_name")
        role_color = request.form.get("role_color")

        if not role_name or not role_color:
            message = "鉂?Both fields are required."
        else:
            try:
                r = requests.post(
                    os.getenv("BOT_WEBHOOK_URL") + "/webhook/booster-update",
                    json={
                        "discord_id": target_id,
                        "role_name": role_name,
                        "role_color": role_color
                    },
                    headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
                    timeout=5
                )
                message = "✅ Role updated!" if r.status_code == 200 else "❌ Failed to update role"
            except Exception as e:
                message = f"鉂?Error: {e}"

        # Load all boosters
        boosters = []
        all_boosters = list(booster_col.find({}))
        all_user_ids = [str(b["_id"]) for b in all_boosters]
        users = list(user_col.find({"_id": {"$in": all_user_ids}}))
        user_map = {u["_id"]: u for u in users}

        for b in all_boosters:
            user = user_map.get(str(b["_id"]))

            boosters.append({
                "user_id": str(b["_id"]),
                "display_name": user.get("display_name", "Unknown") if user else "Unknown",
                "username": user.get("username", "") if user else "",
                "avatar_url": user.get("avatar", "https://cdn.discordapp.com/embed/avatars/0.png") if user else "https://cdn.discordapp.com/embed/avatars/0.png",
                "role_name": b.get("role_name", "鉂?Unknown"),
                "color": f"#{int(b.get('role_color', 0)):06x}"
            })

    return render_template("booster_dashboard.html", boosters=boosters, message=message)

@app.route("/force-logout", methods=["POST"])
def force_logout_all():
    if session.get("discord_id") != "154282062973501441":
        return "鉂?Unauthorized", 403

    client = get_db()
    # Clear all session data in the Website.users collection
    result = client["Website"]["users"].update_many({}, {
        "$unset": {
            "session": "",
            "last_login": "",
            "staff_role": "",
        }
    })

    # Optionally log out current user too
    session.clear()
    return redirect("/login")



@csrf.exempt
@app.route("/update-bio", methods=["POST"])
def update_bio():
    if "discord_id" not in session:
        return redirect(url_for("login", next=url_for("profile")))

    new_bio = request.form.get("bio", "").strip()
    if len(new_bio) > 300:
        flash("鉂?Bio must be under 300 characters.", "error")
        return redirect(url_for("profile"))

    safe_bio = escape(new_bio)  # prevent injection

    client = get_db()
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

    client = get_db()
    users = client["Website"]["users"]
    users.update_one(
        {"_id": session["discord_id"]},
        {"$set": {"featured_achievement": new_badge}}
    )

    return jsonify({"success": True})
    

@app.route("/api/button-toggles", methods=["GET", "POST"])
def button_toggles():
    if not is_staff():
        return "Unauthorized", 403

    if "discord_id" not in session:
        return redirect("/login-page")

    client = get_db()
    toggle_col = client["Website"]["ButtonToggles"]

    if request.method == "GET":
        toggles = {
            doc["_id"]: {
                "enabled": doc["enabled"],
                "reason": doc.get("reason", "")
            } for doc in toggle_col.find()
        }
        return jsonify(toggles)

    if request.method == "POST":
        data = request.json
        key = data.get("key")
        enabled = data.get("enabled", True)
        reason = data.get("reason", "").strip()

        if not enabled and not reason:
            reason = "🔒 This function is disabled by the staff."

        if key not in ["staff_application", "support", "giveaway", "verification", "auction"]:
            return jsonify({"error": "Invalid key"}), 400

        toggle_col.update_one(
            {"_id": key},
            {"$set": {"enabled": enabled, "reason": reason}},
            upsert=True
        )
        return jsonify({"message": f"{key} status updated."})



@app.route("/giveaways")
def giveaways_page():
    client = get_db()
    db = client["Giveaway"]
    user_db = client["Website"]["usernames"]
    raw_giveaways = list(db["current_giveaways"].find({"ended": False}))

    # --- ensure session roles are present & normalized ---
    discord_id = session.get("discord_id")
    session_roles = session.get("roles") or []
    if not session_roles and discord_id:
        # fallback: load roles from Website.usernames
        udoc = user_db.find_one({"_id": str(discord_id)}, {"roles": 1})
        if udoc:
            session_roles = [str(r) for r in udoc.get("roles", [])]
            session["roles"] = session_roles  # cache back into session
    else:
        # normalize whatever's in session to strings
        session_roles = [str(r) for r in session_roles]

    # collect user + host ids (unchanged) ...
    user_ids = set()
    for g in raw_giveaways:
        user_ids.update(map(str, g.get("participants", {}).keys()))
        if "host_id" in g:
            user_ids.add(str(g["host_id"]))
    users = user_db.find({"_id": {"$in": list(user_ids)}})
    user_map = {str(u["_id"]): u for u in users}

    giveaways = []
    now_ts = time.time()
    now = datetime.now(COPENHAGEN_TZ)

    guild_id = "959220051427340379"
    try:
        role_mapping = fetch_role_mapping(guild_id)
    except Exception as e:
        print(f"[Giveaways Page] Failed to fetch roles: {e}")
        role_mapping = {}

    # Make sure these IDs are strings
    BYPASS_ROLE_ID = "975188431636418681"
    # Make sure this is your real member role ID:
    MEMBER_ROLE_ID = "959220051469279296"

    for g in raw_giveaways:
        end = g.get("end_time")
        if not end:
            continue
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        end_local = end.astimezone(COPENHAGEN_TZ)

        if end_local.timestamp() < now_ts:
            continue

        diff = int(end.timestamp() - now_ts)
        hours = diff // 3600
        minutes = (diff % 3600) // 60
        g["time_remaining"] = f"{hours}h {minutes}m"
        g["end_time"] = end_local
        g["end_time_str"] = f"<t:{int(end.timestamp())}:R>"
        g["end_time_ts"] = int(end.timestamp())

        g["entry_count"] = sum(g.get("participants", {}).values())
        g["winners"] = g.get("winners_count", 1)
        g["guild_id"] = str(g.get("guild_id", GUILD_ID))
        g["channel_id"] = str(g.get("channel_id", ""))

        # --- Required roles (OR + legacy fallback) ---
        raw_ids = list(g.get("required_role_ids") or [])
        legacy = g.get("required_role_id")
        if legacy not in (None, "", 0):
            raw_ids.append(legacy)

        # normalize to strings for display & session compare
        required_ids = [str(x) for x in raw_ids if x not in (None, "", 0)]
        g["required_role_ids"] = required_ids  # expose to Jinja

        # names for display (if you fetched role_mapping earlier)
        required_names = [role_mapping.get(rid, {}).get("name") for rid in required_ids]
        required_names = [n for n in required_names if n]
        g["required_role_names"] = required_names
        g["required_role_display"] = ", ".join(required_names) if required_names else None

        # Eligibility (OR): has at least one of the required roles
        user_roles = session_roles  # already normalized to strings earlier
        is_booster = BYPASS_ROLE_ID in user_roles
        has_required = (len(required_ids) == 0) or any(rid in user_roles for rid in required_ids)

        boosters_bypass = bool(g.get("boosters_bypass", True))
        can_booster_bypass = is_booster and boosters_bypass

        # checkbox only when they LACK all required roles but ARE a booster (bypass)
        g["has_bypass"] = (len(required_ids) > 0) and (not has_required) and can_booster_bypass
        g["can_join"] = has_required or can_booster_bypass

        g["not_in_guild"] = str(MEMBER_ROLE_ID) not in user_roles

        # host info
        host_id = str(g.get("host_id"))
        host = user_map.get(host_id)
        g["host_display"] = host.get("display_name", f"<@{host_id}>") if host else f"<@{host_id}>"
        g["host_avatar"] = None
        if host:
            if host.get("avatar"):
                g["host_avatar"] = host.get("avatar")
            elif host.get("avatar_hash"):
                g["host_avatar"] = f"https://cdn.discordapp.com/avatars/{host_id}/{host.get('avatar_hash')}.png"

        # participants info
        total_entries = g["entry_count"]
        g["participants_percent"] = []
        g["participant_info"] = []
        for uid, count in g.get("participants", {}).items():
            uid_str = str(uid)
            percent = round((count / total_entries) * 100, 2) if total_entries else 0
            user = user_map.get(uid_str)
            display_name = user.get("display_name", f"<@{uid_str}>") if user else f"<@{uid_str}>"
            avatar = user.get("avatar") if user and user.get("avatar") else "https://cdn.discordapp.com/embed/avatars/0.png"
            g["participants_percent"].append({"id": uid_str, "count": count, "percent": percent})
            g["participant_info"].append({"id": uid_str, "count": count, "percent": percent, "name": display_name, "avatar": avatar})

        giveaways.append(g)

    return render_template(
        "giveaways.html",
        giveaways=giveaways,
        discord_id=discord_id,
        user_roles=session_roles,
        year=now.year
    )


@app.route("/api/giveaways/won")
def won_giveaways():
    if "discord_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    page = int(request.args.get("page", 1))
    limit = 4
    skip = (page - 1) * limit
    discord_id = session["discord_id"]

    client = get_db()
    col = client["Giveaway"]["current_giveaways"]

    winner_match = [str(discord_id)]
    try:
        winner_match.append(int(discord_id))
    except (TypeError, ValueError):
        pass

    query = {
        "ended": True,
        "winners": {"$in": winner_match}
    }

    total = col.count_documents(query)
    recent = list(col.find(query)
                    .sort("end_time", -1)
                    .skip(skip)
                    .limit(limit))

    usernames_col = client["Website"]["usernames"]

    for g in recent:
        g["_id"] = str(g["_id"])
        g["you_won"] = True

        # Timestamp fix
        end_time = g.get("end_time")
        if isinstance(end_time, datetime):
            g["end_time_ts"] = int(end_time.timestamp())
        else:
            g["end_time_ts"] = 0

        # Host display/avatars
        host_id = g.get("host_id")
        if host_id:
            profile = usernames_col.find_one({"_id": str(host_id)})
            g["host_display"] = profile.get("display_name", "Unknown") if profile else "Unknown"
            g["host_avatar"] = profile.get("avatar_url", "") if profile else ""
            g["host_id"] = str(host_id)
        else:
            g["host_display"] = "Unknown"
            g["host_avatar"] = ""
            g["host_id"] = None

    return jsonify({
        "giveaways": recent,
        "page": page,
        "total": total,
        "limit": limit
    })

@app.route("/api/live-giveaways")
def api_live_giveaways():
    now_ts = time.time()

    if LIVE_GIVEAWAYS_CACHE["payload"] is not None and now_ts < LIVE_GIVEAWAYS_CACHE["expires"]:
        return jsonify(LIVE_GIVEAWAYS_CACHE["payload"])

    client = get_db()
    db = client["Giveaway"]
    user_db = client["Website"]["usernames"]

    raw_giveaways = list(
        db["current_giveaways"].find(
            {"ended": False},
            {"prize": 1, "end_time": 1, "host_id": 1}
        )
    )

    host_ids = {
        str(g["host_id"])
        for g in raw_giveaways
        if g.get("host_id") is not None
    }

    user_map = {}
    if host_ids:
        users = user_db.find(
            {"_id": {"$in": list(host_ids)}},
            {"username": 1, "display_name": 1, "avatar": 1, "avatar_hash": 1}
        )
        user_map = {str(u["_id"]): u for u in users}

    output = []

    for g in raw_giveaways:
        end = g.get("end_time")
        if not end:
            continue
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        end_ts = end.timestamp()
        if end_ts < now_ts:
            continue

        host_id = str(g.get("host_id") or "")
        host = user_map.get(host_id, {})

        output.append({
            "prize": g.get("prize"),
            "end_time_ts": int(end_ts),
            "host_display": host.get("display_name") or host.get("username") or f"User {host_id}",
            "host_avatar": host.get("avatar")
        })

    payload = output
    LIVE_GIVEAWAYS_CACHE["payload"] = payload
    LIVE_GIVEAWAYS_CACHE["expires"] = now_ts + 10

    return jsonify(payload)


@app.route("/api/production-data")
def api_production_data():
    now_ts = time.time()

    if PRODUCTION_DATA_CACHE["payload"] is not None and now_ts < PRODUCTION_DATA_CACHE["expires"]:
        return jsonify(PRODUCTION_DATA_CACHE["payload"])

    client = get_db()
    col = client["hayday"]["ProductionGuide"]
    data = list(col.find({}, {"_id": 0}))

    PRODUCTION_DATA_CACHE["payload"] = data
    PRODUCTION_DATA_CACHE["expires"] = now_ts + 300

    return jsonify(data)

@app.route("/api/fandom-thumbs")
def fandom_thumbs():
    qs = request.query_string.decode("utf-8")
    key = f"/api.php?{qs}"
    cached = _get_cached(_API_CACHE, key)
    if cached:
        body, headers = cached
        return Response(body, headers=headers)

    url = f"https://hayday.fandom.com/api.php?{qs}"
    r = requests.get(url, timeout=10)
    body = r.content
    headers = {"Content-Type": r.headers.get("Content-Type", "application/json"),
               "Cache-Control": "public, max-age=86400"}
    _set_cached(_API_CACHE, key, body, headers, _TTL_API)
    return Response(body, headers=headers)

@app.route("/api/thumbs")
def api_thumbs():
    """
    Query Fandom pageimages and return a flat {Title: thumbUrl} dict.
    Titles must be pipe-separated, with underscores already OK.
    """
    size = request.args.get("size", "96")
    titles = request.args.get("titles", "")  # e.g. "Wheat|Carrot|Brown_Sugar"

    url = "https://hayday.fandom.com/api.php"
    params = {
        "action": "query",
        "prop": "pageimages",
        "pithumbsize": size,
        "titles": titles,
        "format": "json",
    }
    r = requests.get(url, params=params, timeout=10)
    j = r.json()

    pages = (j.get("query") or {}).get("pages") or {}

    # Build the flat map the frontend expects
    out = {}
    for page in pages.values():
        title = (page.get("title") or "").replace("_", " ").strip()
        src = ((page.get("thumbnail") or {}).get("source")) or None
        if title and src:
            # Frontend keys are normalized to lowercase names
            out[title.lower()] = src

    # Cache-friendly headers
    resp = jsonify(out)
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.get("/thumb/<slug>.png")
def serve_thumb(slug):
    path = THUMB_ROOT / f"{slug}.png"
    if not path.exists():
        abort(404)
    mime, _ = mimetypes.guess_type(str(path))
    resp = make_response(send_file(path, mimetype=mime or "image/png"))
    return _cache(resp)

@app.route("/admin/production", methods=["GET", "POST"])
def admin_production():
    if not is_staff():
        return "Unauthorized", 403

    client = get_db()
    col = client["hayday"]["ProductionGuide"]

    if request.method == "POST":
        if "delete_product" in request.form:
            to_delete = request.form.get("delete_product")
            col.delete_one({"product": to_delete})
        else:
            product = request.form.get("product").strip()
            machine = request.form.get("machine").strip()
            xp = int(request.form.get("xp"))
            price = int(request.form.get("price"))
            time_min = float(request.form.get("time_min"))
            level = int(request.form.get("level"))

            # Save image if uploaded
            image = request.files.get("image")
            if image and image.filename:
                filename = product.lower().replace(" ", "_") + ".png"
                image_path = os.path.join("static/img/hayday/products", filename)
                image.save(image_path)
                
            machine_image = request.files.get("machine_image")
            if machine_image and machine_image.filename:
                filename = machine.lower().replace(" ", "_") + ".png"
                image_path = os.path.join("static/img/hayday/machines", filename)
                machine_image.save(image_path)

            col.update_one(
                {"product": product},
                {"$set": {
                    "machine": machine,
                    "xp": xp,
                    "price": price,
                    "time_min": time_min,
                    "level": level
                }},
                upsert=True
            )


        return redirect("/admin/production")


    all_items = list(col.find().sort("level", 1))

    return render_template("admin_production.html", products=all_items, year=datetime.now().year)


@app.route("/admin")
def admin_panel():
    if not is_staff():  # Ensure only staff can access
        return "Unauthorized", 403
    return render_template("admin.html", year=datetime.now().year)


@app.route("/admin/backups")
def admin_backups():
    if "discord_id" not in session or not is_admin():
        return "Unauthorized", 403
    return render_template(
        "admin_backups.html",
        year=datetime.now().year,
        backup_bucket=BACKUP_R2_BUCKET,
        mongorestore_available=bool(_backup_mongorestore_path()),
    )


@app.get("/api/admin/backups")
def api_admin_backups_list():
    if "discord_id" not in session or not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        return jsonify({
            "ok": True,
            "bucket": BACKUP_R2_BUCKET,
            "mongorestore_available": bool(_backup_mongorestore_path()),
            "backups": _backup_list_objects(),
        })
    except Exception as e:
        app.logger.exception("Failed to list backups")
        return jsonify({"error": str(e)}), 500


@app.post("/api/admin/backups/inspect")
def api_admin_backups_inspect():
    if "discord_id" not in session or not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    user_id = (data.get("user_id") or "").strip()
    target_user_id = str(data.get("target_user_id") or user_id).strip()
    backup_type = _backup_key_type(key)

    try:
        if backup_type == "database":
            if not user_id:
                return jsonify({"error": "Enter a Discord user ID before inspecting a database backup."}), 400
            return jsonify(_backup_database_inspect_payload(key, user_id, target_user_id))
        if backup_type == "discord":
            return jsonify(_backup_discord_inspect_payload(key, user_id or None, target_user_id or None))
        return jsonify({"error": "Unsupported backup key."}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.exception("Failed to inspect backup %s", key)
        return jsonify({"error": str(e)}), 500


@app.post("/api/admin/backups/inspect/start")
def api_admin_backups_inspect_start():
    if "discord_id" not in session or not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    user_id = (data.get("user_id") or "").strip()
    target_user_id = str(data.get("target_user_id") or user_id).strip()
    backup_type = _backup_key_type(key)

    if backup_type != "database":
        return jsonify({"error": "Background inspection is only needed for database backups."}), 400
    if not user_id:
        return jsonify({"error": "Enter a Discord user ID before inspecting a database backup."}), 400

    try:
        _backup_validate_key(key, "database")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    job = _backup_start_job(
        "database_inspect",
        "Queued database backup inspection...",
        lambda update: (
            update("Downloading and restoring database backup...") or _backup_database_inspect_payload(key, user_id, target_user_id)
        ),
    )
    return jsonify(job)


@app.get("/api/admin/backups/jobs/<job_id>")
def api_admin_backups_job(job_id):
    if "discord_id" not in session or not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    job = _backup_public_job(job_id)
    if not job:
        return jsonify({"error": "Backup job expired or was not found."}), 404
    return jsonify(job)


@app.post("/api/admin/backups/restore")
def api_admin_backups_restore():
    if "discord_id" not in session or not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    user_id = (data.get("user_id") or "").strip()
    target_user_id = str(data.get("target_user_id") or user_id).strip()
    selections = data.get("selections") or {}
    confirm = (data.get("confirm") or "").strip()

    if confirm != "RESTORE":
        return jsonify({"error": "Type RESTORE to confirm the selected field restore."}), 400
    if not user_id:
        return jsonify({"error": "Missing user ID."}), 400

    try:
        return jsonify(_backup_restore_selected_fields(key, user_id, selections, target_user_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.exception("Failed to restore from backup %s for user %s", key, user_id)
        return jsonify({"error": str(e)}), 500


@app.post("/api/admin/backups/restore-discord-roles")
def api_admin_backups_restore_discord_roles():
    if "discord_id" not in session or not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    user_id = (data.get("user_id") or "").strip()
    target_user_id = str(data.get("target_user_id") or user_id).strip()
    confirm = (data.get("confirm") or "").strip()

    if confirm != "RESTORE ROLES":
        return jsonify({"error": "Type RESTORE ROLES to confirm Discord role restore."}), 400
    if not user_id:
        return jsonify({"error": "Missing user ID."}), 400

    try:
        return jsonify(_backup_restore_discord_roles(key, user_id, target_user_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.exception("Failed to restore Discord roles from backup %s for user %s", key, user_id)
        return jsonify({"error": str(e)}), 500



@csrf.exempt
@app.post("/easter/track")
def easter_track():
    action = (request.form.get("action") or "").strip()
    egg_id_raw = request.form.get("egg_id")
    meta = (request.form.get("meta") or "").strip()

    egg_id = None
    if egg_id_raw and str(egg_id_raw).isdigit():
        egg_id = int(egg_id_raw)

    inc = {}

    if action == "banner_view":
        inc["counters.banner_views"] = 1
    elif action == "banner_click":
        inc["counters.banner_clicks"] = 1
    elif action == "banner_close":
        inc["counters.banner_closes"] = 1
    elif action == "cta_click":
        inc["counters.cta_clicks"] = 1
    elif action == "egg_click":
        inc["counters.egg_clicks"] = 1
        if egg_id:
            inc[f"eggs.{egg_id}.clicks"] = 1
    elif action == "admin_view":
        inc["counters.admin_views"] = 1

    elif action == "admin_tab_click":
        inc["counters.admin_tab_clicks"] = 1

    elif action == "egg_view":
        if egg_id:
            inc[f"eggs.{egg_id}.views"] = 1
    if inc:
        _analytics_inc(EASTER_EVENT_ID, inc)
        _analytics_log("frontend_action", action_name=action, egg_id=egg_id, meta=meta)

    return jsonify(ok=True)

@csrf.exempt
@app.route("/admin/easter-wins", methods=["GET", "POST"])
def admin_easter_wins():
    if request.method == "POST":
        entered = (request.form.get("password") or "").strip()
        expected = os.getenv("EASTER_WINS_PASSWORD", "").strip()

        if expected and entered == expected:
            session["easter_wins_authed"] = True
            session.modified = True
            return redirect(url_for("admin_easter_wins"))

        return render_template(
            "admin_easter_wins.html",
            needs_password=True,
            wins=[],
            analytics={},
            logs=[],
            error="Wrong password."
        )

    if not _has_easter_wins_access():
        return render_template(
            "admin_easter_wins.html",
            needs_password=True,
            wins=[],
            analytics={},
            logs=[],
            error=None
        )

    _analytics_inc(EASTER_EVENT_ID, {"counters.admin_views": 1})
    _analytics_log("admin_dashboard_view")

    wins_col = get_db("Website")["easter_wins"]
    wins = list(
        wins_col.find({"event_id": EASTER_EVENT_ID})
        .sort("opened_at", -1)
        .limit(200)
    )

    analytics = _event_analytics_state()
    logs = _recent_event_logs(limit=100)
    stats = _event_stats_state()
    inventory = _event_inventory_state()

    counters = analytics.get("counters", {})
    results = analytics.get("results", {})
    performance = analytics.get("performance", {})

    total_open_attempts = int(counters.get("open_attempts", 0))
    real_wins = int(results.get("real_wins", 0))
    soft_losses = int(results.get("soft_losses", 0))
    successful_opens = real_wins + soft_losses

    win_rate = round((real_wins / successful_opens) * 100, 2) if successful_opens else 0
    soft_loss_rate = round((soft_losses / successful_opens) * 100, 2) if successful_opens else 0
    avg_open_response_ms = round(
        performance.get("open_response_ms_total", 0) / performance.get("open_requests", 1), 1
    ) if performance.get("open_requests", 0) else 0

    return render_template(
        "admin_easter_wins.html",
        needs_password=False,
        event=EASTER_EVENT,
        wins=wins,
        analytics=analytics,
        stats=stats,
        inventory=inventory,
        logs=logs,
        total_open_attempts=total_open_attempts,
        successful_opens=successful_opens,
        win_rate=win_rate,
        soft_loss_rate=soft_loss_rate,
        avg_open_response_ms=avg_open_response_ms,
        error=None
    )

@csrf.exempt
@app.get("/admin/easter-analytics.json")
def admin_easter_analytics_json():
    if not _has_easter_wins_access():
        return jsonify(ok=False, error="Unauthorized"), 403

    analytics = _event_analytics_state()
    stats = _event_stats_state()
    inventory = _event_inventory_state()
    logs = _recent_event_logs(limit=100)

    return jsonify(
        ok=True,
        analytics=_json_safe(analytics),
        stats=_json_safe(stats),
        inventory=_json_safe(inventory),
        logs=_json_safe(logs),
    )

@csrf.exempt
@app.post("/admin/easter-wins/logout")
def admin_easter_wins_logout():
    session.pop("easter_wins_authed", None)
    session.modified = True
    return redirect(url_for("admin_easter_wins"))


@csrf.exempt
@app.post("/admin/easter-wins/mark-delivered")
def admin_easter_mark_delivered():
    if not _has_easter_wins_access():
        return jsonify(ok=False, error="Unauthorized"), 403

    data = request.get_json(silent=True) or {}
    win_id = (data.get("win_id") or "").strip()

    if not win_id:
        return jsonify(ok=False, error="Missing win_id"), 400

    try:
        object_id = ObjectId(win_id)
    except Exception:
        return jsonify(ok=False, error="Invalid win_id"), 400

    wins_col = get_db("Website")["easter_wins"]

    result = wins_col.update_one(
        {
            "_id": object_id,
            "event_id": EASTER_EVENT_ID,
            "delivered": {"$ne": True}
        },
        {
            "$set": {
                "delivered": True,
                "delivered_by": str(session.get("discord_id")),
                "delivered_by_name": session.get("display_name") or session.get("username"),
                "delivered_at": datetime.now(timezone.utc),
            }
        }
    )

    if result.matched_count == 0:
        return jsonify(ok=False, error="Win not found or already delivered"), 404

    _analytics_log("admin_mark_delivered", win_id=win_id)

    return jsonify(
        ok=True,
        delivered_by=session.get("display_name") or session.get("username") or session.get("discord_id"),
        delivered_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )

@app.route("/summer", methods=["GET", "POST"])
def summer_event_page():
    access_error = None

    if request.args.get("reset") == "1":
        session.pop("summer_event_access", None)
        return redirect(url_for("summer_event_page"))

    if request.method == "POST":
        submitted_code = (request.form.get("access_code") or "").strip().lower()
        if secrets.compare_digest(submitted_code, SUMMER_EVENT_ACCESS_CODE):
            session["summer_event_access"] = True
            return redirect(url_for("summer_event_page"))
        access_error = "That code did not open the beach gate."

    return render_template(
        "summer_event.html",
        summer_event=SUMMER_EVENT,
        has_access=bool(session.get("summer_event_access")),
        access_error=access_error,
        meta=page_meta(
            title=SUMMER_EVENT["title"],
            description=SUMMER_EVENT["subtitle"],
            image=url_for("static", filename="img/summer/beach-bg.png", _external=True),
            url=url_for("summer_event_page", _external=True),
        ),
    )

@csrf.exempt
@app.route("/easter")
def easter_event_page():
    access = _easter_access_state()
    _analytics_track_page_view(access)

    return render_template(
        "easter_event.html",
        easter_live=EASTER_LIVE,
        year=datetime.now(timezone.utc).year,
        event=EASTER_EVENT,
        available_count=_next_available_eggs(),
        opened=_event_open_state(str(session["discord_id"])) if "discord_id" in session else {},
        stats=_event_stats_state(),
        analytics=_event_analytics_state(),
        remaining_real_prizes=_remaining_prizes(_event_inventory_state()),
        live_feed=_easter_feed_entries(limit=20),
        testing_enabled=False,
        testing_config=EASTER_TESTING,
        easter_access=access,
        error=None,
    )

EASTER_FEED_CACHE = {
    "expires": 0,
    "payload": None,
}

@csrf.exempt
@app.get("/api/easter-feed")
def api_easter_feed():
    now = time.time()

    if EASTER_FEED_CACHE["payload"] is not None and now < EASTER_FEED_CACHE["expires"]:
        return jsonify(EASTER_FEED_CACHE["payload"])

    payload = {
        "ok": True,
        "feed": _json_safe(_easter_feed_entries(limit=20))
    }

    EASTER_FEED_CACHE["payload"] = payload
    EASTER_FEED_CACHE["expires"] = now + 8   # cache for 8 seconds

    return jsonify(payload)

@csrf.exempt
@limiter.limit("5 per minute")
@app.post("/easter/open")
def easter_open_egg():
    start_ts = time.time()
    access = _easter_access_state()

    if not access["logged_in"]:
        _analytics_inc(EASTER_EVENT_ID, {"counters.login_gate_hits": 1})
        _analytics_log("open_blocked_login")
        return jsonify(ok=False, error="Please log in with Discord first."), 401

    if not access["is_member"]:
        _analytics_inc(EASTER_EVENT_ID, {"counters.member_gate_hits": 1})
        _analytics_log("open_blocked_member")
        return jsonify(ok=False, error="You must be a server member to open eggs."), 403
        
    if _is_easter_event_over():
        _analytics_inc(EASTER_EVENT_ID, {"counters.event_over_attempts": 1})
        _analytics_log("open_blocked_event_over")
        return jsonify(ok=False, error="This Easter event has ended."), 400
    
    try:
        egg_id = int(request.form.get("egg_id", 0))
    except ValueError:
        return jsonify(ok=False, error="Invalid egg id"), 400

    available_count = _next_available_eggs()
    discord_id = str(session["discord_id"])
    opened = _event_open_state(discord_id)
    key = str(egg_id)

    if egg_id < 1 or egg_id > len(EASTER_EVENT["eggs"]):
        _analytics_track_open_result(
            egg_id=egg_id,
            result="invalid",
            response_ms=int((time.time() - start_ts) * 1000),
        )
        return jsonify(ok=False, error="Unknown egg"), 404

    if egg_id > available_count:
        _analytics_track_open_result(
            egg_id=egg_id,
            result="locked",
            response_ms=int((time.time() - start_ts) * 1000),
        )
        return jsonify(ok=False, error="This egg is not unlocked yet."), 400

    if key in opened:
        _analytics_track_open_result(
            egg_id=egg_id,
            result="already_opened",
            reward=opened[key]["reward"],
            rarity=opened[key]["rarity"],
            response_ms=int((time.time() - start_ts) * 1000),
        )
        return jsonify(
            ok=True,
            already_opened=True,
            reward=opened[key]["reward"],
            rarity=opened[key]["rarity"]
        )
    
    try:
        _rollover_unused_stock_to_egg(egg_id)

        claimed = _claim_easter_egg_slot(discord_id, egg_id)
        if not claimed:
            opened = _event_open_state(discord_id)
            existing = opened.get(key)
            if existing:
                _analytics_track_open_result(
                    egg_id=egg_id,
                    result="already_opened",
                    reward=existing.get("reward"),
                    rarity=existing.get("rarity"),
                    response_ms=int((time.time() - start_ts) * 1000),
                )
                return jsonify(
                    ok=True,
                    already_opened=True,
                    reward=existing.get("reward", "Already opened"),
                    rarity=existing.get("rarity", "bonus")
                )

            _analytics_track_open_result(
                egg_id=egg_id,
                result="already_opened",
                response_ms=int((time.time() - start_ts) * 1000),
            )
            return jsonify(ok=False, error="This egg was already opened."), 409

        cols = _easter_collections()
        events_col = cols["events"]

        events_col.update_one(
            {"_id": EASTER_EVENT_ID},
            {
                "$inc": {
                    "stats.total_opens": 1,
                    f"stats.eggs.{egg_id}.total_opens": 1
                }
            }
        )

        inventory = _egg_inventory_state(egg_id)
        stats = _egg_stats_state(egg_id)

        forced_result = None
        if _is_easter_testing_enabled():
            forced_result = EASTER_TESTING.get("force_result")

        if forced_result == "win":
            did_win = True
        elif forced_result == "soft_loss":
            did_win = False
        else:
            did_win = _should_win(inventory, stats)

        if did_win:
            reward = _pick_weighted_prize(egg_id)
            if reward:
                rarity = "winner"

                cols = _easter_collections()
                events_col = cols["events"]
                wins_col = cols["wins"]

                events_col.update_one(
                    {"_id": EASTER_EVENT_ID},
                    {
                        "$inc": {
                            "stats.total_real_wins": 1,
                            f"stats.eggs.{egg_id}.total_real_wins": 1
                        }
                    }
                )

                wins_col.insert_one({
                    "event_id": EASTER_EVENT_ID,
                    "discord_id": str(session["discord_id"]),
                    "display_name": session.get("display_name"),
                    "username": session.get("username"),
                    "egg_id": egg_id,
                    "reward": reward,
                    "rarity": "winner",
                    "opened_at": datetime.now(timezone.utc),
                })

                _insert_easter_feed_entry(
                    discord_id=str(session["discord_id"]),
                    egg_id=egg_id,
                    reward=reward,
                    rarity="winner",
                )

                _analytics_track_open_result(
                    egg_id=egg_id,
                    result="win",
                    reward=reward,
                    rarity=rarity,
                    response_ms=int((time.time() - start_ts) * 1000),
                )                    

            else:
                rarity = "bonus"
                reward = random.choice(EASTER_EVENT["soft_loss_rewards"])
        else:
            rarity = "bonus"
            reward = random.choice(EASTER_EVENT["soft_loss_rewards"])

        if rarity == "bonus":
            cols = _easter_collections()
            events_col = cols["events"]

            events_col.update_one(
                {"_id": EASTER_EVENT_ID},
                {
                    "$inc": {
                        "stats.soft_losses": 1,
                        f"stats.eggs.{egg_id}.soft_losses": 1
                    }
                }
            )

            _insert_easter_feed_entry(
                discord_id=str(session["discord_id"]),
                egg_id=egg_id,
                reward=reward,
                rarity="bonus",
            )

            _analytics_track_open_result(
                egg_id=egg_id,
                result="soft_loss",
                reward=reward,
                rarity=rarity,
                response_ms=int((time.time() - start_ts) * 1000),
            )                

        _save_opened_egg(discord_id, egg_id, reward, rarity)

        return jsonify(
            ok=True,
            already_opened=False,
            reward=reward,
            rarity=rarity
        )

    except Exception:
        _release_pending_easter_egg(discord_id, egg_id)
        raise

@app.route("/admin/competition")
def admin_competition():
    if not is_staff(): 
        return "Unauthorized", 403

    phase, default_comp = _phase_today()
    comp_id = request.args.get("comp_id", default_comp)

    client = get_db()
    db = client["Website"]
    entries = list(db["CompEntries"].find({"comp_id": comp_id}).sort("created_at", -1))
    vote_counts = _vote_counts_for(comp_id, client)

    ids = [str(e.get("user_id")) for e in entries if e.get("user_id")]
    users = list(db["usernames"].find({"_id": {"$in": ids}}))
    user_map = {u["_id"]: u for u in users}
    bans = list(db["CompSubmissionBans"].find({"comp_id": comp_id}).sort("banned_at", -1))
    ban_map = {str(b.get("user_id")): b for b in bans if b.get("user_id")}
    month_options = sorted(
        set(db["CompEntries"].distinct("comp_id") + db["CompSubmissionBans"].distinct("comp_id") + [comp_id]),
        reverse=True,
    )
    stats = {
        "entries": len(entries),
        "submitters": len(set(ids)),
        "votes": sum(vote_counts.values()),
        "bans": len(bans),
    }

    return render_template("admin_competition.html",
                           comp_id=comp_id, phase=phase,
                           entries=entries, vote_counts=vote_counts,
                           user_map=user_map, ban_map=ban_map,
                           bans=bans, stats=stats,
                           month_options=month_options,
                           moderation_reasons=COMP_MODERATION_REASONS)

@csrf.exempt
@app.post("/admin/competition/caption/<entry_id>")
def admin_competition_caption(entry_id):
    if not is_staff(): 
        return "Unauthorized", 403
    new_caption = (request.form.get("caption") or "").strip()[:35]
    db = get_db("Website")
    db["CompEntries"].update_one(
        {"_id": ObjectId(entry_id)},
        {"$set": {"caption": new_caption}}
    )
    flash("Caption updated.", "success")
    return redirect(url_for("admin_competition", comp_id=request.args.get("comp_id")))

@csrf.exempt
@app.post("/admin/competition/delete/<entry_id>")
def admin_competition_delete(entry_id):
    if not is_staff():
        return "Unauthorized", 403
    db = get_db("Website")
    try:
        oid = ObjectId(entry_id)
    except Exception:
        return "Invalid entry id", 400
    entry = db["CompEntries"].find_one({"_id": oid})
    if not entry:
        flash("Entry was already deleted.", "warning")
        return redirect(url_for("admin_competition", comp_id=request.args.get("comp_id")))
    comp_id = entry.get("comp_id") or request.args.get("comp_id")
    db["CompEntries"].delete_one({"_id": oid})
    db["CompVotes"].delete_many({"entry_id": entry_id})
    if comp_id:
        _competition_clear_results_cache(comp_id)
    flash("Entry deleted (votes removed).", "success")
    return redirect(url_for("admin_competition", comp_id=comp_id))


@csrf.exempt
@app.post("/admin/competition/moderate/<entry_id>")
def admin_competition_moderate(entry_id):
    if not is_staff():
        return "Unauthorized", 403

    db = get_db("Website")
    try:
        oid = ObjectId(entry_id)
    except Exception:
        return "Invalid entry id", 400

    entry = db["CompEntries"].find_one({"_id": oid})
    if not entry:
        flash("Entry was already deleted.", "warning")
        return redirect(url_for("admin_competition", comp_id=request.args.get("comp_id")))

    comp_id = str(entry.get("comp_id") or request.args.get("comp_id") or _phase_today()[1])
    user_id = str(entry.get("user_id") or "").strip()
    if not user_id:
        flash("Entry has no user id, so it cannot be monthly-banned.", "error")
        return redirect(url_for("admin_competition", comp_id=comp_id))

    reason_code = (request.form.get("reason_code") or "other").strip()
    if reason_code not in COMP_MODERATION_REASONS:
        reason_code = "other"
    staff_note = (request.form.get("staff_note") or "").strip()[:500]
    reason = COMP_MODERATION_REASONS[reason_code]
    if staff_note:
        reason = f"{reason} Staff note: {staff_note}"

    now = datetime.now(timezone.utc)
    actor_id = str(session.get("discord_id") or "")
    actor_name = session.get("username") or session.get("display_name") or "Website Staff"

    removed_entries = list(db["CompEntries"].find({"comp_id": comp_id, "user_id": user_id}))
    if not removed_entries:
        removed_entries = [entry]
    removed_entry_ids = [str(e["_id"]) for e in removed_entries if e.get("_id")]
    primary_entry = entry

    moderation_doc = {
        "comp_id": comp_id,
        "user_id": user_id,
        "reason_code": reason_code,
        "reason": reason,
        "staff_note": staff_note,
        "removed_entries": removed_entries,
        "removed_entry_ids": removed_entry_ids,
        "primary_image_url": primary_entry.get("image_url", ""),
        "primary_caption": primary_entry.get("caption", ""),
        "created_at": now,
        "created_by": actor_id,
        "created_by_name": actor_name,
    }
    moderation_id = db["CompModerationActions"].insert_one(moderation_doc).inserted_id

    revoke_result = {
        "revoked": False,
        "amount": 0,
        "balance_after": None,
        "claim_id": _competition_reward_claim_id(comp_id, user_id, "submit"),
    }
    if user_id.isdigit():
        revoke_result = _competition_revoke_submit_reward(
            comp_id,
            user_id,
            entry_id=str(primary_entry["_id"]),
            moderation_id=moderation_id,
        )

    votes_removed = 0
    for removed_entry_id in removed_entry_ids:
        votes_removed += db["CompVotes"].delete_many({
            "comp_id": comp_id,
            "entry_id": removed_entry_id,
        }).deleted_count

    db["CompEntries"].delete_many({"comp_id": comp_id, "user_id": user_id})
    _competition_clear_results_cache(comp_id)

    ban_doc = {
        "comp_id": comp_id,
        "user_id": user_id,
        "reason_code": reason_code,
        "reason": reason,
        "staff_note": staff_note,
        "image_url": primary_entry.get("image_url", ""),
        "caption": primary_entry.get("caption", ""),
        "entry_id": str(primary_entry["_id"]),
        "removed_entry_ids": removed_entry_ids,
        "banned_at": now,
        "banned_by": actor_id,
        "banned_by_name": actor_name,
        "moderation_id": str(moderation_id),
        "reward_revoked": bool(revoke_result["revoked"]),
        "revoke_amount": int(revoke_result["amount"]),
        "balance_after_revoke": revoke_result["balance_after"],
        "votes_removed": votes_removed,
        "warning_status": "pending",
    }
    db["CompSubmissionBans"].update_one(
        {"_id": _competition_ban_id(comp_id, user_id)},
        {"$set": ban_doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    warning_message = (
        f"Your Farm Design Contest submission for {comp_id} was removed. "
        f"{reason} You cannot submit again during this contest month."
    )
    if revoke_result["revoked"]:
        warning_message += f" The {revoke_result['amount']:,} server coin submission reward was removed from your balance."

    bot_payload = {
        "type": "competition_submission_moderation",
        "user_id": user_id,
        "comp_id": comp_id,
        "entry_id": str(primary_entry["_id"]),
        "moderation_id": str(moderation_id),
        "reason_code": reason_code,
        "reason": reason,
        "caption": primary_entry.get("caption", ""),
        "image_url": primary_entry.get("image_url", ""),
        "message": warning_message,
        "reward_revoked": bool(revoke_result["revoked"]),
        "revoke_amount": int(revoke_result["amount"]),
        "balance_after_revoke": revoke_result["balance_after"],
        "moderator_id": actor_id,
        "moderator_name": actor_name,
    }
    notify_result = _competition_notify_bot_moderation(bot_payload)
    warning_update = {
        "warning_status": "sent" if notify_result.get("ok") else "failed",
        "warning_result": notify_result,
        "warning_checked_at": datetime.now(timezone.utc),
    }
    if notify_result.get("ok"):
        warning_update["warning_sent_at"] = datetime.now(timezone.utc)
    db["CompSubmissionBans"].update_one(
        {"_id": _competition_ban_id(comp_id, user_id)},
        {"$set": warning_update},
    )
    db["CompModerationActions"].update_one(
        {"_id": moderation_id},
        {"$set": {
            "revoke_result": revoke_result,
            "votes_removed": votes_removed,
            "bot_payload": bot_payload,
            "bot_notify_result": notify_result,
        }},
    )

    coin_text = (
        f" Removed {revoke_result['amount']:,} coins; new balance {revoke_result['balance_after']:,}."
        if revoke_result["revoked"]
        else " No submit reward had been claimed, so no coins were removed."
    )
    warn_text = " Discord warning sent." if notify_result.get("ok") else f" Discord warning failed: {notify_result.get('error', 'unknown error')}"
    flash(f"Submission removed and user banned for {comp_id}.{coin_text}{warn_text}", "success" if notify_result.get("ok") else "warning")
    return redirect(url_for("admin_competition", comp_id=comp_id))


@csrf.exempt
@app.post("/admin/competition/unban/<user_id>")
def admin_competition_unban(user_id):
    if not is_staff():
        return "Unauthorized", 403

    comp_id = str(request.form.get("comp_id") or request.args.get("comp_id") or _phase_today()[1])
    user_id = str(user_id or "").strip()
    if not user_id:
        return "Missing user id", 400

    db = get_db("Website")
    ban_id = _competition_ban_id(comp_id, user_id)
    ban = db["CompSubmissionBans"].find_one({"_id": ban_id})
    if not ban:
        flash("That user is not banned for this competition month.", "warning")
        return redirect(url_for("admin_competition", comp_id=comp_id))

    now = datetime.now(timezone.utc)
    actor_id = str(session.get("discord_id") or "")
    actor_name = session.get("username") or session.get("display_name") or "Website Staff"

    reward_claim_reset = False
    claim_id = _competition_reward_claim_id(comp_id, user_id, "submit")
    if ban.get("reward_revoked"):
        claim = db["CompRewardClaims"].find_one({"_id": claim_id}, {"revoked_at": 1})
        if claim and claim.get("revoked_at"):
            db["CompRewardClaims"].delete_one({"_id": claim_id})
            reward_claim_reset = True

    db["CompModerationActions"].insert_one({
        "type": "ban_lift",
        "comp_id": comp_id,
        "user_id": user_id,
        "ban_id": ban_id,
        "ban_snapshot": ban,
        "reward_claim_reset": reward_claim_reset,
        "created_at": now,
        "created_by": actor_id,
        "created_by_name": actor_name,
    })
    db["CompSubmissionBans"].delete_one({"_id": ban_id})

    reward_text = " Their submit reward eligibility was reset." if reward_claim_reset else ""
    flash(f"Monthly competition ban removed for user {user_id}.{reward_text}", "success")
    return redirect(url_for("admin_competition", comp_id=comp_id))

@app.route("/api/live-auctions")
def live_auctions():
    client = get_db()
    db = client["hayday"]
    now = datetime.now(timezone.utc)
    auctions = list(db["auctions"].find({
        "status": "active",
        "end_time": {"$gt": now}
    }))
    user_cache = client["Website"]["UserCache"]

    results = []
    for auction in auctions:
        data = serialize_auction(auction)
        bidder_id = data.get("highest_bidder")
        if bidder_id:
            user_doc = user_cache.find_one({"user_id": bidder_id})
            if user_doc:
                data["display_name"] = user_doc.get("display_name") or user_doc.get("username")
                data["bidder_tag"] = user_doc.get("discord_tag")
        results.append(data)

    return jsonify(results)


@limiter.limit("10/minute")
@app.route("/api/bid", methods=["POST"])
def api_bid():
    user_id = session.get("discord_id")
    if not user_id:
        return jsonify({"success": False, "message": "Not logged in via Discord"}), 401
    user_roles = session.get("roles", [])

    if not user_roles or str(UNVERIFIED_ROLE_ID) in user_roles:
        return jsonify({
            "success": False,
            "message": "鉂?You must be a verified member of the Discord to bid. Join here: https://discord.gg/hayday"
        }), 403

    if str(MEMBER_ROLE_ID) not in user_roles:
        return jsonify({
            "success": False,
            "message": "鉂?You must be a member of the Discord server to place bids. Join here: https://discord.gg/hayday"
        }), 403

    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400

    auction_id = data.get("auction_id")
    amount = data.get("amount")

    try:
        amount = int(amount)
        auction_id_int = int(auction_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid input (amount or auction_id)"}), 400


    if amount <= 0:
        return jsonify({"success": False, "message": "Invalid input"}), 400

    client = get_db()
    db = client["hayday"]
    auction = db["auctions"].find_one({"message_id": auction_id_int, "status": "active"})

    if not auction:
        return jsonify({"success": False, "message": "Auction not found or already ended"}), 404

    if str(auction["owner_id"]) == str(user_id):
        return jsonify({"success": False, "message": "鉂?You cannot bid on your own auction."}), 403

    now = datetime.now(timezone.utc)
    end_time = auction["end_time"]
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    if end_time <= now:
        return jsonify({"success": False, "message": "Auction already expired"}), 410
    
    # Step 2: Bid validation 
    starting_bid = int(auction.get("starting_bid", 0) or 0)
    current_bid = int(auction.get("current_bid", 0) or 0)
    min_increment = int(auction.get("min_increment") or 1)

    # If there are no bids yet, the minimum allowed is starting_bid
    if current_bid <= 0:
        min_allowed = starting_bid
        if amount < min_allowed:
            return jsonify({
                "success": False,
                "message": f"Bid must be at least {min_allowed:,} (starting bid)."
            }), 400
    else:
        baseline = max(current_bid, starting_bid)
        min_allowed = baseline + min_increment
        if amount < min_allowed:
            return jsonify({
                "success": False,
                "message": f"Bid must be at least {min_allowed:,} (min increment {min_increment:,})."
            }), 400

    # Step 3: Update auction (ATOMIC)
    result = db["auctions"].update_one(
        {
            "_id": auction["_id"],
            "status": "active",
            # Guard against race: only update if current_bid is unchanged
            "current_bid": current_bid
        },
        {
            "$set": {
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
            }
        }
    )

    if result.modified_count == 0:
        # Someone else updated the bid first 鈫?tell the user to re-try with the latest number
        return jsonify({
            "success": False,
            "message": "Another bid landed just before yours. Please refresh and try again."
        }), 409

    try:
        requests.post(
            os.getenv("BOT_WEBHOOK_URL") + "/webhook/auction",
            json={
                "message_id": auction_id_int,
                "amount": amount,
                "user_id": int(user_id),
                "channel_id": auction["channel_id"]
            },
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
            timeout=3
        )
    except Exception as e:
        print(f"Failed to ping bot webhook: {e}")

    return jsonify({"success": True, "message": "Bid placed!"})

@app.after_request
def apply_security_headers(response):
    # Hide server details
    response.headers["Server"] = "hidden"

    # Core protections
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"

    # Updated CSP - currently allowing unsafe-inline until nonce migration is ready
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https://cdn.discordapp.com https://cdn-icons-png.flaticon.com "
        "https://upload.hayday.info https://img.hayday.info https://pub-d697248b8aeb486487aa84c6781bea50.r2.dev "
        "https://hayday-upload.davisandersen16.workers.dev; "  # TEMP for old images
        "script-src 'self' 'unsafe-inline' https://api.ipify.org https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' https://api.ipify.org; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )


    # Feature policies
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # Enforce HTTPS for 1 year
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

    return response

@app.before_request
def track_page_views():
    ignore_prefixes = (
        "/api", "/thumb-file", "/img-proxy", "/log-interaction",
        "/static", "/assets", "/webhook", "/oauth", "/internal",
    )
    ignore_exact = ("/robots.txt", "/favicon.ico", "/callback")
    file_exts = (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".webp",
                 ".svg", ".ico", ".json", ".xml", ".map", ".txt", ".csv")

    path = request.path

    if (
        request.endpoint == "static"
        or any(path.startswith(p) for p in ignore_prefixes)
        or path in ignore_exact
        or any(path.endswith(ext) for ext in file_exts)
    ):
        return

    with PAGEVIEW_LOCK:
        PAGEVIEW_BUFFER[path] += 1

@app.before_request
def force_canonical_host():
    host = request.host.split(":")[0].lower()

    # Do not redirect OAuth callback requests
    if request.path == "/callback":
        return

    if host == "www.hayday.info":
        return redirect(f"https://hayday.info{request.full_path}", code=301)

@app.before_request
def ensure_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

@app.before_request
def set_session_lifetime():
    session.permanent = True
    user_roles = session.get("roles", [])

    is_staff_role = any(
        int(role) in STAFF_ROLES
        for role in user_roles
        if str(role).isdigit()
    )

    if is_staff_role:
        app.permanent_session_lifetime = timedelta(days=7)
    else:
        app.permanent_session_lifetime = timedelta(days=14)

@app.before_request
def block_dangerous_methods():
    if request.method not in ("GET", "POST", "HEAD", "OPTIONS"):
        app.logger.warning(f"[BLOCKED METHOD] {request.remote_addr} tried {request.method} on {request.path}")
        abort(405)  # Method Not Allowed

@app.before_request
def handle_scanner_protection():
    global banned_ips_loaded, BANNED_IPS

    raw_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    real_ip = raw_ip.split(",")[0].strip()
    internal_ip = request.remote_addr
    path = request.path.lower()
    now = time.time()

    if any(path.startswith(prefix) for prefix in SCANNER_EXEMPT_PREFIXES):
        return

    # Load banned IPs from MongoDB once
    global banned_ips_loaded, BANNED_IPS, BANNED_IPS_LOADED_AT

    if (not banned_ips_loaded) or (time.time() - BANNED_IPS_LOADED_AT > BANNED_IPS_REFRESH_SECONDS):
        client = get_db()
        banned = client["Security"]["banned_ips"].find()
        BANNED_IPS = set(doc["_id"] for doc in banned)
        banned_ips_loaded = True
        BANNED_IPS_LOADED_AT = time.time()

    # Auto-block if IP is banned
    if real_ip in BANNED_IPS:
        client = get_db()
        doc = client["Security"]["banned_ips"].find_one({"_id": real_ip})
        if doc:
            banned_at = doc.get("banned_at")
            if banned_at and (datetime.utcnow() - banned_at).total_seconds() >= BAN_TIME:
                # Expired - unban them
                client["Security"]["banned_ips"].delete_one({"_id": real_ip})
                BANNED_IPS.discard(real_ip)
                app.logger.info(f"[UNBANNED] IP {real_ip} was automatically unbanned after expiry")
            else:
                # Extend the ban if they hit again
                client["Security"]["banned_ips"].update_one(
                    {"_id": real_ip},
                    {"$set": {"banned_at": datetime.utcnow()}},
                    upsert=True
                )
                app.logger.warning(f"[AUTO-EXTENDED BAN] {real_ip} tried {path} again - ban extended (internal: {internal_ip})")
                abort(403)

    # Check for scanner-like behavior
    matched = next((pattern for pattern in SCANNER_PATHS if pattern in path), None)
    if matched:
        ip_hits[real_ip].append(now)
        ip_hits[real_ip] = [t for t in ip_hits[real_ip] if now - t < BAN_TIME]

        if len(ip_hits[real_ip]) >= SCAN_THRESHOLD:
            BANNED_IPS.add(real_ip)
            client = get_db()
            client["Security"]["banned_ips"].update_one(
                {"_id": real_ip},
                {"$set": {
                    "banned_at": datetime.utcnow(),
                    "reason": f"Matched pattern: {matched}",
                    "hit_count": len(ip_hits[real_ip]),
                    "internal_ip": internal_ip
                }},
                upsert=True
            )
            app.logger.warning(f"[🔥 BANNED] IP {real_ip} matched '{matched}' {len(ip_hits[real_ip])} times (internal: {internal_ip})")
        else:
            app.logger.warning(f"[BLOCKED] Scanner-like request: {real_ip} tried {path} (matched: {matched})")

        abort(403)


@app.route("/debug-ip")
def debug_ip():
    real_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    internal_ip = request.remote_addr

    return f"""
        <h1>📳 IP Debug</h1>
        <p><strong>Real IP:</strong> {real_ip}</p>
        <p><strong>Internal IP:</strong> {internal_ip}</p>
    """

@app.route("/submit_bid", methods=["POST"])
def submit_bid():
    return jsonify({"error": "Deprecated. Use /api/bid"}), 410

@app.route("/auctions")
def auctions_page():
    client = get_db()
    db = client["hayday"]
    auctions = list(
        db["auctions"].find(
            {"status": "active"},
            {
                "item": 1,
                "quantity": 1,
                "starting_bid": 1,
                "min_increment": 1,
                "current_bid": 1,
                "highest_bidder": 1,
                "owner_id": 1,
                "message_id": 1,
                "end_time": 1,
                "status": 1
            }
        ).sort("end_time", 1)
    )
    needed_user_ids = set()
    for auc in auctions:
        if auc.get("owner_id") is not None:
            needed_user_ids.add(str(auc["owner_id"]))
        if auc.get("highest_bidder") is not None:
            needed_user_ids.add(str(auc["highest_bidder"]))

    user_map = {}
    if needed_user_ids:
        user_cache = client["Website"]["UserCache"].find(
            {"_id": {"$in": list(needed_user_ids)}}
        )
        user_map = {str(u["_id"]): u for u in user_cache}

    now = datetime.now(pytz_timezone("Europe/Copenhagen"))  # local time

    for auc in auctions:
        end = auc.get("end_time")
        if end:
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            end = end.astimezone(COPENHAGEN_TZ)
            auc["end_time"] = end  # update for HTML countdown
            auc["time_remaining"] = str(end - now).split(".")[0]
        else:
            auc["time_remaining"] = "Unknown"

        bidder_id = str(auc.get("highest_bidder"))
        user_info = user_map.get(bidder_id, {})
        auc["bidder_tag"] = user_info.get("tag") or f"User {bidder_id}"
        auc["display_name"] = user_info.get("display_name")
        auc["avatar"] = user_info.get("avatar")

        # Owner info for Jinja
        owner_id = str(auc.get("owner_id"))
        owner_info = user_map.get(owner_id, {})
        auc["owner_display_name"] = owner_info.get("display_name")
        auc["owner_tag"] = owner_info.get("tag")
        auc["owner_avatar"] = owner_info.get("avatar")

    discord_id = session.get("discord_id")
    return render_template("auctions.html", auctions=auctions, year=now.year, discord_id=discord_id)




@app.route("/current-bans")
def current_bans():
    search = request.args.get("search", "").strip().lower()
    page = int(request.args.get("page", 1))
    per_page = 12

    client = get_db()
    db = client["Moderation"]

    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": re.escape(search), "$options": "i"}},
            {"reason": {"$regex": re.escape(search), "$options": "i"}},
        ]

    total = db["ban_list"].count_documents(query)
    bans_paginated = list(
        db["ban_list"]
        .find(query)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    if request.args.get("ajax") == "1":
        return render_template(
            "partials/ban_cards.html",
            bans=bans_paginated,
            is_staff=is_staff()
        )

    return render_template(
        "current_bans.html",
        bans=bans_paginated,
        page=page,
        total_pages=(total + per_page - 1) // per_page,
        search=search,
        is_staff=is_staff
    )

@app.route("/mod-action", methods=["POST"])
def mod_action():
    if "discord_id" not in session or not is_staff():
        return redirect(url_for("home"))

    user_input = request.form.get("user_input")
    action = request.form.get("action")
    duration_raw = request.form.get("duration", "")
    reason = request.form.get("reason", "No reason provided")

    try:
        target_user_id = str(user_input).strip("<@!>")
        target_user_id = int(target_user_id)

        client = get_db()
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
            flash("鉂?Unknown action selected.", "error")

    except Exception as e:
        print(f"[mod_action] Error: {e}")
        flash("鉂?Failed to perform action.", "error")

    return redirect("/staff-panel")


@app.route("/api/news")
def api_news():
    client = get_db()
    collection = client["hayday"]["NewsFeed"]
    items = list(collection.find({"timestamp": {"$exists": True}}).sort("timestamp", -1).limit(5))

    return jsonify([
        {
            "title": item.get("title", "Untitled"),
            "url": item.get("_id", "#"),
            "timestamp": item.get("timestamp") or datetime.utcnow().isoformat(),
            "source": item.get("source", "unknown"),
            "thumbnail": item.get("thumbnail")  # ensure this field is populated by your bot
        }
        for item in items
    ])


@app.route("/production_guide")
def production():
    return render_template("production_guide.html")

@app.route("/scam-ids")
def scam_ids():
    if not is_staff():
        return "Unauthorized", 403
    
    client = get_db()
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
    meta = page_meta()
    year = datetime.now(timezone.utc).year
    resp = make_response(render_template("index.html", year=year, meta=meta))
    resp.headers["Cache-Control"] = "public, max-age=60"
    return resp

@app.route("/login-page")
def login_page():
    next_path = _safe_next_path(request.args.get("next", "/"))
    return redirect(url_for("login", next=next_path))

@app.route("/login")
@limiter.limit("5 per minute", key_func=get_remote_address, error_message="Too many login attempts. Please wait a minute.")
def login():
    next_page = _safe_next_path(request.args.get("next", _current_request_path()))
    nonce = secrets.token_urlsafe(16)
    state = oauth_state_serializer.dumps({"nonce": nonce, "next": next_page})
    session["oauth_state"] = nonce
    session["next_page"] = next_page
    session.modified = True

    return redirect(
        f"https://discord.com/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds.members.read"
        f"&guild_id=959220051427340379"
        f"&prompt=consent"
        f"&state={state}"
    )


@app.route("/admin/logs/export")
def export_logs():
    if not is_staff():
        return "Unauthorized", 403
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    log_type = request.args.get("type")

    query = {"timestamp": {"$exists": True}}
    if log_type:
        query["type"] = log_type

    # Date filtering
    if start_date_str:
        query["timestamp"] = query.get("timestamp", {})
        query["timestamp"]["$gte"] = start_date_str  # "YYYY-MM-DD"

    if end_date_str:
        try:
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
            query["timestamp"]["$lt"] = end_dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    client = get_db()
    logs_cursor = client["Website"]["Logs"].find(query).sort("timestamp", -1)

    def generate():
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(["Type", "Author", "Channel", "Timestamp", "Content", "Images"])
        yield si.getvalue()
        si.seek(0)
        si.truncate(0)

        for log in logs_cursor:
            images = ", ".join(log.get("images", [])) if "images" in log else ""
            if log.get("type") == "message_edit":
                content = f"Before: {log.get('before', '')} | After: {log.get('after', '')}"
            else:
                content = log.get("content", "")

            writer.writerow([
                log.get("type"),
                log.get("author", {}).get("name", ""),
                log.get("channel_name", ""),
                log.get("timestamp", ""),
                content,
                images
            ])
            yield si.getvalue()
            si.seek(0)
            si.truncate(0)

    filename = f"discord_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        stream_with_context(generate()),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@app.route("/admin/logs", methods=["GET", "POST"])
def view_logs():
    if not is_staff():
        return "Unauthorized", 403
    year = datetime.now(timezone.utc).year
    now = datetime.now(timezone.utc)

    search_term = request.form.get("search", "").strip() if request.method == "POST" else request.args.get("search", "").strip()
    selected_channel = request.form.get("channel_filter", "") if request.method == "POST" else request.args.get("channel_filter", "").strip()
    preset = request.args.get("preset", "").strip()

    deleted_page = int(request.args.get("deleted_page", 1))
    edited_page = int(request.args.get("edited_page", 1))
    per_page = 6

    query = {"timestamp": {"$exists": True}}

    if search_term:
        query["$or"] = [
            {"author.name": {"$regex": search_term, "$options": "i"}},
            {"author.id": search_term}
        ]

    if selected_channel:
        query["channel_name"] = selected_channel

    if preset == "24h":
        query["timestamp"]["$gte"] = now - timedelta(hours=24)
    elif preset == "7d":
        query["timestamp"]["$gte"] = now - timedelta(days=7)
    elif preset == "this_week":
        start_of_week = now - timedelta(days=now.weekday())
        query["timestamp"]["$gte"] = datetime(start_of_week.year, start_of_week.month, start_of_week.day, tzinfo=timezone.utc)

    client = get_db()
    logs_collection = client["Website"]["Logs"]

    deleted_query = dict(query)
    deleted_query["type"] = "message_delete"

    edited_query = dict(query)
    edited_query["type"] = "message_edit"

    deleted_total = logs_collection.count_documents(deleted_query)
    edited_total = logs_collection.count_documents(edited_query)

    deleted_logs = list(
        logs_collection.find(deleted_query)
        .sort("timestamp", -1)
        .skip((deleted_page - 1) * per_page)
        .limit(per_page)
    )

    edited_logs = list(
        logs_collection.find(edited_query)
        .sort("timestamp", -1)
        .skip((edited_page - 1) * per_page)
        .limit(per_page)
    )

    channels = logs_collection.distinct("channel_name", {"channel_name": {"$ne": None}})

    return render_template(
        "logs.html",
        deleted_logs=deleted_logs,
        edited_logs=edited_logs,
        deleted_page=deleted_page,
        deleted_total=deleted_total,
        edited_page=edited_page,
        edited_total=edited_total,
        per_page=per_page,
        search_term=search_term,
        selected_channel=selected_channel,
        preset=preset,
        channels=sorted(channels),
        year=year
    )

PET_SWITCH_LOCK_HOURS = 24
CLEAN_TRAY_MIN_AVG = 40
CLEAN_TRAY_INTERVAL_HOURS = 12
PET_HOTEL_RETURN_STATE = 50
PET_HOTEL_WEEKS = (1, 2, 3, 4)
VISIBLE_STAT_MIN = 0
VISIBLE_STAT_MAX = 100
INTERNAL_STAT_MIN = -100
INTERNAL_STAT_MAX = 100
NEGLECT_VISIBLE_AVG_THRESHOLD = 10
RECOVERY_VISIBLE_AVG_THRESHOLD = 30
NEGLECT_ITEM_LOSS_EVERY_DAYS = 7
CARE_ACTION_COIN_REWARDS = {
    "feed": (50, 80),
    "play": (60, 100),
    "clean": (65, 110),
}
CARE_ACTION_LEVEL_BONUS_BY_LEVEL = {1: 0, 5: 40, 10: 100, 20: 195}
PET_XP_TREAT_XP = 39
STARTER_CONSUMABLES = ["pet_snack", "toy_ball", "bubble_bath"]

PET_STARTERS = {
    "cat": {"name": "Cat", "emoji": "🐱", "subtitle": "A sleepy barn sweetheart."},
    "dog": {"name": "Dog", "emoji": "🐶", "subtitle": "Always ready for adventure."},
    "duck": {"name": "Duck", "emoji": "🦆", "subtitle": "Waddles through every puddle."},
    "bee": {"name": "Bee", "emoji": "🐝", "subtitle": "Tiny, buzzy, and full of energy."},
    "bunny": {"name": "Bunny", "emoji": "🐰", "subtitle": "Softest helper on the farm."},
}

BOOST_SHOP = {
    "daily_coin_chip": {
        "name": "Daily Coin Chip",
        "price": 40000,
        "description": "Adds a meaningful coin bonus to /daily while active.",
        "bonus_type": "daily_coins_flat",
        "bonus_by_level": {1: 165, 5: 325, 10: 585, 20: 975},
    },
    "daily_xp_chip": {
        "name": "Daily XP Chip",
        "price": 40000,
        "description": "Adds a meaningful XP bonus to /daily while active.",
        "bonus_type": "daily_xp_flat",
        "bonus_by_level": {1: 35, 5: 65, 10: 115, 20: 195},
    },
    "bee_hunt_chip": {
        "name": "Bee Hunt Chip",
        "price": 40000,
        "description": "Adds a % Bee Hunt coin bonus while active.",
        "bonus_type": "bee_hunt_coins_pct",
        "bonus_by_level": {1: 20, 5: 30, 10: 45, 20: 60},
    },
    "message_income_chip": {
        "name": "Message Income Chip",
        "price": 40000,
        "description": "Adds passive message coins while active with a separate daily cap.",
        "bonus_type": "message_income_flat",
        "bonus_by_level": {1: 1, 5: 2, 10: 3, 20: 5},
        "cap_by_level": {1: 165, 5: 295, 10: 490, 20: 715},
    },
}

PETSHOP_ITEMS = {
    "daily_coin_chip": {"name": "Daily Coin Chip", "price": 40000, "type": "boost", "description": "Equippable boost. Adds +165/+325/+585/+975 coins to /daily by pet level."},
    "daily_xp_chip": {"name": "Daily XP Chip", "price": 40000, "type": "boost", "description": "Equippable boost. Adds +35/+65/+115/+195 XP to /daily by pet level."},
    "bee_hunt_chip": {"name": "Bee Hunt Chip", "price": 40000, "type": "boost", "description": "Equippable boost. Adds +20%/+30%/+45%/+60% Bee Hunt coins by pet level."},
    "message_income_chip": {"name": "Message Income Chip", "price": 40000, "type": "boost", "description": "Equippable boost. Adds +1/+2/+3/+5 passive message coins with a 165/295/490/715 daily cap."},
    "pet_snack": {"name": "Pet Snack", "price": 800, "type": "consumable", "description": "One-time use. Gives +25 Hunger. Does not give Pet XP."},
    "toy_ball": {"name": "Toy Ball", "price": 1200, "type": "consumable", "description": "One-time use. Gives +25 Happiness. Does not give Pet XP."},
    "bubble_bath": {"name": "Bubble Bath", "price": 1500, "type": "consumable", "description": "One-time use. Gives +30 Cleanliness. Does not give Pet XP."},
    "pet_xp_treat": {"name": "Pet XP Treat", "price": 5000, "type": "consumable", "description": "One-time use. Gives +39 Pet XP only."},
}

CONSUMABLE_CAPS = {
    "pet_snack": 10,
    "toy_ball": 10,
    "bubble_bath": 10,
    "pet_xp_treat": 3,
}

CONSUMABLE_DAILY_USE_CAPS = {
    "pet_snack": 2,
    "toy_ball": 2,
    "bubble_bath": 2,
    "pet_xp_treat": 1,
}

PET_MOODS = [
    (85, "Excellent"),
    (70, "Happy"),
    (50, "Okay"),
    (30, "Grumpy"),
    (0, "Neglected"),
]

PET_STYLE_SWATCHES = [
    {"key": "strawberry", "label": "Strawberry", "color": "#ff7fa5"},
    {"key": "sunflower", "label": "Sunflower", "color": "#ffc94d"},
    {"key": "mint", "label": "Mint", "color": "#7ee2b8"},
    {"key": "sky", "label": "Sky", "color": "#76b7ff"},
    {"key": "lavender", "label": "Lavender", "color": "#b59cff"},
]


def _pet_now():
    return datetime.utcnow()


def _pet_users_col():
    return get_db("Economy")["Users"]


def _pet_logs_col():
    return get_db("Economy")["pet_logs"]


def _petshop_logs_col():
    return get_db("Economy")["petshop_logs"]


def _pet_level_col():
    return get_db("hayday")["level"]


def _pet_flash_redirect():
    return redirect(url_for("pet_profile"))


def _pet_today_key() -> str:
    return _pet_now().strftime("%Y-%m-%d")


def _pet_clamp_visible(value: int) -> int:
    return max(VISIBLE_STAT_MIN, min(VISIBLE_STAT_MAX, int(value)))


def _pet_clamp_internal(value: int) -> int:
    return max(INTERNAL_STAT_MIN, min(INTERNAL_STAT_MAX, int(value)))


def _pet_visible_stat(value: int) -> int:
    return _pet_clamp_visible(value)


def _pet_xp_needed(level: int) -> int:
    return int(160 * (int(level) ** 1.65))


def _pet_default(pet_type: str, name: str | None = None) -> dict:
    starter = PET_STARTERS[pet_type]
    return {
        "type": pet_type,
        "emoji": starter["emoji"],
        "name": (name or starter["name"])[:24],
        "level": 1,
        "xp": 0,
        "hunger": 100,
        "happiness": 100,
        "cleanliness": 100,
        "adopted_at": _pet_now(),
        "last_fed": None,
        "last_played": None,
        "last_cleaned": None,
        "last_clean_tray_at": None,
        "last_decay_at": _pet_now(),
        "hotel_started_at": None,
        "hotel_until": None,
        "owned_boosts": [],
        "owned_cosmetics": [],
        "owned_consumables": list(STARTER_CONSUMABLES),
        "consumable_daily_uses": {},
        "active_boost_key": None,
        "boost_switch_locked_until": None,
        "neglected_since": None,
        "neglected_penalty_weeks_applied": 0,
        "equipped_cosmetics": [],
        "web_style": {"accent_color": "strawberry"},
        "action_alert_state": {
            "feed": True,
            "play": True,
            "clean": True,
            "clean_tray": True,
        },
    }


def _pet_visible_average_stats(pet: dict) -> int:
    return int((
        _pet_visible_stat(int(pet.get("hunger", 100))) +
        _pet_visible_stat(int(pet.get("happiness", 100))) +
        _pet_visible_stat(int(pet.get("cleanliness", 100)))
    ) / 3)


def _pet_hotel_until(pet: dict) -> datetime | None:
    hotel_until = pet.get("hotel_until")
    return hotel_until if isinstance(hotel_until, datetime) else None


def _pet_is_in_hotel(pet: dict, now: datetime | None = None) -> bool:
    hotel_until = _pet_hotel_until(pet)
    if not hotel_until:
        return False
    return hotel_until > (now or _pet_now())


def _pet_release_hotel(pet: dict, now: datetime | None = None, force: bool = False) -> bool:
    now = now or _pet_now()
    hotel_until = _pet_hotel_until(pet)
    if not hotel_until:
        return False
    if not force and hotel_until > now:
        return False

    pet["hunger"] = PET_HOTEL_RETURN_STATE
    pet["happiness"] = PET_HOTEL_RETURN_STATE
    pet["cleanliness"] = PET_HOTEL_RETURN_STATE
    pet["last_decay_at"] = now
    pet["last_clean_tray_at"] = now
    pet["hotel_started_at"] = None
    pet["hotel_until"] = None
    pet["neglected_since"] = None
    pet["neglected_penalty_weeks_applied"] = 0
    pet["last_pet_care_alert_at"] = None
    _pet_sync_action_alert_state(pet, now)
    return True


def _pet_hotel_status_text(pet: dict) -> str:
    hotel_until = _pet_hotel_until(pet)
    if hotel_until and _pet_is_in_hotel(pet):
        return (
            f"In hotel for {_pet_format_remaining(hotel_until - _pet_now())}. "
            f"Returns at {PET_HOTEL_RETURN_STATE}% condition. "
            "No pet XP, Clean Tray rewards, or boost bonuses while away."
        )
    return "Not currently in the hotel."


def _pet_mood(pet: dict) -> str:
    avg = _pet_visible_average_stats(pet)
    for threshold, label in PET_MOODS:
        if avg >= threshold:
            return label
    return "Neglected"


def _pet_is_neglected(pet: dict) -> bool:
    return _pet_visible_average_stats(pet) <= NEGLECT_VISIBLE_AVG_THRESHOLD


def _pet_is_recovered_from_neglect(pet: dict) -> bool:
    return _pet_visible_average_stats(pet) > RECOVERY_VISIBLE_AVG_THRESHOLD


def _pet_boost_locked(pet: dict) -> bool:
    locked_until = pet.get("boost_switch_locked_until")
    return isinstance(locked_until, datetime) and locked_until > _pet_now()


def _pet_get_boost_value(boost_key: str, level: int) -> int:
    boost = BOOST_SHOP.get(boost_key)
    if not boost:
        return 0

    best = 0
    for req_level in sorted(boost["bonus_by_level"].keys()):
        if int(level) >= req_level:
            best = boost["bonus_by_level"][req_level]
    return best


def _pet_get_boost_cap(boost_key: str, level: int) -> int:
    boost = BOOST_SHOP.get(boost_key)
    if not boost:
        return 0

    best = 0
    for req_level in sorted(boost.get("cap_by_level", {}).keys()):
        if int(level) >= req_level:
            best = boost["cap_by_level"][req_level]
    return best


def _pet_boost_label(boost_key: str, pet_level: int) -> str:
    boost = BOOST_SHOP[boost_key]
    value = _pet_get_boost_value(boost_key, pet_level)
    if boost["bonus_type"] == "daily_coins_flat":
        return f"+{value} Daily coins"
    if boost["bonus_type"] == "daily_xp_flat":
        return f"+{value} Daily XP"
    if boost["bonus_type"] == "bee_hunt_coins_pct":
        return f"+{value}% Bee Hunt coins"
    if boost["bonus_type"] == "message_income_flat":
        cap = _pet_get_boost_cap(boost_key, pet_level)
        return f"+{value} Message coins ({cap}/day cap)"
    return "Unknown boost"


def _pet_effective_multiplier_from_state(pet: dict) -> float:
    if _pet_is_neglected(pet):
        return 0.0

    avg = _pet_visible_average_stats(pet)
    if avg < 30:
        return 0.30
    if avg < 50:
        return 0.60
    if avg < 70:
        return 0.80
    return 1.00


def _pet_care_effectiveness_multiplier(stat_value: int) -> float:
    if stat_value < -50:
        return 0.35
    if stat_value < 0:
        return 0.50
    return 1.00


def _pet_clean_tray_rewards(pet_level: int) -> tuple[int, int]:
    if pet_level >= 20:
        return 1040, 295
    if pet_level >= 10:
        return 650, 195
    if pet_level >= 5:
        return 425, 130
    return 260, 100


def _pet_level_up_reward(pet_level: int) -> tuple[int, int]:
    if pet_level >= 20:
        return 5850, 975
    if pet_level >= 15:
        return 3575, 585
    if pet_level >= 10:
        return 2275, 390
    if pet_level >= 5:
        return 1300, 195
    return 650, 105


def _pet_clean_tray_ready_at(pet: dict) -> datetime | None:
    if _pet_is_in_hotel(pet):
        return None
    last_collected = pet.get("last_clean_tray_at")
    if not isinstance(last_collected, datetime):
        return None
    return last_collected + timedelta(hours=CLEAN_TRAY_INTERVAL_HOURS)


def _pet_scaled_level_bonus(table: dict[int, int], level: int) -> int:
    best = 0
    for req_level in sorted(table.keys()):
        if int(level) >= req_level:
            best = int(table[req_level])
    return best


def _pet_care_action_coin_reward(pet: dict, action: str) -> int:
    if _pet_is_neglected(pet) or _pet_is_in_hotel(pet):
        return 0

    reward_range = CARE_ACTION_COIN_REWARDS.get(action)
    if not reward_range:
        return 0

    base = random.randint(reward_range[0], reward_range[1])
    level_bonus = _pet_scaled_level_bonus(
        CARE_ACTION_LEVEL_BONUS_BY_LEVEL,
        int(pet.get("level", 1)),
    )
    amount = base + level_bonus
    return int(amount * _pet_effective_multiplier_from_state(pet))


def _pet_grant_care_action_coin_reward(user_id: int, pet: dict, action: str) -> int:
    coins = _pet_care_action_coin_reward(pet, action)
    if coins <= 0:
        return 0

    _pet_users_col().update_one({"_id": int(user_id)}, {"$inc": {"coins": int(coins)}})
    return coins


def _pet_care_reward_preview(pet: dict) -> dict:
    if _pet_is_in_hotel(pet):
        return {"rows": [], "note": "Paused while your pet is in the hotel."}
    if _pet_is_neglected(pet):
        return {"rows": [], "note": "Recover your pet above neglect range to earn care coins again."}

    level_bonus = _pet_scaled_level_bonus(
        CARE_ACTION_LEVEL_BONUS_BY_LEVEL,
        int(pet.get("level", 1)),
    )
    multiplier = _pet_effective_multiplier_from_state(pet)
    labels = {
        "feed": "Feed",
        "play": "Play",
        "clean": "Clean",
    }

    rows = []
    for action, label in labels.items():
        low, high = CARE_ACTION_COIN_REWARDS[action]
        low_amt = int((low + level_bonus) * multiplier)
        high_amt = int((high + level_bonus) * multiplier)
        rows.append({"label": label, "amount": f"{low_amt}-{high_amt} coins"})

    note = "Better condition raises these rewards." if multiplier < 1 else None
    return {"rows": rows, "note": note}


def _pet_clean_tray_status_text(pet: dict) -> str:
    coins, server_xp = _pet_clean_tray_rewards(int(pet.get("level", 1)))
    avg = _pet_visible_average_stats(pet)
    ready_at = _pet_clean_tray_ready_at(pet)
    now = _pet_now()

    if _pet_is_in_hotel(pet, now):
        return (
            f"Unavailable while your pet is in the hotel. "
            f"Returns in {_pet_format_remaining(_pet_hotel_until(pet) - now)}."
        )

    lines = [
        f"Claim: +{coins} coins and +{server_xp} server XP",
        f"Requirement: average condition must stay {CLEAN_TRAY_MIN_AVG}%+",
    ]

    last_collected = pet.get("last_clean_tray_at")
    if isinstance(last_collected, datetime):
        lines.append(f"Last collected: {last_collected.strftime('%Y-%m-%d %H:%M UTC')}")

    if avg < CLEAN_TRAY_MIN_AVG:
        lines.append(f"Status: Paused right now because your pet average is only {avg}%.")
    elif ready_at is None or ready_at <= now:
        lines.append("Status: Ready to collect now.")
    else:
        lines.append(f"Status: Ready in {_pet_format_remaining(ready_at - now)}.")

    return "\n".join(lines)


def _pet_level_up_reward_text(pet: dict) -> str:
    pet_level = int(pet.get("level", 1))
    coins, server_xp = _pet_level_up_reward(min(pet_level + 1, 20))
    return (
        f"Next reward: +{coins} coins and +{server_xp} server XP\n"
        "Rewards are granted automatically whenever your pet levels up."
    )


def _pet_add_server_xp(user_id: int, xp_amount: int):
    if int(xp_amount) <= 0:
        return
    _pet_level_col().update_one(
        {"_id": str(user_id)},
        {"$inc": {"xp": int(xp_amount)}},
        upsert=True,
    )


def _pet_grant_level_up_rewards(user_id: int, pet: dict, leveled: list[int]) -> tuple[int, int]:
    total_coins = 0
    total_server_xp = 0

    for level in leveled:
        coins, server_xp = _pet_level_up_reward(level)
        total_coins += coins
        total_server_xp += server_xp

    if total_coins > 0:
        _pet_users_col().update_one({"_id": int(user_id)}, {"$inc": {"coins": int(total_coins)}})
    if total_server_xp > 0:
        _pet_add_server_xp(user_id, total_server_xp)

    return total_coins, total_server_xp


def _pet_normalize_neglect_state(pet: dict):
    now = _pet_now()
    if _pet_is_neglected(pet):
        if not isinstance(pet.get("neglected_since"), datetime):
            pet["neglected_since"] = now
    elif pet.get("neglected_since") and _pet_is_recovered_from_neglect(pet):
        pet["neglected_since"] = None
        pet["neglected_penalty_weeks_applied"] = 0


def _pet_random_removable_item(pet: dict):
    pool = []

    for item in pet.get("owned_consumables", []):
        pool.append(("owned_consumables", item))
    for item in pet.get("owned_cosmetics", []):
        pool.append(("owned_cosmetics", item))

    active_boost = pet.get("active_boost_key")
    for item in pet.get("owned_boosts", []):
        if item != active_boost:
            pool.append(("owned_boosts", item))

    if not pool:
        return None
    return random.choice(pool)


def _pet_remove_owned_item(pet: dict, bucket: str, item: str):
    values = list(pet.get(bucket, []))
    if item in values:
        values.remove(item)
        pet[bucket] = values
    if bucket == "owned_cosmetics":
        equipped = [key for key in pet.get("equipped_cosmetics", []) if key != item]
        pet["equipped_cosmetics"] = equipped


def _pet_get_consumable_uses_today(pet: dict, item: str) -> int:
    daily_uses = pet.get("consumable_daily_uses", {})
    today_key = _pet_today_key()
    return int(daily_uses.get(today_key, {}).get(item, 0))


def _pet_increment_consumable_use(pet: dict, item: str):
    today_key = _pet_today_key()
    daily_uses = dict(pet.get("consumable_daily_uses", {}))
    today_bucket = dict(daily_uses.get(today_key, {}))
    today_bucket[item] = int(today_bucket.get(item, 0)) + 1
    pet["consumable_daily_uses"] = {today_key: today_bucket}


def _pet_apply_xp(pet: dict, gained_xp: int) -> list[int]:
    if _pet_is_neglected(pet) or _pet_is_in_hotel(pet):
        return []

    pet["xp"] = int(pet.get("xp", 0)) + int(gained_xp)
    pet["level"] = int(pet.get("level", 1))
    leveled = []

    while pet["xp"] >= _pet_xp_needed(pet["level"]):
        pet["xp"] -= _pet_xp_needed(pet["level"])
        pet["level"] += 1
        leveled.append(pet["level"])

    return leveled


def _pet_sync_decay(pet: dict) -> tuple[dict, bool]:
    now = _pet_now()
    changed = False

    if _pet_is_in_hotel(pet, now):
        return pet, changed

    last_decay_at = pet.get("last_decay_at")
    if not isinstance(last_decay_at, datetime):
        pet["last_decay_at"] = now
        return pet, True

    hours_passed = int((now - last_decay_at).total_seconds() // 3600)
    if hours_passed < 1:
        return pet, changed

    neglected_before = _pet_is_neglected(pet)
    if neglected_before:
        hunger_decay = 5 * hours_passed
        happiness_decay = 4 * hours_passed
        cleanliness_decay = 4 * hours_passed
    else:
        hunger_decay = 3 * hours_passed
        happiness_decay = 2 * hours_passed
        cleanliness_decay = 2 * hours_passed

    pet["hunger"] = _pet_clamp_internal(int(pet.get("hunger", 100)) - hunger_decay)
    pet["happiness"] = _pet_clamp_internal(int(pet.get("happiness", 100)) - happiness_decay)
    pet["cleanliness"] = _pet_clamp_internal(int(pet.get("cleanliness", 100)) - cleanliness_decay)
    pet["last_decay_at"] = now
    changed = True

    _pet_normalize_neglect_state(pet)

    neglected_since = pet.get("neglected_since")
    if isinstance(neglected_since, datetime):
        neglected_days = (now - neglected_since).days
        weeks_due = neglected_days // NEGLECT_ITEM_LOSS_EVERY_DAYS
        already_applied = int(pet.get("neglected_penalty_weeks_applied", 0))

        while weeks_due > already_applied:
            removable = _pet_random_removable_item(pet)
            if removable:
                bucket, item = removable
                _pet_remove_owned_item(pet, bucket, item)
            already_applied += 1
            pet["neglected_penalty_weeks_applied"] = already_applied
            changed = True

    return pet, changed


def _pet_log(user_id: int, action: str, extra: dict | None = None):
    payload = {"user_id": user_id, "action": action, "ts": _pet_now()}
    if extra:
        payload.update(extra)
    try:
        _pet_logs_col().insert_one(payload)
    except Exception:
        app.logger.exception("Failed to write pet log")


def _pet_log_purchase(user_id: int, item_key: str, price: int):
    try:
        _petshop_logs_col().insert_one({
            "user_id": user_id,
            "item": item_key,
            "price": price,
            "ts": _pet_now(),
        })
    except Exception:
        app.logger.exception("Failed to write pet shop log")


def _pet_load_user(user_id: int):
    user_doc = _pet_users_col().find_one({"_id": int(user_id)}) or {"_id": int(user_id), "coins": 0}
    pet = user_doc.get("pet")
    if pet:
        changed = False
        if not isinstance(pet.get("equipped_cosmetics"), list):
            pet["equipped_cosmetics"] = []
            changed = True
        if "last_clean_tray_at" not in pet:
            pet["last_clean_tray_at"] = None
            changed = True
        if "hotel_started_at" not in pet:
            pet["hotel_started_at"] = None
            changed = True
        if "hotel_until" not in pet:
            pet["hotel_until"] = None
            changed = True
        if not isinstance(pet.get("action_alert_state"), dict):
            _pet_sync_action_alert_state(pet)
            changed = True
        if not isinstance(pet.get("web_style"), dict):
            pet["web_style"] = {"accent_color": "strawberry"}
            changed = True
        elif pet["web_style"].get("accent_color") not in {sw["key"] for sw in PET_STYLE_SWATCHES}:
            pet["web_style"]["accent_color"] = "strawberry"
            changed = True
        if pet.get("owned_cosmetics"):
            pet["owned_cosmetics"] = []
            changed = True
        if pet.get("equipped_cosmetics"):
            pet["equipped_cosmetics"] = []
            changed = True
        if _pet_release_hotel(pet):
            changed = True
            _pet_log(int(user_id), "pet_hotel_return", {"returned_at": _pet_now()})
        pet, decay_changed = _pet_sync_decay(pet)
        changed = changed or decay_changed
        if changed:
            _pet_users_col().update_one({"_id": int(user_id)}, {"$set": {"pet": pet}}, upsert=True)
        user_doc["pet"] = pet
    return user_doc


def _pet_save(user_id: int, pet: dict):
    _pet_users_col().update_one({"_id": int(user_id)}, {"$set": {"pet": pet}}, upsert=True)


def _pet_inventory_counts(items: list[str]):
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


def _pet_format_remaining(delta: timedelta) -> str:
    total_seconds = max(0, int(delta.total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _pet_care_actions_state(pet: dict):
    now = _pet_now()
    configs = {
        "feed": {"field": "last_fed", "hours": 4, "title": "Feed", "subtitle": "Every 4 hours"},
        "play": {"field": "last_played", "hours": 3, "title": "Play", "subtitle": "Every 3 hours"},
        "clean": {"field": "last_cleaned", "hours": 6, "title": "Clean", "subtitle": "Every 6 hours"},
    }

    states = {}
    for key, config in configs.items():
        last_at = pet.get(config["field"])
        ready_at = None
        remaining = None
        is_ready = True
        if isinstance(last_at, datetime):
            ready_at = last_at + timedelta(hours=config["hours"])
            remaining_delta = ready_at - now
            if remaining_delta.total_seconds() > 0:
                is_ready = False
                remaining = _pet_format_remaining(remaining_delta)

        states[key] = {
            "title": config["title"],
            "subtitle": config["subtitle"],
            "is_ready": is_ready,
            "remaining": remaining,
            "ready_at": ready_at,
        }

    return states


def _pet_action_ready_state(pet: dict, now: datetime | None = None) -> dict[str, bool]:
    now = now or _pet_now()

    if _pet_is_in_hotel(pet, now):
        return {
            "feed": False,
            "play": False,
            "clean": False,
            "clean_tray": False,
        }

    last_fed = pet.get("last_fed")
    last_played = pet.get("last_played")
    last_cleaned = pet.get("last_cleaned")
    clean_tray_ready_at = _pet_clean_tray_ready_at(pet)
    average_condition = _pet_visible_average_stats(pet)

    return {
        "feed": not isinstance(last_fed, datetime) or (now - last_fed) >= timedelta(hours=4),
        "play": not isinstance(last_played, datetime) or (now - last_played) >= timedelta(hours=3),
        "clean": not isinstance(last_cleaned, datetime) or (now - last_cleaned) >= timedelta(hours=6),
        "clean_tray": average_condition >= CLEAN_TRAY_MIN_AVG and (clean_tray_ready_at is None or clean_tray_ready_at <= now),
    }


def _pet_sync_action_alert_state(pet: dict, now: datetime | None = None):
    pet["action_alert_state"] = _pet_action_ready_state(pet, now)


def _pet_context_from_doc(user_doc: dict):
    pet = user_doc.get("pet")
    coins = int(user_doc.get("coins", 0))
    context = {
        "pet": pet,
        "coins": coins,
        "pet_items": PETSHOP_ITEMS,
        "pet_starters": PET_STARTERS,
        "shop_categories": ("boost", "consumable"),
        "style_swatches": PET_STYLE_SWATCHES,
        "owned_boost_items": [],
        "owned_consumable_items": [],
        "active_boost_name": None,
        "active_boost_label": None,
        "mood": None,
        "visible_hunger": 0,
        "visible_happiness": 0,
        "visible_cleanliness": 0,
        "visible_average_condition": 0,
        "consumable_counts": {},
        "pet_xp_needed": None,
        "care_actions": {},
        "pet_mood_slug": "happy",
        "hotel_status_text": None,
        "hotel_until": None,
        "hotel_started_at": None,
        "hotel_is_active": False,
        "hotel_time_left": None,
        "hotel_weeks": PET_HOTEL_WEEKS,
        "hotel_return_state": PET_HOTEL_RETURN_STATE,
        "clean_tray_status_text": None,
        "clean_tray_rewards": None,
        "clean_tray_ready_at": None,
        "clean_tray_is_ready": False,
        "clean_tray_requirement": CLEAN_TRAY_MIN_AVG,
        "clean_tray_status_label": None,
        "next_level_reward_text": None,
        "next_level_reward": None,
        "care_reward_preview": {"rows": [], "note": None},
    }

    if not pet:
        return context

    context["mood"] = _pet_mood(pet)
    context["pet_mood_slug"] = str(context["mood"]).lower()
    context["pet_xp_needed"] = _pet_xp_needed(int(pet.get("level", 1)))
    context["visible_hunger"] = _pet_visible_stat(int(pet.get("hunger", 100)))
    context["visible_happiness"] = _pet_visible_stat(int(pet.get("happiness", 100)))
    context["visible_cleanliness"] = _pet_visible_stat(int(pet.get("cleanliness", 100)))
    context["visible_average_condition"] = _pet_visible_average_stats(pet)
    context["consumable_counts"] = _pet_inventory_counts(pet.get("owned_consumables", []))
    context["care_actions"] = _pet_care_actions_state(pet)
    clean_tray_coins, clean_tray_server_xp = _pet_clean_tray_rewards(int(pet.get("level", 1)))
    clean_tray_ready_at = _pet_clean_tray_ready_at(pet)
    hotel_until = _pet_hotel_until(pet)
    context["hotel_until"] = hotel_until
    context["hotel_started_at"] = pet.get("hotel_started_at")
    context["hotel_is_active"] = _pet_is_in_hotel(pet)
    context["hotel_time_left"] = _pet_format_remaining(hotel_until - _pet_now()) if context["hotel_is_active"] and hotel_until else None
    context["hotel_status_text"] = _pet_hotel_status_text(pet)
    context["clean_tray_status_text"] = _pet_clean_tray_status_text(pet)
    context["care_reward_preview"] = _pet_care_reward_preview(pet)
    context["clean_tray_rewards"] = {"coins": clean_tray_coins, "server_xp": clean_tray_server_xp}
    context["clean_tray_ready_at"] = clean_tray_ready_at
    context["clean_tray_is_ready"] = (
        not context["hotel_is_active"] and
        _pet_visible_average_stats(pet) >= CLEAN_TRAY_MIN_AVG and
        (clean_tray_ready_at is None or clean_tray_ready_at <= _pet_now())
    )
    if context["hotel_is_active"]:
        context["clean_tray_status_label"] = f"Hotel stay - {context['hotel_time_left']} left"
    elif _pet_visible_average_stats(pet) < CLEAN_TRAY_MIN_AVG:
        context["clean_tray_status_label"] = f"Paused below {CLEAN_TRAY_MIN_AVG}%"
    elif clean_tray_ready_at is None or clean_tray_ready_at <= _pet_now():
        context["clean_tray_status_label"] = "Ready to collect"
    else:
        context["clean_tray_status_label"] = f"Ready in {_pet_format_remaining(clean_tray_ready_at - _pet_now())}"
    context["next_level_reward_text"] = _pet_level_up_reward_text(pet)
    next_reward_coins, next_reward_server_xp = _pet_level_up_reward(min(int(pet.get("level", 1)) + 1, 20))
    context["next_level_reward"] = {"coins": next_reward_coins, "server_xp": next_reward_server_xp}

    owned_boost_items = []
    for key in pet.get("owned_boosts", []):
        if key not in BOOST_SHOP:
            continue
        item = dict(BOOST_SHOP[key])
        item["key"] = key
        item["label"] = _pet_boost_label(key, int(pet.get("level", 1)))
        item["active"] = pet.get("active_boost_key") == key
        owned_boost_items.append(item)
    context["owned_boost_items"] = owned_boost_items

    owned_consumable_items = []
    for key, amount in context["consumable_counts"].items():
        item = dict(PETSHOP_ITEMS.get(key, {}))
        item["key"] = key
        item["count"] = amount
        owned_consumable_items.append(item)
    context["owned_consumable_items"] = owned_consumable_items

    active_boost = pet.get("active_boost_key")
    if active_boost in BOOST_SHOP:
        context["active_boost_name"] = BOOST_SHOP[active_boost]["name"]
        context["active_boost_label"] = _pet_boost_label(active_boost, int(pet.get("level", 1)))

    return context


def _pet_require_login():
    if "discord_id" not in session:
        return redirect(url_for("login", next=url_for("pet_profile")))
    return None


@app.route("/profile/pet")
def pet_profile():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    user_doc = _pet_load_user(discord_id)
    fallback = get_db("Website")["usernames"].find_one({"_id": str(discord_id)}) or {}
    pet_context = _pet_context_from_doc(user_doc)

    return render_template(
        "pet_profile.html",
        discord_id=str(discord_id),
        display_name=fallback.get("display_name", fallback.get("username", "Unknown")),
        avatar_url=fallback.get("avatar", "https://cdn.discordapp.com/embed/avatars/0.png"),
        **pet_context,
    )


@app.post("/profile/pet/adopt")
def pet_adopt():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    pet_type = (request.form.get("pet_type") or "").strip().lower()
    custom_name = (request.form.get("pet_name") or "").strip()[:24]

    if pet_type not in PET_STARTERS:
        flash("❌ Invalid pet choice.", "error")
        return _pet_flash_redirect()

    user_doc = _pet_load_user(discord_id)
    if user_doc.get("pet"):
        flash("❌ You already adopted a pet.", "error")
        return _pet_flash_redirect()

    pet = _pet_default(pet_type, custom_name or None)
    _pet_save(discord_id, pet)
    _pet_log(discord_id, "adopt", {"pet_name": pet["name"], "pet_type": pet["type"]})
    flash(
        f"✅ You adopted {pet['emoji']} {pet['name']}. Starter kit added: Pet Snack, Toy Ball, and Bubble Bath.",
        "success",
    )
    return _pet_flash_redirect()


@app.post("/profile/pet/rename")
def pet_rename():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    new_name = (request.form.get("pet_name") or "").strip()[:24]
    if not new_name:
        flash("❌ Please give your pet a valid name.", "error")
        return _pet_flash_redirect()

    user_doc = _pet_load_user(discord_id)
    pet = user_doc.get("pet")
    if not pet:
        flash("❌ Adopt a pet first.", "error")
        return _pet_flash_redirect()

    old_name = pet.get("name", "Pet")
    pet["name"] = new_name
    _pet_save(discord_id, pet)
    _pet_log(discord_id, "rename", {"old_name": old_name, "new_name": new_name})
    flash(f"✅ Renamed {old_name} to {new_name}.", "success")
    return _pet_flash_redirect()


@app.post("/profile/pet/hotel")
def pet_hotel():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    user_doc = _pet_load_user(discord_id)
    pet = user_doc.get("pet")
    if not pet:
        flash("❌ Adopt a pet first.", "error")
        return _pet_flash_redirect()

    now = _pet_now()
    if _pet_is_in_hotel(pet, now):
        flash(f"❌ {pet['name']} is already in the hotel for {_pet_format_remaining(_pet_hotel_until(pet) - now)}.", "error")
        return _pet_flash_redirect()

    try:
        weeks = int(request.form.get("hotel_weeks", "0"))
    except (TypeError, ValueError):
        weeks = 0
    if weeks not in PET_HOTEL_WEEKS:
        flash("❌ Choose a valid hotel stay.", "error")
        return _pet_flash_redirect()

    confirm_value = (request.form.get("hotel_confirm") or "").strip().lower()
    if confirm_value != "true":
        flash("❌ Please confirm the hotel warning before sending your pet away.", "error")
        return _pet_flash_redirect()

    hotel_until = now + timedelta(weeks=weeks)
    pet["hotel_started_at"] = now
    pet["hotel_until"] = hotel_until
    _pet_save(discord_id, pet)
    _pet_log(discord_id, "pet_hotel_checkin", {"weeks": weeks, "hotel_until": hotel_until})
    flash(
        f"✅ {pet['name']} is checked into the Pet Hotel for {weeks} "
        f"{'week' if weeks == 1 else 'weeks'}. Returns in {_pet_format_remaining(hotel_until - now)} at {PET_HOTEL_RETURN_STATE}% condition.",
        "success",
    )
    return _pet_flash_redirect()


@app.post("/profile/pet/care")
def pet_care():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    action = (request.form.get("action") or "").strip().lower()
    user_doc = _pet_load_user(discord_id)
    pet = user_doc.get("pet")
    if not pet:
        flash("❌ Adopt a pet first.", "error")
        return _pet_flash_redirect()

    if _pet_is_in_hotel(pet):
        hotel_until = _pet_hotel_until(pet)
        flash(f"❌ {pet['name']} is in the hotel for {_pet_format_remaining(hotel_until - _pet_now())}. Care actions are unavailable while away.", "error")
        return _pet_flash_redirect()

    now = _pet_now()
    configs = {
        "feed": {"field": "last_fed", "hours": 4, "stat": "hunger", "gain": (20, 30), "min_gain": 8, "xp": (8, 14), "verb": "fed", "label": "Hunger"},
        "play": {"field": "last_played", "hours": 3, "stat": "happiness", "gain": (20, 30), "min_gain": 8, "xp": (10, 16), "verb": "played with", "label": "Happiness"},
        "clean": {"field": "last_cleaned", "hours": 6, "stat": "cleanliness", "gain": (25, 35), "min_gain": 10, "xp": (6, 12), "verb": "cleaned", "label": "Cleanliness"},
    }
    config = configs.get(action)
    if not config:
        flash("❌ Unknown care action.", "error")
        return _pet_flash_redirect()

    last_at = pet.get(config["field"])
    if isinstance(last_at, datetime) and (now - last_at) < timedelta(hours=config["hours"]):
        available_at = (last_at + timedelta(hours=config["hours"])).strftime("%H:%M UTC")
        flash(f"❌ {pet['name']} is not ready yet. Try again after {available_at}.", "error")
        return _pet_flash_redirect()

    base_gain = random.randint(*config["gain"])
    gain = int(base_gain * _pet_care_effectiveness_multiplier(int(pet.get(config["stat"], 100))))
    gain = max(config["min_gain"], gain)
    xp_gain = random.randint(*config["xp"])

    pet[config["stat"]] = _pet_clamp_internal(int(pet.get(config["stat"], 100)) + gain)
    pet[config["field"]] = now
    _pet_normalize_neglect_state(pet)
    _pet_sync_action_alert_state(pet, now)
    leveled = _pet_apply_xp(pet, xp_gain)
    reward_coins, reward_server_xp = _pet_grant_level_up_rewards(discord_id, pet, leveled)
    care_coins = _pet_grant_care_action_coin_reward(discord_id, pet, action)
    _pet_save(discord_id, pet)
    _pet_log(
        discord_id,
        action,
        {
            "gain": gain,
            "xp": xp_gain,
            "care_reward_coins": care_coins,
            "level_rewards_coins": reward_coins,
            "level_rewards_server_xp": reward_server_xp,
        },
    )

    level_line = ""
    if leveled:
        level_line = f" Your pet reached level {pet['level']}! +{reward_coins} coins and +{reward_server_xp} server XP."
    care_reward_line = f" +{care_coins} coins." if care_coins > 0 else ""
    recover_note = " It is still recovering from neglect." if _pet_is_neglected(pet) else ""
    message = (
        f"You {config['verb']} {pet['name']}. +{gain} {config['label']}. "
        f"+{0 if _pet_is_neglected(pet) else xp_gain} Pet XP.{care_reward_line}{level_line}{recover_note}"
    )
    flash(message, "success")
    return _pet_flash_redirect()


@app.post("/profile/pet/clean-tray")
def pet_clean_tray():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    user_doc = _pet_load_user(discord_id)
    pet = user_doc.get("pet")
    if not pet:
        flash("❌ Adopt a pet first.", "error")
        return _pet_flash_redirect()

    if _pet_is_in_hotel(pet):
        hotel_until = _pet_hotel_until(pet)
        flash(f"❌ Clean Tray is unavailable while {pet['name']} is in the hotel for {_pet_format_remaining(hotel_until - _pet_now())}.", "error")
        return _pet_flash_redirect()

    avg = _pet_visible_average_stats(pet)
    if avg < CLEAN_TRAY_MIN_AVG:
        flash(
            f"❌ Clean Tray is paused until {pet.get('name', 'your pet')} is back above {CLEAN_TRAY_MIN_AVG}% average condition. It is currently {avg}%.",
            "error",
        )
        return _pet_flash_redirect()

    now = _pet_now()
    ready_at = _pet_clean_tray_ready_at(pet)
    if isinstance(ready_at, datetime) and ready_at > now:
        flash(f"❌ Clean Tray is not ready yet. Try again in {_pet_format_remaining(ready_at - now)}.", "error")
        return _pet_flash_redirect()

    coins, server_xp = _pet_clean_tray_rewards(int(pet.get("level", 1)))
    _pet_users_col().update_one({"_id": discord_id}, {"$inc": {"coins": int(coins)}})
    _pet_add_server_xp(discord_id, server_xp)

    pet["last_clean_tray_at"] = now
    _pet_sync_action_alert_state(pet, now)
    _pet_save(discord_id, pet)
    _pet_log(discord_id, "clean_tray_collect", {"coins": coins, "server_xp": server_xp, "pet_level": int(pet.get("level", 1))})

    flash(f"✅ You collected Clean Tray from {pet['name']}. +{coins} coins and +{server_xp} server XP.", "success")
    return _pet_flash_redirect()


@app.post("/profile/pet/item")
def pet_use_item():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    item = (request.form.get("item_key") or "").strip().lower()
    user_doc = _pet_load_user(discord_id)
    pet = user_doc.get("pet")
    if not pet:
        flash("❌ Adopt a pet first.", "error")
        return _pet_flash_redirect()

    if _pet_is_in_hotel(pet):
        hotel_until = _pet_hotel_until(pet)
        flash(f"❌ {pet['name']} is in the hotel for {_pet_format_remaining(hotel_until - _pet_now())}. Consumables cannot be used while away.", "error")
        return _pet_flash_redirect()

    owned = list(pet.get("owned_consumables", []))
    if item not in owned:
        flash("❌ You do not own that consumable.", "error")
        return _pet_flash_redirect()

    daily_cap = CONSUMABLE_DAILY_USE_CAPS.get(item)
    if daily_cap is not None and _pet_get_consumable_uses_today(pet, item) >= daily_cap:
        flash(f"❌ You already used {PETSHOP_ITEMS[item]['name']} the max amount today.", "error")
        return _pet_flash_redirect()

    message = None
    if item == "pet_snack":
        pet["hunger"] = _pet_clamp_internal(int(pet.get("hunger", 100)) + 25)
        message = f"✅ {pet['name']} loved the Pet Snack. +25 Hunger."
    elif item == "toy_ball":
        pet["happiness"] = _pet_clamp_internal(int(pet.get("happiness", 100)) + 25)
        message = f"✅ {pet['name']} chased the Toy Ball. +25 Happiness."
    elif item == "bubble_bath":
        pet["cleanliness"] = _pet_clamp_internal(int(pet.get("cleanliness", 100)) + 30)
        message = f"✅ {pet['name']} feels fresh after Bubble Bath. +30 Cleanliness."
    elif item == "pet_xp_treat":
        xp_gain = PET_XP_TREAT_XP
        leveled = _pet_apply_xp(pet, xp_gain)
        reward_coins, reward_server_xp = _pet_grant_level_up_rewards(discord_id, pet, leveled)
        message = f"✅ {pet['name']} enjoyed a Pet XP Treat. +{0 if _pet_is_neglected(pet) else xp_gain} Pet XP."
        if leveled:
            message += f" Your pet reached level {pet['level']}! +{reward_coins} coins and +{reward_server_xp} server XP."
    else:
        flash("❌ That item is not ready on web yet.", "error")
        return _pet_flash_redirect()

    owned.remove(item)
    pet["owned_consumables"] = owned
    _pet_increment_consumable_use(pet, item)
    _pet_normalize_neglect_state(pet)
    _pet_sync_action_alert_state(pet)
    _pet_save(discord_id, pet)
    _pet_log(discord_id, "use_item", {"item": item})
    flash(message, "success")
    return _pet_flash_redirect()


@app.post("/profile/pet/boost")
def pet_boost():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    action = (request.form.get("action") or "").strip().lower()
    item_key = (request.form.get("item_key") or "").strip().lower()
    user_doc = _pet_load_user(discord_id)
    pet = user_doc.get("pet")
    if not pet:
        flash("❌ Adopt a pet first.", "error")
        return _pet_flash_redirect()

    if action == "unequip":
        if not pet.get("active_boost_key"):
            flash("❌ No active boost equipped.", "error")
            return _pet_flash_redirect()
        old_key = pet["active_boost_key"]
        pet["active_boost_key"] = None
        pet["boost_switch_locked_until"] = None
        _pet_save(discord_id, pet)
        _pet_log(discord_id, "unequip_boost", {"old_boost_key": old_key})
        flash(f"✅ Unequipped {BOOST_SHOP.get(old_key, {}).get('name', 'boost')}.", "success")
        return _pet_flash_redirect()

    if item_key not in pet.get("owned_boosts", []):
        flash("❌ You do not own that boost.", "error")
        return _pet_flash_redirect()
    if pet.get("active_boost_key") == item_key:
        flash("❌ That boost is already active.", "error")
        return _pet_flash_redirect()
    if _pet_boost_locked(pet):
        flash("❌ Your boost slot is still locked.", "error")
        return _pet_flash_redirect()

    pet["active_boost_key"] = item_key
    pet["boost_switch_locked_until"] = _pet_now() + timedelta(hours=PET_SWITCH_LOCK_HOURS)
    _pet_save(discord_id, pet)
    _pet_log(discord_id, "equip_boost", {"boost_key": item_key})
    flash(f"✅ Equipped {BOOST_SHOP[item_key]['name']}. Locked for {PET_SWITCH_LOCK_HOURS} hours.", "success")
    return _pet_flash_redirect()


@app.post("/profile/pet/style")
def pet_style():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    accent = (request.form.get("accent_color") or "").strip().lower()
    valid_keys = {swatch["key"] for swatch in PET_STYLE_SWATCHES}
    if accent not in valid_keys:
        flash("❌ Invalid style color.", "error")
        return _pet_flash_redirect()

    user_doc = _pet_load_user(discord_id)
    pet = user_doc.get("pet")
    if not pet:
        flash("❌ Adopt a pet first.", "error")
        return _pet_flash_redirect()

    web_style = dict(pet.get("web_style", {}))
    web_style["accent_color"] = accent
    pet["web_style"] = web_style
    _pet_save(discord_id, pet)
    flash("✅ Updated your pet style.", "success")
    return _pet_flash_redirect()


@app.post("/profile/pet/change")
def pet_change():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    new_type = (request.form.get("pet_type") or "").strip().lower()
    if new_type not in PET_STARTERS:
        flash("❌ Invalid pet choice.", "error")
        return _pet_flash_redirect()

    user_doc = _pet_load_user(discord_id)
    pet = user_doc.get("pet")
    if not pet:
        flash("❌ Adopt a pet first.", "error")
        return _pet_flash_redirect()

    old_type = pet.get("type")
    if old_type == new_type:
        flash(f"❌ {pet.get('name', 'Your pet')} is already a {new_type}.", "error")
        return _pet_flash_redirect()

    starter = PET_STARTERS[new_type]
    pet["type"] = new_type
    pet["emoji"] = starter["emoji"]

    _pet_save(discord_id, pet)
    _pet_log(discord_id, "change_pet_type", {"old_type": old_type, "new_type": new_type})
    flash(f"✅ Your pet is now a {starter['name']}. Progress and items were kept.", "success")
    return _pet_flash_redirect()


@app.post("/profile/pet/shop")
def pet_shop_buy():
    login_redirect = _pet_require_login()
    if login_redirect:
        return login_redirect

    discord_id = int(session["discord_id"])
    item_key = (request.form.get("item_key") or "").strip().lower()
    if item_key not in PETSHOP_ITEMS:
        flash("Invalid pet shop item.", "error")
        return _pet_flash_redirect()

    user_doc = _pet_load_user(discord_id)
    pet = user_doc.get("pet")
    if not pet:
        flash("Adopt a pet first.", "error")
        return _pet_flash_redirect()

    item_data = PETSHOP_ITEMS[item_key]
    item_type = item_data["type"]
    price = int(item_data["price"])
    purchase_query = {
        "_id": discord_id,
        "pet": {"$exists": True},
        "coins": {"$gte": price},
    }
    purchase_update = {"$inc": {"coins": -price}}

    if item_type == "boost":
        purchase_query["pet.owned_boosts"] = {"$ne": item_key}
        purchase_update["$addToSet"] = {"pet.owned_boosts": item_key}
    elif item_type == "consumable":
        max_allowed = CONSUMABLE_CAPS.get(item_key, 10)
        purchase_query["$expr"] = {
            "$lt": [
                {
                    "$size": {
                        "$filter": {
                            "input": {"$ifNull": ["$pet.owned_consumables", []]},
                            "as": "owned_item",
                            "cond": {"$eq": ["$$owned_item", item_key]},
                        }
                    }
                },
                max_allowed,
            ]
        }
        purchase_update["$push"] = {"pet.owned_consumables": item_key}

    result = _pet_users_col().update_one(purchase_query, purchase_update, upsert=False)
    if result.modified_count != 1:
        latest_user_doc = _pet_load_user(discord_id)
        latest_pet = latest_user_doc.get("pet")
        if not latest_pet:
            flash("Adopt a pet first.", "error")
            return _pet_flash_redirect()
        if item_type == "boost" and item_key in latest_pet.get("owned_boosts", []):
            flash("You already own that boost.", "error")
            return _pet_flash_redirect()
        if item_type == "consumable":
            current_amount = list(latest_pet.get("owned_consumables", [])).count(item_key)
            max_allowed = CONSUMABLE_CAPS.get(item_key, 10)
            if current_amount >= max_allowed:
                flash(f"You already hold the max amount of {item_data['name']}.", "error")
                return _pet_flash_redirect()
        if int(latest_user_doc.get("coins", 0)) < price:
            flash("You do not have enough coins.", "error")
            return _pet_flash_redirect()
        flash("Purchase could not be completed. Please try again.", "error")
        return _pet_flash_redirect()

    _pet_log_purchase(discord_id, item_key, price)
    flash(f"Bought {item_data['name']} for {price:,} coins.", "success")
    return _pet_flash_redirect()


@app.route("/profile")
def profile():
    if "discord_id" not in session:
        return redirect(url_for("login", next=request.path))

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
    highest_role = sorted_roles[0] if sorted_roles else None

    client = get_db()
    level_col = client["hayday"]["level"]
    level_doc = level_col.find_one({"_id": discord_id})

    users_collection = client["Website"]["users"]
    usernames_collection = client["Website"]["usernames"]

    user = users_collection.find_one({"_id": discord_id}) or {}
    fallback = usernames_collection.find_one({"_id": discord_id}) or {}

    display_name = fallback.get("display_name", "Unknown")

    # Always fetch avatar from synced collection
    avatar_url = fallback.get("avatar", f"https://cdn.discordapp.com/embed/avatars/0.png")

    eco_user = client["Economy"]["Users"].find_one({"_id": int(discord_id)}) or {}
    coins = eco_user.get("coins", 0)
    streak = eco_user.get("streak", 0)

    mention_doc = client["Mentions"]["Amount"].find_one({"id": int(discord_id)})
    mention_count = mention_doc.get("Mentions", 0) if mention_doc else 0

    friend_doc = client["Website"]["FriendRequests"].find_one({"_id": discord_id}) or {}
    friend_count = len(friend_doc.get("friends", []))

    user_roles = user.get("roles", fallback.get("roles", []))
    staff_badges = [STAFF_ROLES[int(rid)] for rid in user_roles if int(rid) in STAFF_ROLES]

    level = xp = message_count = 0
    boost_time_left = None
    rank = "?"
    progress_percent = 0
    current_xp_formatted = required_xp_formatted = "0"

    if level_doc:
        level = level_doc.get("level", 1)
        xp = level_doc.get("xp", 0)
        message_count = level_doc.get("message_count", 0)

        boost_until = level_doc.get("xp_boost_until")
        if boost_until:
            now = datetime.now(timezone.utc)
            if not isinstance(boost_until, datetime):
                boost_until = boost_until.to_datetime()
            if boost_until.tzinfo is None:
                boost_until = boost_until.replace(tzinfo=timezone.utc)

            if boost_until > now:
                boost_time_left = str(boost_until - now).split(".")[0]

        def calc_required_xp(lvl):
            return 100 * (lvl ** 2) + 100 * lvl + 100

        prev_xp = calc_required_xp(level - 1) if level > 1 else 0
        next_xp = calc_required_xp(level)
        current_xp = xp - prev_xp
        required_xp = next_xp - prev_xp
        progress_percent = int((current_xp / required_xp) * 100)

        current_xp_formatted = f"{current_xp:,}"
        required_xp_formatted = f"{required_xp:,}"
        rank = level_col.count_documents({"xp": {"$gt": xp}}) + 1

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
        display_name=display_name,
        discord_id=discord_id,
        avatar_url=avatar_url,
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
        friend_count=friend_count,
        pet=eco_user.get("pet")
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
        return redirect(url_for("login", next=url_for("profile")))

    discord_id = session["discord_id"]
    users_collection = get_db("Website")["users"]
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
    lb_type = request.args.get("type", "level")
    def _viewer_page_from_rank(rank: int, per_page: int) -> int:
        if not rank or rank < 1:
            return 1
        return ((rank - 1) // per_page) + 1
    
    client = get_db()
    username_col = client["Website"]["usernames"]
    username_col2 = client["Website"]["users"]
    viewer_id = session.get("discord_id")
    viewer_profile = username_col2.find_one({"_id": str(viewer_id)}) if viewer_id else None

    is_staff = False
    if viewer_profile:
        user_roles = viewer_profile.get("roles", [])
        is_staff = any(str(role) in STAFF_ROLE_IDS for role in user_roles)

    level_col = client["hayday"]["level"]

    sort_field = {
        "level": "xp",
        "messages": "message_count",
        "streak": "streak",
        "mentions": "Mentions"
    }.get(lb_type, "xp")

    if lb_type == "streak":
        col = client["Economy"]["Users"]
        total_users = col.count_documents({"streak": {"$gt": 0}})
        users = list(col.find({"streak": {"$gt": 0}}).sort("streak", -1).skip(skip).limit(limit))
        user_ids = [str(u["_id"]) for u in users]

    elif lb_type == "mentions":
        col = client["Mentions"]["Amount"]
        total_users = col.count_documents({"Mentions": {"$gt": 0}})
        users = list(col.find().sort("Mentions", -1).skip(skip).limit(limit))
        user_ids = [str(u["id"]) for u in users]

    elif lb_type == "hosted":
        col = client["Giveaway"]["current_giveaways"]
        count_cursor = col.aggregate([
            {"$match": {"host_id": {"$exists": True}}},
            {"$group": {"_id": "$host_id"}},
            {"$count": "count"}
        ])
        total_users = next(count_cursor, {}).get("count", 0)
        users = list(col.aggregate([
            {"$match": {"host_id": {"$exists": True}}},
            {"$group": {"_id": {"$toString": "$host_id"}, "hosted_count": {"$sum": 1}}},
            {"$sort": {"hosted_count": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ]))
        user_ids = [u["_id"] for u in users]

    elif lb_type == "wins":
        col = client["Giveaway"]["current_giveaways"]
        count_cursor = col.aggregate([
            {"$match": {"winners": {"$exists": True}}},
            {"$unwind": "$winners"},
            {"$group": {"_id": {"$toString": "$winners"}}},
            {"$count": "count"}
        ])
        total_users = next(count_cursor, {}).get("count", 0)
        users = list(col.aggregate([
            {"$match": {"winners": {"$exists": True}}},
            {"$unwind": "$winners"},
            {"$group": {"_id": {"$toString": "$winners"}, "won_count": {"$sum": 1}}},
            {"$sort": {"won_count": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ]))
        user_ids = [u["_id"] for u in users]

    elif lb_type == "trivia":
        col = client["Economy"]["Users"]
        raw = list(col.find({"trivia_total": {"$gte": 5}}))
        total_users = len(raw)
        sorted_users = sorted(raw, key=lambda u: u.get("trivia_correct", 0) / max(u.get("trivia_total", 1), 1), reverse=True)
        users = sorted_users[skip:skip + limit]
        user_ids = [str(u["_id"]) for u in users]

    elif lb_type == "verifications":
        col = client["Verify"]["TopUsers"]
        all_staff = list(col.find({}))
        total_users = len(all_staff)

        # Sort and slice
        sorted_staff = sorted(all_staff, key=lambda u: u.get("Number of Verifications", 0), reverse=True)
        users = sorted_staff[skip:skip + limit]

        # Make sure all user IDs are strings
        for user in users:
            user["_id"] = str(user["id"])

        user_ids = [user["_id"] for user in users]

    elif lb_type == "coins":
        col = client["Economy"]["Users"]
        total_users = col.count_documents({"coins": {"$gt": 0}})
        users = list(col.find({"coins": {"$gt": 0}}).sort("coins", -1).skip(skip).limit(limit))
        user_ids = [str(u["_id"]) for u in users]

    elif lb_type == "pet_xp":
        col = client["Economy"]["Users"]
        raw = list(col.find({"pet": {"$exists": True}}))
        ranked = sorted(
            [u for u in raw if isinstance(u.get("pet"), dict)],
            key=lambda u: (
                int((u.get("pet") or {}).get("level", 1) or 1),
                int((u.get("pet") or {}).get("xp", 0) or 0),
            ),
            reverse=True,
        )
        total_users = len(ranked)
        users = ranked[skip:skip + limit]
        user_ids = [str(u["_id"]) for u in users]

    else:  # default = level or messages
        total_users = level_col.count_documents({})
        users = list(level_col.find().sort(sort_field, -1).skip(skip).limit(limit))
        user_ids = [u["_id"] for u in users]

    profiles = list(username_col.find({"_id": {"$in": user_ids}}))
    profile_map = {p["_id"]: p for p in profiles}

    for i, user in enumerate(users):
        uid = str(user["id"]) if lb_type == "mentions" else str(user["_id"])

        user["uid"] = uid
        user["profile_url"] = f"/profile/{uid}"

        user["rank"] = skip + i + 1
        user["xp_formatted"] = f"{user.get('xp', 0):,}"
        user["level"] = user.get("level", 1)
        user["message_count"] = user.get("message_count", 0)
        user["mention_count"] = user.get("Mentions", 0)
        user["streak"] = user.get("streak", 0)
        user["coins"] = int(user.get("coins", 0) or 0)
        pet = user.get("pet") or {}
        user["pet_level"] = int(pet.get("level", 1) or 1)
        user["pet_xp"] = int(pet.get("xp", 0) or 0)
        profile = profile_map.get(uid)
        user["display_name"] = profile.get("display_name") or profile.get("username", "Unknown") if profile else f"<@{uid}>"
        user["avatar_url"] = profile.get("avatar") if profile else "https://cdn.discordapp.com/embed/avatars/0.png"
        user["is_boosting"] = profile.get("boosting", False) if profile else False
        user["hosted_count"] = user.get("hosted_count", 0)
        user["won_count"] = user.get("won_count", 0)
        user["trivia_correct"] = user.get("trivia_correct", 0)
        user["trivia_total"] = user.get("trivia_total", 0)

        if user["trivia_total"] > 0:
            user["trivia_percent"] = round((user["trivia_correct"] / user["trivia_total"]) * 100, 1)
        else:
            user["trivia_percent"] = 0.0
        user["verifications"] = user.get("Number of Verifications", 0)

    viewer_rank = None
    viewer_page = None

    if viewer_id:
        vid = str(viewer_id)

        try:
            if lb_type in ("coins", "streak", "trivia"):
                econ = client["Economy"]["Users"]

                try:
                    econ_id = int(vid)
                except (TypeError, ValueError):
                    econ_id = vid

                me = econ.find_one({"_id": econ_id}) or {}

                if lb_type == "coins":
                    my_val = int(me.get("coins", 0) or 0)
                    if my_val > 0:
                        above = econ.count_documents({"coins": {"$gt": my_val}})
                        viewer_rank = above + 1

                elif lb_type == "streak":
                    my_val = int(me.get("streak", 0) or 0)
                    if my_val > 0:
                        above = econ.count_documents({"streak": {"$gt": my_val}})
                        viewer_rank = above + 1

                elif lb_type == "trivia":
                    raw = list(econ.find({"trivia_total": {"$gte": 5}}))
                    def _ratio(u):
                        return (u.get("trivia_correct", 0) / max(u.get("trivia_total", 1), 1))
                    raw_sorted = sorted(raw, key=_ratio, reverse=True)
                    for idx, u in enumerate(raw_sorted):
                        if u.get("_id") == econ_id:
                            viewer_rank = idx + 1
                            break

            elif lb_type == "pet_xp":
                econ = client["Economy"]["Users"]
                try:
                    econ_id = int(vid)
                except (TypeError, ValueError):
                    econ_id = vid

                raw = list(econ.find({"pet": {"$exists": True}}))
                ranked = sorted(
                    [u for u in raw if isinstance(u.get("pet"), dict)],
                    key=lambda u: (
                        int((u.get("pet") or {}).get("level", 1) or 1),
                        int((u.get("pet") or {}).get("xp", 0) or 0),
                    ),
                    reverse=True,
                )
                for idx, u in enumerate(ranked):
                    if u.get("_id") == econ_id:
                        viewer_rank = idx + 1
                        break

            elif lb_type == "mentions":
                mcol = client["Mentions"]["Amount"]
                me = mcol.find_one({"id": vid}) or {}
                my_val = int(me.get("Mentions", 0) or 0)
                if my_val > 0:
                    above = mcol.count_documents({"Mentions": {"$gt": my_val}})
                    viewer_rank = above + 1

            elif lb_type in ("hosted", "wins"):
                gcol = client["Giveaway"]["current_giveaways"]

                if lb_type == "hosted":
                    grouped = list(gcol.aggregate([
                        {"$match": {"host_id": {"$exists": True}}},
                        {"$group": {"_id": {"$toString": "$host_id"}, "hosted_count": {"$sum": 1}}},
                    ]))
                    grouped.sort(key=lambda x: x.get("hosted_count", 0), reverse=True)
                    for idx, u in enumerate(grouped):
                        if str(u.get("_id")) == vid:
                            viewer_rank = idx + 1
                            break

                else:
                    grouped = list(gcol.aggregate([
                        {"$match": {"winners": {"$exists": True}}},
                        {"$unwind": "$winners"},
                        {"$group": {"_id": {"$toString": "$winners"}, "won_count": {"$sum": 1}}},
                    ]))
                    grouped.sort(key=lambda x: x.get("won_count", 0), reverse=True)
                    for idx, u in enumerate(grouped):
                        if str(u.get("_id")) == vid:
                            viewer_rank = idx + 1
                            break

            elif lb_type == "verifications":
                vcol = client["Verify"]["TopUsers"]
                all_staff = list(vcol.find({}))
                all_staff.sort(key=lambda u: u.get("Number of Verifications", 0), reverse=True)
                for idx, u in enumerate(all_staff):
                    if str(u.get("id")) == vid:
                        viewer_rank = idx + 1
                        break

            else:
                # default leaderboard (level/messages)
                me = level_col.find_one({"_id": vid}) or {}
                my_val = int(me.get(sort_field, 0) or 0)
                my_val = int(me.get(sort_field, 0) or 0)
                if my_val > 0:
                    above = level_col.count_documents({sort_field: {"$gt": my_val}})
                    viewer_rank = above + 1

        except Exception:
            viewer_rank = None

        if viewer_rank:
            viewer_page = _viewer_page_from_rank(viewer_rank, limit)

    total_pages = (total_users + limit - 1) // limit

    return render_template(
        "leaderboard.html",
        users=users,
        page=page,
        total_pages=total_pages,
        type=lb_type,
        viewer_id=viewer_id,
        is_staff=is_staff,
        viewer_rank=viewer_rank,
        viewer_page=viewer_page,
    )

@app.route("/callback")
@limiter.limit("10 per minute", key_func=get_remote_address, error_message="Too many requests to the callback endpoint. Please wait a bit.")
def callback():
    try:
        code = request.args.get("code")
        state = request.args.get("state")      
        if not code:
            return "鉂?Missing code from Discord redirect", 400

        state_next_page = "/"
        expected_nonce = session.get("oauth_state")
        if state:
            try:
                state_payload = oauth_state_serializer.loads(state)
                state_next_page = _safe_next_path(state_payload.get("next"), default="/")
                state_nonce = state_payload.get("nonce")
                if expected_nonce and state_nonce != expected_nonce:
                    return "鉂?Invalid OAuth state", 400
            except BadSignature:
                return "鉂?Invalid OAuth state", 400

        data = {
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_REDIRECT_URI,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        r = requests.post(
            "https://discord.com/api/oauth2/token",
            data=data,
            headers=headers,
            timeout=10
        )
        r.raise_for_status()
        access_token = r.json()["access_token"]
        user = requests.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"}, timeout=10
        ).json()

        GUILD_ID = "959220051427340379"  # Replace with your actual server ID

        member = requests.get(
            f"https://discord.com/api/users/@me/guilds/{GUILD_ID}/member",
            headers={"Authorization": f"Bearer {access_token}"}, timeout=10
        )
        guild_data = requests.get(
            f"https://discord.com/api/guilds/{GUILD_ID}",
            headers={"Authorization": f"Bot {BOT_TOKEN}"}, timeout=10
        ).json()
        session.permanent = True
        member_data = {}
        if member.status_code == 200:
            member_data = member.json()
            role_ids = [str(r) for r in member_data.get("roles", [])]

            session["roles"] = role_ids
            session["display_name"] = member_data.get("nick") or user["username"]
            session["is_member"] = str(MEMBER_ROLE_ID) in role_ids

            session["staff_role"] = None
            for rid, role_name in STAFF_ROLES.items():
                if str(rid) in role_ids:
                    session["staff_role"] = role_name
                    break
        else:
            role_ids = []
            session["roles"] = []
            session["display_name"] = user["username"]
            session["is_member"] = False
            session["staff_role"] = None

        session["discord_id"] = user["id"]
        session["username"] = user["username"] + "#" + user["discriminator"]
        
        client = get_db()
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
        staff_collection = client["Website"]["Staff"]
        staff_doc = staff_collection.find_one({"_id": user["id"]})
        if staff_doc:
            session["staff_role"] = staff_doc.get("role", None)  # Use .get safely
        else:
            session["staff_role"] = None

        session.modified = True      
        next_page = _safe_next_path(state_next_page or session.get("next_page"), default="/")

        session.pop("oauth_state", None)
        session.pop("next_page", None)
        session.modified = True

        resp = redirect(f"https://hayday.info{next_page}")
        return resp
    
    except Exception as e:
        traceback.print_exc()
        return f"<h1>鉂?Error:</h1><pre>{e}</pre>", 500

@app.route("/admin/purchases/export")
def export_purchases_csv():
    if not is_staff():
        return "Unauthorized", 403

    start = request.args.get("start")
    end = request.args.get("end")
    query = request.args.get("q", "").strip().lower()

    filter_ = {}
    if start or end:
        date_filter = {}
        if start:
            date_filter["$gte"] = datetime.fromisoformat(start)
        if end:
            date_filter["$lte"] = datetime.fromisoformat(end)
        filter_["timestamp"] = date_filter

    if query:
        filter_["$or"] = [
            {"item": {"$regex": query, "$options": "i"}},
            {"name": {"$regex": query, "$options": "i"}},
            {"user_id": {"$regex": query}}
        ]

    client = get_db()
    purchases = list(
        client["Economy"]["Purchases"]
        .find(filter_)
        .sort("timestamp", -1)
    )

    user_ids = list({str(p["user_id"]) for p in purchases})
    users = client["Website"]["users"].find({"_id": {"$in": user_ids}})
    user_map = {u["_id"]: u for u in users}

    # Prepare CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["User ID", "Display Name", "Item", "Key", "Price", "Timestamp"])

    for p in purchases:
        uid = str(p["user_id"])
        user = user_map.get(uid)
        display_name = user.get("display_name") or user.get("username") if user else uid

        writer.writerow([
            uid,
            display_name,
            p.get("name", ""),
            p.get("item", ""),
            p.get("price", ""),
            p.get("timestamp").strftime("%Y-%m-%d %H:%M")
        ])

    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=purchases.csv"}
    )

@app.route("/admin/users")
def admin_users():
    if not is_staff():
        return "Unauthorized", 403

    page = int(request.args.get("page", 1))
    query = request.args.get("q", "").strip().lower()
    per_page = 15
    search_filter = {}

    if query:
        search_filter["$or"] = [
            {"username": {"$regex": query, "$options": "i"}},
            {"_id": {"$regex": query}}
        ]

    client = get_db()
    users_collection = client["Website"]["users"]

    total = users_collection.count_documents(search_filter)
    users = list(
        users_collection.find(search_filter)
        .sort("username", 1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    return render_template(
        "admin_users.html",
        users=users,
        query=query,
        page=page,
        total_pages=(total + per_page - 1) // per_page
    )


@app.route("/admin/update-bio", methods=["POST"])
def update_user_bio():
    if not is_staff():
        return "Unauthorized", 403

    user_id = request.form.get("user_id")
    is_clear = request.form.get("clear") == "1"
    new_bio = request.form.get("bio", "").strip()

    client = get_db()
    users = client["Website"]["users"]
    if is_clear:
        users.update_one({"_id": user_id}, {"$unset": {"bio": ""}})
    elif new_bio:
        users.update_one({"_id": user_id}, {"$set": {"bio": new_bio}})

    return redirect(url_for("moderate_bios"))




@app.route("/admin/bios", methods=["GET", "POST"])
def moderate_bios():
    if not is_staff():
        return "Unauthorized", 403

    query = request.args.get("q", "").strip().lower()
    page = int(request.args.get("page", 1))
    per_page = 12
    filter_ = {"bio": {"$exists": True, "$ne": ""}}

    if query:
        filter_["$or"] = [
            {"username": {"$regex": query, "$options": "i"}},
            {"_id": {"$regex": query}}
        ]

    client = get_db()
    users_col = client["Website"]["users"]
    total = users_col.count_documents(filter_)
    users = list(
        users_col.find(filter_)
        .sort("username", 1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    return render_template(
        "admin_bios.html",
        users=users,
        query=query,
        page=page,
        total_pages=(total + per_page - 1) // per_page
    )

@app.route("/directory")
def public_directory():
    query = request.args.get("q", "").lower()
    page = int(request.args.get("page", 1))
    page_size = 12

    users_collection = get_db("Website")["users"]

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

    db = get_db("Website")
    usernames_col = db["usernames"]
    users_col = db["users"]

    member_role = "959220051469279296"
    query = {
        "roles": {
            "$in": [
                member_role,
                int(member_role)
            ]
        },
        "$or": [
            {"public_profile": True},
            {"public_profile": {"$exists": False}}  # default to public if not set
        ]
    }
    if search:
        norm_search = normalize(search)
        query = {
            "$and": [
                query,
                {
                    "$or": [
                        {"normalized_username": {"$regex": norm_search, "$options": "i"}},
                        {"normalized_display": {"$regex": norm_search, "$options": "i"}}
                    ]
                }
            ]
        }

    total = usernames_col.count_documents(query)

    raw_users = list(
        usernames_col.find(query)
        .sort("display_name", 1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    user_ids = [u["_id"] for u in raw_users]
    public_docs = list(
        users_col.find(
            {"_id": {"$in": user_ids}},
            {"public_profile": 1}
        )
    )
    public_map = {doc["_id"]: doc for doc in public_docs}
    users = []
    for user in raw_users:
        roles = user.get("roles", [])
        staff_badges = []
        for rid in roles:
            try:
                if isinstance(rid, dict) and "$numberLong" in rid:
                    rid_int = int(rid["$numberLong"])
                else:
                    rid_int = int(rid)
                if rid_int in STAFF_ROLES:
                    staff_badges.append(STAFF_ROLES[rid_int])
            except:
                continue

        settings_doc = public_map.get(user["_id"], {})
        user["public_profile"] = settings_doc.get("public_profile", True)
        avatar = user.get("avatar")
        if avatar and avatar.startswith("http"):
            user["avatar_url"] = avatar
        else:
            user["avatar_url"] = f"https://cdn.discordapp.com/avatars/{user['_id']}/{user.get('avatar_hash', '')}.png"
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

@app.route("/trading")
def trading_page():
    staff = ("discord_id" in session) and is_staff()
    return render_template("trading.html", is_staff=staff)

@app.route("/admin/trading/override/delete", methods=["POST"])
@csrf.exempt
def admin_trading_override_delete():
    if "discord_id" not in session or not is_staff():
        return jsonify(ok=False, error="Unauthorized"), 403

    item_key = (request.form.get("item_key") or "").strip().lower()
    if not item_key:
        return jsonify(ok=False, error="Missing item_key"), 400

    col = get_db("Website")["trading_item_overrides"]

    doc = col.find_one({"_id": item_key})
    if not doc:
        return jsonify(ok=False, error="Not found"), 404

    # Only allow deleting manual overrides
    if not doc.get("manual_override"):
        return jsonify(ok=False, error="Cannot delete non-manual override"), 400

    # Best-effort delete image from R2 if we have a key
    image_key = doc.get("image_key")
    if image_key:
        try:
            r2 = get_r2_client()
            r2.delete_object(Bucket=os.getenv("R2_BUCKET"), Key=image_key)
        except Exception:
            pass

    col.delete_one({"_id": item_key})

    return jsonify(ok=True)


@app.route("/admin/trading/override", methods=["POST"])
@csrf.exempt
def admin_trading_override():
    if "discord_id" not in session or not is_staff():
        return jsonify(ok=False, error="Unauthorized"), 403

    item_key = (request.form.get("item_key") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    aliases_raw = (request.form.get("aliases") or "").strip()
    source_url = (request.form.get("source_url") or "").strip()

    if not item_key:
        return jsonify(ok=False, error="Missing item_key"), 400
    if not name:
        return jsonify(ok=False, error="Missing name"), 400

    aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]

    update = {
        "name": name,
        "aliases": aliases,
        "source_url": source_url,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": str(session.get("discord_id")),
        "manual_override": True,
    }

    f = request.files.get("image")
    if f and f.filename:
        ext = os.path.splitext(f.filename)[1].lower() or ".png"
        if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
            return jsonify(ok=False, error="Image must be png/jpg/jpeg/webp"), 400

        key_name = f"items/{item_key}{ext}"

        image_url = r2_put_object(
            fileobj=f.stream,
            key=key_name,
            content_type=f.mimetype or "application/octet-stream"
        )

        update["image_key"] = key_name
        update["image_url"] = image_url

    col = get_db("Website")["trading_item_overrides"]
    col.update_one({"_id": item_key}, {"$set": update}, upsert=True)

    return jsonify(ok=True, item_key=item_key, name=name, image_url=update.get("image_url"))

@app.route("/api/trading/suggest")
def api_trading_suggest():
    q = (request.args.get("q", "") or "").strip().lower()
    limit = min(max(int(request.args.get("limit", 8)), 1), 20)

    display_map, alias_to_key, key_to_filename, _src, key_to_image_url = _trading_maps_with_overrides()

    if not q:
        return jsonify(ok=True, items=[])

    qk = clean_key(q)

    # If they typed an alias exactly, boost that item to the top
    resolved = alias_to_key.get(q) or alias_to_key.get(qk)

    scored = []
    for key, name in display_map.items():
        ck = clean_key(key)
        cn = clean_key(name)

        if qk not in ck and qk not in cn:
            continue

        score = 2
        if cn.startswith(qk) or ck.startswith(qk):
            score = 0
        elif (qk in cn) or (qk in ck):
            score = 1

        if resolved and key == resolved:
            score = -1

        scored.append((score, len(cn), name, key))

    scored.sort(key=lambda t: (t[0], t[1], t[2]))

    items = [{
        "item_key": key,
        "item_name": name,
        "image_url": key_to_image_url.get(key),
        "image_file": key_to_filename.get(key),    
    } for (_s, _l, name, key) in scored[:limit]]

    return jsonify(ok=True, items=items)



@app.route("/api/trading/overview")
def api_trading_overview():
    days = int(request.args.get("days", 7))
    post_type = (request.args.get("type", "all") or "all").lower()
    sort = (request.args.get("sort", "value") or "value").lower()
    q = (request.args.get("q", "") or "").strip().lower()

    page = max(1, int(request.args.get("page", 1)))
    per_page = 16

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    match = {
        "guild_id": TRADING_GUILD_ID,
        "created_at": {"$gte": since},
        "status": "accepted",
        "price_type": "coins",
    }

    if post_type in {"buy", "sell"}:
        match["post_type"] = post_type
    else:
        match["post_type"] = {"$in": ["buy", "sell"]}


    ticks = get_trading_collection("ticks")
    display_map, alias_to_key, key_to_filename, key_to_source_url, key_to_image_url = _trading_maps_with_overrides()


    pipeline = [
    {"$match": match},
    {"$group": {
        "_id": {"k": "$item_key", "t": "$post_type"},
        "sum_qty": {"$sum": {"$ifNull": ["$qty", 0]}},
        "sum_value": {"$sum": {"$cond": [
            {"$and": [{"$isNumber": "$qty"}, {"$isNumber": "$unit_price"}]},
            {"$multiply": ["$qty", "$unit_price"]},
            0,
        ]}},
        "posts": {"$sum": 1},
        "price_posts": {"$sum": {"$cond": [{"$isNumber": "$unit_price"}, 1, 0]}},
        "sum_unit_price": {"$sum": {"$cond": [{"$isNumber": "$unit_price"}, "$unit_price", 0]}},
    }},

    {"$project": {
        "_id": 0,
        "item_key": "$_id.k",
        "post_type": "$_id.t",
        "sum_qty": 1,
        "sum_value": 1,
        "posts": 1,

        # NEW
        "price_posts": 1,
        "sum_unit_price": 1,
    }},

    {"$limit": 10000},
    ]
    rows = list(ticks.aggregate(pipeline))

    trend_match = dict(match)
    trend_match["unit_price"] = {"$ne": None}  # only meaningful prices
    # match already excludes trade because post_type is buy/sell/all(buy+sell)

    trend_pipe = [
        {"$match": trend_match},
        {"$sort": {"created_at": 1}},
        {"$group": {
            "_id": {"k": "$item_key", "t": "$post_type"},
            "first_price": {"$first": "$unit_price"},
            "last_price": {"$last": "$unit_price"},
        }},
    ]
    trend_rows = list(ticks.aggregate(trend_pipe))

    # --- Market-price multiplier range from the normalized prize ticks. ---
    mp_match = {
        "guild_id": TRADING_GUILD_ID,
        "status": "accepted",
        "price_type": "market",
        "unit_price": {"$ne": None},
        "created_at": {"$gte": since},
    }
    if post_type in {"buy", "sell"}:
        mp_match["post_type"] = post_type
    else:
        mp_match["post_type"] = {"$in": ["buy", "sell"]}


    mp_pipe = [
        {"$match": mp_match},
        {"$group": {
            "_id": "$item_key",
            "min_mp": {"$min": "$unit_price"},
            "max_mp": {"$max": "$unit_price"},
            "mp_posts": {"$sum": 1},
        }},
    ]
    mp_rows = list(ticks.aggregate(mp_pipe))

    mp_map = {}  # canonical_key -> {"min": x, "max": y, "posts": n}
    for r in mp_rows:
        raw_key = (r.get("_id") or "").strip().lower()
        if not raw_key:
            continue

        # resolve to canonical key
        if raw_key in display_map:
            canonical = raw_key
        else:
            ck = clean_key(raw_key)
            canonical = alias_to_key.get(raw_key) or alias_to_key.get(ck)

        if not canonical or canonical not in display_map:
            continue

        mp_map[canonical] = {
            "min": r.get("min_mp"),
            "max": r.get("max_mp"),
            "posts": int(r.get("mp_posts") or 0),
        }


    trend_map = {}  # canonical_key -> {"sell": pct, "buy": pct}

    for r in trend_rows:
        raw_key = (r["_id"].get("k") or "").strip().lower()
        t = (r["_id"].get("t") or "").strip().lower()
        if t not in ("buy", "sell") or not raw_key:
            continue

        # resolve to controlled canonical key
        if raw_key in display_map:
            canonical = raw_key
        else:
            ck = clean_key(raw_key)
            canonical = alias_to_key.get(raw_key) or alias_to_key.get(ck)

        if not canonical or canonical not in display_map:
            continue

        first_p = r.get("first_price")
        last_p = r.get("last_price")
        try:
            first_p = float(first_p)
            last_p = float(last_p)
        except:
            continue

        if first_p <= 0:
            continue

        pct = ((last_p - first_p) / first_p) * 100.0
        trend_map.setdefault(canonical, {})[t] = pct

    merged = {}
    for r in rows:
        key = (r.get("item_key") or "").strip().lower()
        t = (r.get("post_type") or "").strip().lower()
        if not key or t not in ("buy", "sell"):
            continue

        if key in display_map:
            canonical = key
        else:
            ck = clean_key(key)
            canonical = alias_to_key.get(key) or alias_to_key.get(ck)

        if not canonical or canonical not in display_map:
            continue

        m = merged.setdefault(canonical, {
            "item_key": canonical,
            "item_name": display_map[canonical],

            "buy_qty": 0, "buy_value": 0, "buy_posts": 0,
            "sell_qty": 0, "sell_value": 0, "sell_posts": 0,
            "buy_price_posts": 0, "buy_price_sum": 0,
            "sell_price_posts": 0, "sell_price_sum": 0,
        })


        qty = int(r.get("sum_qty") or 0)
        val = int(r.get("sum_value") or 0)
        posts = int(r.get("posts") or 0)
        price_posts = int(r.get("price_posts") or 0)
        price_sum = float(r.get("sum_unit_price") or 0)

        if t == "buy":
            m["buy_qty"] += qty
            m["buy_value"] += val
            m["buy_posts"] += posts

            m["buy_price_posts"] += price_posts
            m["buy_price_sum"] += price_sum
        else:
            m["sell_qty"] += qty
            m["sell_value"] += val
            m["sell_posts"] += posts

            m["sell_price_posts"] += price_posts
            m["sell_price_sum"] += price_sum

    # Keep items that currently have only market-multiplier observations.
    for canonical in mp_map:
        merged.setdefault(canonical, {
            "item_key": canonical,
            "item_name": display_map[canonical],
            "buy_qty": 0, "buy_value": 0, "buy_posts": 0,
            "sell_qty": 0, "sell_value": 0, "sell_posts": 0,
            "buy_price_posts": 0, "buy_price_sum": 0,
            "sell_price_posts": 0, "sell_price_sum": 0,
        })


    items_list = list(merged.values())

    for it in items_list:
        it["avg_buy"]  = (it["buy_price_sum"]  / it["buy_price_posts"])  if it["buy_price_posts"]  > 0 else None
        it["avg_sell"] = (it["sell_price_sum"] / it["sell_price_posts"]) if it["sell_price_posts"] > 0 else None

        it["total_qty"] = it["buy_qty"] + it["sell_qty"]
        it["total_posts"] = it["buy_posts"] + it["sell_posts"]
        it["total_value"] = it["buy_value"] + it["sell_value"]
        # XMP range (if available)
        mp = mp_map.get(it["item_key"])
        it["xmp_min"] = mp.get("min") if mp else None
        it["xmp_max"] = mp.get("max") if mp else None
        it["xmp_posts"] = mp.get("posts") if mp else 0


    def sk(it):
        if sort == "qty": return it["total_qty"]
        if sort == "posts": return it["total_posts"]
        if sort == "avg_buy": return it["avg_buy"] or 0
        if sort == "avg_sell": return it["avg_sell"] or 0
        if sort == "trend": return it.get("trend_pct") if it.get("trend_pct") is not None else -999999
        return it["total_value"]

    if q:
        qk = clean_key(q)
        qn = clean_key(q)
        resolved = alias_to_key.get(q) or alias_to_key.get(qn) or alias_to_key.get(clean_key(q))


        if resolved:
            items_list = [it for it in items_list if it["item_key"] == resolved]
        else:
            items_list = [
                it for it in items_list
                if qk in clean_key(it["item_key"]) or qk in clean_key(it["item_name"])
            ]
    for it in items_list:
        key = it["item_key"]
        m = trend_map.get(key) or {}
        it["trend_sell_pct"] = m.get("sell")
        it["trend_buy_pct"]  = m.get("buy")

        # keep this if you still want one combined badge somewhere
        it["trend_pct"] = it["trend_sell_pct"] if it["trend_sell_pct"] is not None else it["trend_buy_pct"]

        it["item_name"] = display_map.get(key) or key.replace("_", " ").title()
        it["image_file"] = key_to_filename.get(key)
        it["source_url"] = key_to_source_url.get(key)         
        it["image_url"]  = key_to_image_url.get(key)     


    items_list.sort(key=sk, reverse=True)


    total = len(items_list)

    total_pages = max(ceil(total / per_page), 1)
    page = min(page, total_pages)

    start = (page - 1) * per_page
    page_items = items_list[start:start + per_page]

    return jsonify(
        ok=True,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        items=page_items
    )

@app.route("/admin/trading/tick/delete", methods=["POST"])
@csrf.exempt
def admin_trading_tick_delete():
    if "discord_id" not in session or not is_staff():
        return jsonify(ok=False, error="Unauthorized"), 403

    tick_id = (request.form.get("tick_id") or "").strip()
    if not tick_id:
        return jsonify(ok=False, error="Missing tick_id"), 400

    try:
        oid = ObjectId(tick_id)
    except InvalidId:
        return jsonify(ok=False, error="Invalid tick_id"), 400

    ticks = get_trading_collection("ticks")
    res = ticks.delete_one({"_id": oid, "guild_id": TRADING_GUILD_ID})

    return jsonify(ok=True, deleted=int(res.deleted_count))


@app.route("/api/trading/item/<item_key>/posts")
def api_trading_item_posts(item_key):
    bucket = (request.args.get("bucket", "day") or "day").lower()
    if bucket not in {"day", "hour"}:
        bucket = "day"

    at = (request.args.get("at") or "").strip()
    post_type = (request.args.get("type") or "").strip().lower()
    if post_type not in {"buy", "sell", "both"}:
        return jsonify(ok=False, error="Invalid type (must be buy/sell/both)"), 400


    limit = min(max(int(request.args.get("limit", 200)), 1), 500)

    # Resolve item_key to canonical (same logic as history endpoint)
    display_map, alias_to_key, _k2f, _source_map, _img_url_map = _trading_maps_with_overrides()
    raw = (item_key or "").strip().lower()
    if raw in display_map:
        canonical = raw
    else:
        canonical = alias_to_key.get(raw) or alias_to_key.get(clean_key(raw))

    if not canonical or canonical not in display_map:
        return jsonify(ok=False, error="Unknown item_key"), 404

    # Parse "at" label into a UTC start/end window
    try:
        if bucket == "hour":
            # labels are like: "YYYY-MM-DD HH:MM"
            start = datetime.strptime(at, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            end = start + timedelta(hours=1)
        else:
            # labels are like: "YYYY-MM-DD"
            start = datetime.strptime(at, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end = start + timedelta(days=1)
    except ValueError:
        return jsonify(ok=False, error="Invalid at format"), 400

    match = {
        "guild_id": TRADING_GUILD_ID,
        "status": "accepted",
        "price_type": "coins",
        "item_key": canonical,
        "post_type": {"$in": ["buy", "sell"]} if post_type == "both" else post_type,
        "created_at": {"$gte": start, "$lt": end},
    }

    # Return posts for scrolling + jump link
    ticks = get_trading_collection("ticks")
    tick_rows = list(ticks.find(match).sort("created_at", -1).limit(limit))

    posts = []
    for d in tick_rows:
        qty = d.get("qty")
        unit_price = d.get("unit_price")
        total_value = None
        if isinstance(qty, (int, float)) and isinstance(unit_price, (int, float)):
            total_value = qty * unit_price
        posts.append({
            "id": str(d.get("_id")),
            "post_type": d.get("post_type"),
            "ts": d.get("created_at").isoformat() if d.get("created_at") else None,
            "jump_url": d.get("jump_url"),
            "author_id": str(d.get("author_id")) if d.get("author_id") is not None else None,
            "channel_id": str(d.get("channel_id")) if d.get("channel_id") is not None else None,
            "message_id": str(d.get("message_id")) if d.get("message_id") is not None else None,
            "qty": qty,
            "unit_price": unit_price,
            "total_value": total_value,
        })


    return jsonify(
        ok=True,
        item_key=canonical,
        bucket=bucket,
        at=at,
        type=post_type,
        count=len(posts),
        posts=posts,
    )

@app.route("/api/trading/item/<item_key>/history")
def api_trading_item_history(item_key):
    bucket = (request.args.get("bucket", "day") or "day").lower()
    if bucket not in {"day", "hour"}:
        bucket = "day"

    # range can be: 7,14,30,90,365,all
    range_raw = (request.args.get("range", "30") or "30").lower().strip()

    # Resolve to a controlled key
    display_map, alias_to_key, _k2f, _source_map, _img_url_map = _trading_maps_with_overrides()

    raw = (item_key or "").strip().lower()
    if raw in display_map:
        canonical = raw
    else:
        canonical = alias_to_key.get(raw) or alias_to_key.get(clean_key(raw))

    if not canonical or canonical not in display_map:
        return jsonify(ok=False, error="Unknown item_key")

    match = {
        "guild_id": TRADING_GUILD_ID,
        "status": "accepted",
        "price_type": "coins",
        "item_key": canonical,
        "post_type": {"$in": ["buy", "sell"]},
        "unit_price": {"$ne": None},
    }

    # Apply range filter (server-side) so the popup range dropdown works
    now = datetime.now(timezone.utc)
    if range_raw != "all":
        try:
            days = int(range_raw)
            match["created_at"] = {"$gte": now - timedelta(days=days)}
        except ValueError:
            # fallback
            match["created_at"] = {"$gte": now - timedelta(days=30)}

    unit = "hour" if bucket == "hour" else "day"

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {
                "d": {"$dateTrunc": {"date": "$created_at", "unit": unit}},
                "t": "$post_type",
            },
            "avg_price": {"$avg": "$unit_price"},
            "posts": {"$sum": 1},
            "qty": {"$sum": {"$ifNull": ["$qty", 0]}},
        }},
        {"$sort": {"_id.d": 1}},
    ]

    ticks = get_trading_collection("ticks")
    rows = list(ticks.aggregate(pipeline))

    # date -> { buy: {avg, posts}, sell: {avg, posts} }
    series = {}
    for r in rows:
        d = r["_id"]["d"]
        t = r["_id"]["t"]
        if d not in series:
            series[d] = {
                "buy": {"avg": None, "posts": 0},
                "sell": {"avg": None, "posts": 0},
            }

        series[d][t]["avg"] = float(r["avg_price"]) if r.get("avg_price") is not None else None
        series[d][t]["posts"] = int(r.get("posts") or 0)

    dates = sorted(series.keys())
    labels = [dt.strftime("%Y-%m-%d %H:%M" if bucket == "hour" else "%Y-%m-%d") for dt in dates]

    buy = [series[dt]["buy"]["avg"] for dt in dates]
    sell = [series[dt]["sell"]["avg"] for dt in dates]

    buy_posts = [series[dt]["buy"]["posts"] for dt in dates]
    sell_posts = [series[dt]["sell"]["posts"] for dt in dates]

    return jsonify(
        ok=True,
        item_key=canonical,
        item_name=display_map.get(canonical, canonical),
        bucket=bucket,
        range=range_raw,
        labels=labels,
        buy=buy,
        sell=sell,
        buy_posts=buy_posts,
        sell_posts=sell_posts,
    )


@app.route("/profile/<discord_id>")
def public_profile(discord_id):
    viewer_id = session.get("discord_id")
    if viewer_id == discord_id:
        return redirect(url_for("profile"))

    # Defaults
    level = xp = message_count = boost_time_left = None
    progress_percent = current_xp_formatted = required_xp_formatted = rank = None
    is_owner = viewer_id == discord_id

    client= get_db()
    usernames_collection = client["Website"]["usernames"]
    users_collection = client["Website"]["users"]

    fallback = usernames_collection.find_one({"_id": discord_id})
    if not fallback:
        return "🚫 This profile is private or does not exist.", 404

    # Get synced info from Website.usernames
    display_name = fallback.get("display_name", fallback.get("username", "Unknown"))
    avatar_url = fallback.get("avatar", "https://cdn.discordapp.com/embed/avatars/0.png")
    roles = fallback.get("roles", [])

    # Get Website.users doc and force-sync name/avatar
    user = users_collection.find_one({"_id": discord_id}) or {}
    user["display_name"] = display_name  # always use latest name from usernames collection
    user["avatar"] = avatar_url          # always use latest avatar from usernames collection

    # Public/private check
    if not user.get("public_profile", True) and not is_owner:
        return "🚫 This profile is private or does not exist.", 404


    # Staff badges from roles
    staff_badges = []
    for rid in roles:
        try:
            if isinstance(rid, dict) and "$numberLong" in rid:
                rid_int = int(rid["$numberLong"])
            else:
                rid_int = int(rid)
            if rid_int in STAFF_ROLES:
                staff_badges.append(STAFF_ROLES[rid_int])
        except:
            continue

    # Economy
    eco_user = client["Economy"]["Users"].find_one({"_id": int(discord_id)}) or {}
    coins = eco_user.get("coins", 0)
    streak = eco_user.get("streak", 0)

    # Mentions
    mention_col = client["Mentions"]["Amount"]
    mention_doc = mention_col.find_one({"id": int(discord_id)})
    mention_count = mention_doc.get("Mentions", 0) if mention_doc else 0

    # Level
    level_col = client["hayday"]["level"]
    level_doc = level_col.find_one({"_id": discord_id})
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
        try:
            rank = level_col.count_documents({"xp": {"$gt": xp}}) + 1
        except Exception:
            app.logger.exception("Failed to calculate public profile rank for %s", discord_id)
            rank = "?"

    return render_template(
        "profile.html",
        discord_id=discord_id,
        avatar_url=avatar_url,
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
        is_owner=is_owner,
        pet=eco_user.get("pet")
    )



@app.route("/builder")
def builder():
    return render_template("builder.html")


_TIER_RE = re.compile(r"^(?P<prefix>.+)_t(?P<tier>\d+)$")
_MUTE_VARIANT_RE = re.compile(r"^mute_other_(?P<minutes>\d+)m$")

def _sorted_shop_items(shop_items: dict):
    """
    Sort rules:
    1) Most expensive 'group' first (group = prefix before _tX)
    2) Inside a group, Tier III, II, I next to each other (highest tier first)
    3) Mute variants stay next to each other in minute order
    4) Fallback sorting by price desc
    """
    rows = []
    for key, item in shop_items.items():
        key_l = (key or "").lower()

        m = _TIER_RE.match(key_l)
        mute_match = _MUTE_VARIANT_RE.match(key_l)
        group = "mute_other" if mute_match else (m.group("prefix") if m else key_l)
        tier = int(m.group("tier")) if m else 0
        mute_minutes = int(mute_match.group("minutes")) if mute_match else None
        price = int(item.get("price", 0) or 0)

        rows.append((key, item, group, tier, price, mute_minutes))

    # group max price (so grouped tier sets sort by their strongest tier)
    group_max = {}
    for _, _, group, _, price, _ in rows:
        group_max[group] = max(group_max.get(group, 0), price)

    # Sort: group expensive first, then tier high->low, then price high->low
    rows.sort(
        key=lambda r: (
            -group_max[r[2]],
            0 if r[5] is not None else 1,
            r[5] if r[5] is not None else -r[3],
            -r[4],
            r[0],
        )
    )

    # Return list of (key, item) tuples for Jinja: {% for key, item in items %}
    return [(k, it) for (k, it, _, _, _, _) in rows]


@app.route("/shop")
def shop():
    if "discord_id" not in session:
        return redirect("/login")

    user_id = int(session["discord_id"])
    coins = 0
    owned_items = set()

    client= get_db()
    eco_user = client["Economy"]["Users"].find_one({"_id": user_id}) or {}
    lvl_doc = client["hayday"]["level"].find_one({"_id": str(user_id)}) or {}

    coins = int(eco_user.get("coins", 0))

    # Base owned_items (if you ever use this)
    owned_items = set(eco_user.get("owned_items", []) or [])

    # -------------------------
    # Daily Upgrade Tier logic
    # -------------------------
    daily_tier = int(eco_user.get("daily_upgrade_tier", 0) or 0)

    if daily_tier >= 1:
        owned_items.add("daily_upgrade_t1")
    if daily_tier >= 2:
        owned_items.add("daily_upgrade_t2")
    if daily_tier >= 3:
        owned_items.add("daily_upgrade_t3")

    # -------------------------
    # Permanent XP Boost logic
    # -------------------------
    perm_tier = int(lvl_doc.get("perm_xp_tier", 0) or 0)

    if perm_tier >= 1:
        owned_items.add("perm_xp_boost_t1")
    if perm_tier >= 2:
        owned_items.add("perm_xp_boost_t2")
    if perm_tier >= 3:
        owned_items.add("perm_xp_boost_t3")

    # -------------------------
    # Prestige Roles (Optional)
    # -------------------------
    # Only works if you store flags in DB when purchased
    if eco_user.get("wealth_flex_owned"):
        owned_items.add("wealth_flex_role")

    if eco_user.get("millionaire_owned"):
        owned_items.add("millionaire_club_role")

    # -------------------------
    # Passive Message Income Tier logic
    # -------------------------
    passive_tier = int(eco_user.get("passive_income_tier", 0) or 0)

    # Backwards compat (if you previously used passive_income_licenses)
    if passive_tier <= 0 and eco_user.get("passive_income_licenses"):
        passive_tier = min(3, int(eco_user.get("passive_income_licenses", 0) or 0))

    if passive_tier >= 1:
        owned_items.add("passive_income_t1")
    if passive_tier >= 2:
        owned_items.add("passive_income_t2")
    if passive_tier >= 3:
        owned_items.add("passive_income_t3")

    sorted_items = _sorted_shop_items(SHOP_ITEMS)

    return render_template(
        "shop.html",
        items=sorted_items,     
        coins=coins,
        owned_items=list(owned_items)
    )

@csrf.exempt
@app.route("/buy", methods=["POST"])
def buy_item():
    if "discord_id" not in session:
        flash("You need to log in to make a purchase.", "error")
        return redirect(url_for("login", next=url_for("shop")))

    item_id = (request.form.get("item_id") or "").strip().lower()
    if not item_id or item_id not in SHOP_ITEMS:
        flash("Unknown item.", "error")
        return redirect(url_for("shop"))

    user_id = int(session["discord_id"])

    bot_base = os.getenv("BOT_BASE_URL")
    bot_key = os.getenv("BOT_WEBHOOK_KEY")

    print("[SHOP] buy_item user_id=", user_id, "item_id=", item_id)
    print("[SHOP] BOT_BASE_URL=", bot_base, "BOT_WEBHOOK_KEY set?", bool(bot_key))

    if not bot_base or not bot_key:
        flash("Missing BOT_BASE_URL / BOT_WEBHOOK_KEY on website.", "error")
        return redirect(url_for("shop"))

    try:
        r = requests.post(
            f"{bot_base.rstrip('/')}/webhook/shop/buy",
            headers={"Authorization": bot_key},
            json={"user_id": user_id, "item": item_id},
            timeout=10,
        )

        print("[SHOP] bot status:", r.status_code)
        print("[SHOP] bot text:", r.text[:500])

        data = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
        print("[SHOP] bot json:", data)

    except Exception as e:
        print("[SHOP] ERROR contacting bot:", repr(e))
        data = {"success": False, "error": f"Failed to contact bot service: {e}"}

    # IMPORTANT: treat error as failure even if success=True
    bot_ok = bool(data.get("ok") or data.get("success"))
    if (not bot_ok) or data.get("error"):
        flash(f"Purchase failed: {data.get('error', 'Unknown error')}", "error")
        return redirect(url_for("shop"))

    flash(f"Purchase complete: {SHOP_ITEMS[item_id]['name']}", "success")
    return redirect(url_for("shop"))

@app.route("/admin/purchases")
def view_purchases():
    if not is_staff():
        return "Unauthorized", 403

    query = request.args.get("q", "").strip().lower()
    start = request.args.get("start")
    end = request.args.get("end")
    page = int(request.args.get("page", 1))
    per_page = 20
    filter_ = {}

    # Handle date range
    if start or end:
        date_filter = {}
        if start:
            date_filter["$gte"] = datetime.fromisoformat(start)
        if end:
            date_filter["$lte"] = datetime.fromisoformat(end)
        filter_["timestamp"] = date_filter

    if query:
        filter_["$or"] = [
            {"item": {"$regex": query, "$options": "i"}},
            {"name": {"$regex": query, "$options": "i"}},
            {"user_id": {"$regex": query}}
        ]

    client= get_db()
    purchases_col = client["Economy"]["Purchases"]
    user_col = client["Website"]["users"]

    total = purchases_col.count_documents(filter_)
    purchases = list(
        purchases_col.find(filter_)
        .sort("timestamp", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    user_ids = list({str(p["user_id"]) for p in purchases})
    users = list(user_col.find({"_id": {"$in": user_ids}}))
    user_map = {u["_id"]: u for u in users}

    for p in purchases:
        uid = str(p["user_id"])
        user = user_map.get(uid)
        p["display_name"] = user.get("display_name") or user.get("username") if user else uid

    return render_template(
        "admin_purchases.html",
        purchases=purchases,
        query=query,
        start=start,
        end=end,
        page=page,
        total_pages=(total + per_page - 1) // per_page
    )



@app.route("/api/starboard/threshold", methods=["GET"])
def get_star_threshold():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    client= get_db()
    col = client["hayday"]["starboard"]
    settings = col.find_one({"config": "starboard_settings"}) or {}
    threshold = settings.get("star_threshold", 5)

    # Convert Decimal128 or other Mongo types if necessary
    if isinstance(threshold, dict) and "$numberInt" in threshold:
        threshold = int(threshold["$numberInt"])

    return jsonify({"threshold": threshold})



@app.route("/api/starboard/data")
def starboard_data():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    client= get_db()
    col = client["hayday"]["starboard"]

    settings = col.find_one({"config": "starboard_settings"}) or {}
    starboard_entries = list(
        col.find({"starboard_message_id": {"$exists": True}})
        .sort("star_count", -1)
    )

    for entry in starboard_entries:
        entry["_id"] = str(entry["_id"])
        entry["star_count"] = int(entry.get("star_count", 0))
        entry["original_message_id"] = str(entry.get("original_message_id", ""))
        entry["starboard_message_id"] = str(entry.get("starboard_message_id", ""))

        # Add these two lines:
        entry["guild_id"] = str(entry.get("guild_id", ""))
        entry["channel_id"] = str(entry.get("channel_id", ""))


    return jsonify({
        "settings": {
            "star_threshold": int(settings.get("star_threshold", 5))
        },
        "entries": starboard_entries
    })

@csrf.exempt
@app.route("/log-interaction", methods=["POST"])
def log_interaction():
    if session.get("discord_id") == "154282062973501441":
        return "OK"  # Skip logging the owner

    data = request.get_json()
    user_agent = request.headers.get("User-Agent")

    log = {
        "discord_id": session.get("discord_id"),
        "username": session.get("username"),
        "user_agent": user_agent,
        "action": data.get("action"),
        "details": data.get("details", {}),
        "timestamp": datetime.now(timezone.utc)
    }

    client= get_db()
    client["Website"]["InteractionLogs"].insert_one(log)

    return "OK"



@app.route("/admin/interactions")
def view_interaction_logs():
    if session.get("discord_id") != "154282062973501441":
        return "Unauthorized", 403

    page = int(request.args.get("page", 1))
    search = request.args.get("search", "").strip()
    action_filter = request.args.get("action", "")
    anon_only = request.args.get("anon", "") == "1"
    export = request.args.get("export", "") == "1"

    limit = 30
    skip = (page - 1) * limit

    query = {}

    if search:
        query["$or"] = [
            {"action": {"$regex": search, "$options": "i"}},
            {"username": {"$regex": search, "$options": "i"}},
            {"details.text": {"$regex": search, "$options": "i"}}
        ]
    if action_filter:
        query["action"] = action_filter
    if anon_only:
        query["username"] = None

    client= get_db()
    col = client["Website"]["InteractionLogs"]

    if export:
        logs = list(col.find(query).sort("timestamp", -1))
        response = make_response()
        response.headers["Content-Disposition"] = "attachment; filename=interaction_logs.csv"
        response.headers["Content-Type"] = "text/csv"
        writer = csv.writer(response.stream)
        writer.writerow(["Timestamp", "Action", "Username", "Discord ID", "Text", "Href", "User Agent"])
        for log in logs:
            writer.writerow([
                log.get("timestamp"),
                log.get("action", ""),
                log.get("username", ""),
                log.get("discord_id", ""),
                log.get("details", {}).get("text", ""),
                log.get("details", {}).get("href", ""),
                log.get("user_agent", "")
            ])
        return response

    total = col.count_documents(query)
    logs = list(col.find(query).sort("timestamp", -1).skip(skip).limit(limit))

    # Stats for the normal interaction logs
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    past_week = today - timedelta(days=6)

    stats = {
        "today": col.count_documents({"timestamp": {"$gte": today}}),
        "week": col.count_documents({"timestamp": {"$gte": past_week}}),
        "anon": col.count_documents({"username": None}),
        "actions": col.distinct("action")
    }

    # Top pages tracking
    pv_col = client["Website"]["PageViews"]

    match_real_pages = {
        "$match": {
            "_id": {
                "$regex": r"^(?!/(?:api|thumb-file|img-proxy|log-interaction|static|assets|webhook|oauth|internal)\b)"
                        r"(?!.*\.(?:js|css|png|jpe?g|gif|webp|svg|ico|json|xml|map|txt|csv)$)"
                        r"^(?!/(?:robots\.txt|favicon\.ico|callback)$)"
            }
        }
    }

    top_pages = list(pv_col.aggregate([
        match_real_pages,
        {"$sort": {"count": -1}},
        {"$limit": 20}
    ]))

    agg = list(pv_col.aggregate([
        match_real_pages,
        {"$group": {"_id": None, "total": {"$sum": "$count"}}}
    ]))
    total_views = agg[0]["total"] if agg else 0

    for p in top_pages:
        p["_id"] = str(p.get("_id", ""))

            
    return render_template(
        "admin_interactions.html",
        logs=logs,
        page=page,
        total=total,
        limit=limit,
        search=search,
        action_filter=action_filter,
        anon_only=anon_only,
        stats=stats,
        top_pages=top_pages,
        total_views=total_views,    
        year=datetime.now().year
    )


@app.route("/api/starboard/delete", methods=["POST"])
def delete_starboard_message():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    message_id = str(data.get("message_id"))

    client= get_db()
    col = client["hayday"]["starboard"]
    result = col.delete_one({"starboard_message_id": message_id})

    if result.deleted_count > 0:
        return jsonify({"message": "✅ Starboard message deleted."})
    else:
        return jsonify({"message": "鉂?Message not found."})
    

@app.route("/starboard-dashboard")
def starboard_dashboard():
    if not is_admin():  # optionally require stricter access than is_staff()
        return "Unauthorized", 403

    return render_template("starboard_dashboard.html", year=datetime.now().year)


@app.route("/auction-dashboard")
def auction_dashboard():
    if "discord_id" not in session:
        return redirect("/login-page")
    if not is_staff():
        return "Unauthorized", 403

    def fix_ids(doc):
        if isinstance(doc, list):
            return [fix_ids(x) for x in doc]
        if isinstance(doc, dict):
            new_doc = {}
            for k, v in doc.items():
                if isinstance(v, (ObjectId, int)) and k in {"_id", "message_id", "channel_id", "owner_id", "highest_bidder"}:
                    new_doc[k] = str(v)
                else:
                    new_doc[k] = fix_ids(v)
            return new_doc
        return doc

    active_page = int(request.args.get("active_page", 1))
    ended_page = int(request.args.get("ended_page", 1))
    log_page = int(request.args.get("log_page", 1))
    ban_page = int(request.args.get("ban_page", 1))
    limit = 12

    skip_active = (active_page - 1) * limit
    skip_ended = (ended_page - 1) * limit
    skip_logs = (log_page - 1) * limit
    skip_bans = (ban_page - 1) * limit

    client= get_db()
    db = client["hayday"]
    user_col = client["Website"]["usernames"]
    log_col = client["Website"]["Logs"]

    active_auctions_all = list(db["auctions"].find({"status": "active"}).sort("end_time", 1))
    active_auctions_json = fix_ids([
        {
            "message_id": auc.get("message_id"),
            "item": auc.get("item", ""),
            "quantity": auc.get("quantity", 1),
            "current_bid": auc.get("current_bid", 0),
            "min_increment": auc.get("min_increment", 1),
            "status": auc.get("status", "active"),
            "image_url": auc.get("image_url", ""),
        }
        for auc in active_auctions_all
    ])
    active_auctions = active_auctions_all[skip_active : skip_active + limit]

    ended_auctions = list(
        db["auctions"].find({"status": {"$in": ["ended", "no_bids"]}})
        .sort("end_time", -1)
        .skip(skip_ended).limit(limit)
    )
    logs = list(
        log_col.find({"type": {"$regex": "^auction_"}})
        .sort("timestamp", -1)
        .skip(skip_logs).limit(limit)
    )
    AUCTION_BANNED_ROLE_ID = 1379087489779630121
    auction_banned_role_ids = [AUCTION_BANNED_ROLE_ID, str(AUCTION_BANNED_ROLE_ID)]
    banned_users = list(
        user_col.find({"roles": {"$in": auction_banned_role_ids}})
        .skip(skip_bans).limit(limit)
    )

    # Count total documents
    active_total = db["auctions"].count_documents({"status": "active"})
    ended_total = db["auctions"].count_documents({"status": {"$in": ["ended", "no_bids"]}})
    log_total = log_col.count_documents({"type": {"$regex": "^auction_"}})
    ban_total = user_col.count_documents({"roles": {"$in": auction_banned_role_ids}})

    active_total_pages = max((active_total + limit - 1) // limit, 1)
    ended_total_pages = max((ended_total + limit - 1) // limit, 1)
    log_total_pages = max((log_total + limit - 1) // limit, 1)
    ban_total_pages = max((ban_total + limit - 1) // limit, 1)

    # Collect all user IDs
    user_ids = set()
    for auc in active_auctions + ended_auctions:
        user_ids.add(str(auc.get("owner_id")))
        user_ids.add(str(auc.get("highest_bidder")))
    for log in logs:
        if "author" in log and "id" in log["author"]:
            user_ids.add(str(log["author"]["id"]))
    for user in banned_users:
        user_ids.add(user["_id"])

    profiles = list(user_col.find({"_id": {"$in": list(user_ids)}}))
    user_map = {u["_id"]: u for u in profiles}

    for auc in active_auctions + ended_auctions:
        auc["owner_info"] = user_map.get(str(auc.get("owner_id")), {})
        auc["bidder_info"] = user_map.get(str(auc.get("highest_bidder")), {})
    for log in logs:
        author_id = str(log.get("author", {}).get("id"))
        log["author_info"] = user_map.get(author_id, {})
    for user in banned_users:
        user["display_name"] = user.get("display_name", user.get("username", "Unknown"))

    return render_template(
        "auction_dashboard.html",
        active_auctions=active_auctions,
        active_auctions_json=active_auctions_json,
        ended_auctions=ended_auctions,
        logs=logs,
        banned_users=banned_users,
        active_total=active_total,
        ended_total=ended_total,
        log_total=log_total,
        ban_total=ban_total,
        active_page=active_page,
        ended_page=ended_page,
        log_page=log_page,
        ban_page=ban_page,
        active_total_pages=active_total_pages,
        ended_total_pages=ended_total_pages,
        log_total_pages=log_total_pages,
        ban_total_pages=ban_total_pages,
        year=datetime.now().year
    )


def _notify_auction_bot(webhook_path, payload, timeout=5):
    base_url = (os.getenv("BOT_WEBHOOK_URL") or os.getenv("WEBHOOK_BASE_URL") or "").rstrip("/")
    webhook_key = os.getenv("BOT_WEBHOOK_KEY")
    if not base_url or not webhook_key:
        print(f"[AUCTION WEBHOOK] Missing BOT_WEBHOOK_URL/WEBHOOK_BASE_URL or BOT_WEBHOOK_KEY for {webhook_path}")
        return False

    try:
        response = requests.post(
            f"{base_url}{webhook_path}",
            json=payload,
            headers={"Authorization": webhook_key},
            timeout=timeout
        )
        print(f"[AUCTION WEBHOOK] {webhook_path} -> {response.status_code}")
        return response.ok
    except Exception as e:
        print(f"[AUCTION WEBHOOK] Failed {webhook_path}: {e}")
        return False


@app.route("/api/auction/cancel", methods=["POST"])
def cancel_auction():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    message_id = request.form.get("message_id")
    reason = request.form.get("reason") or "No reason provided."

    if not message_id:
        return "Missing message_id", 400

    # Update auction status to 'cancelled'
    client= get_db()
    col = client["hayday"]["auctions"]
    auction = col.find_one({"message_id": int(message_id)})
    if not auction:
        return "Auction not found", 404

    col.update_one({"_id": auction["_id"]}, {"$set": {"status": "cancelled"}})

    # Notify bot to delete the Discord message and log.
    _notify_auction_bot("/webhook/cancel-auction", {
        "message_id": message_id,
        "reason": reason,
    })

    return redirect("/auction-dashboard")



@app.route("/api/auction/<message_id>/bids")
def get_auction_bids(message_id):
    if not is_staff():
        return "Unauthorized", 403

    client= get_db()
    auction = client["hayday"]["auctions"].find_one({"message_id": int(message_id)})
    if not auction or "bid_logs" not in auction:
        return jsonify([])

    user_col = client["Website"]["usernames"]

    output = []
    user_ids = [str(bid["user_id"]) for bid in auction["bid_logs"]]
    user_map = {
        u["_id"]: u for u in user_col.find({"_id": {"$in": user_ids}})
    }

    for bid in auction["bid_logs"]:
        output.append({
            "user_display": user_map.get(str(bid["user_id"]), {}).get("display_name", str(bid["user_id"])),
            "user_id": str(bid["user_id"]),  # 鈫?change from int() to str()
            "amount": bid["amount"],
            "timestamp": bid["timestamp"],
        })


    print("FINAL BIDS RETURNED:", output)

    return jsonify(output)

    

@app.route("/api/auction/edit", methods=["POST"])
def edit_auction():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    def safe_int(val):
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    try:
        data = request.form.to_dict()
        message_id = int(data.get("message_id"))

        client= get_db()
        col = client["hayday"]["auctions"]
        existing = col.find_one({"message_id": message_id})
        if not existing:
            return "Auction not found", 404

        update_fields = {}
        for k, v in data.items():
            if k in ("message_id", "csrf_token"):
                continue
            if k in ("quantity", "current_bid", "min_increment"):
                parsed = safe_int(v)
                if parsed is not None:
                    update_fields[k] = parsed
            else:
                update_fields[k] = v

        image_url = data.get("image_url", "").strip()
        if not image_url and "image_url" in existing:
            image_url = existing["image_url"]
        update_fields["image_url"] = image_url

        col.update_one({"message_id": message_id}, {"$set": update_fields})

        # Notify bot.
        _notify_auction_bot("/webhook/refresh-auction", {"message_id": message_id})
        print("[EDIT] Sent webhook for:", message_id)
        return redirect("/auction-dashboard")

    except Exception as e:
        return f"Error: {e}", 500
    
 
@app.route("/api/auction/remove-buyout", methods=["POST"])
def remove_buyout():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403
        
    message_id = request.form.get("message_id")

    if not message_id:
        return "Missing message_id", 400

    client= get_db()
    col = client["hayday"]["auctions"]
    result = col.update_one(
        {"message_id": int(message_id)},
        {"$unset": {"buyout_offer": ""}}
    )
    print(f"[BUYOUT REMOVE] message_id={message_id} matched={result.matched_count} modified={result.modified_count}")

    _notify_auction_bot("/webhook/refresh-auction", {"message_id": message_id})

    return redirect("/auction-dashboard")


@app.route("/api/auction/remove-image", methods=["POST"])
def remove_auction_image():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403
        
    message_id = request.form.get("message_id")

    client= get_db()
    db = client["hayday"]["auctions"]
    result = db.update_one(
        {"message_id": int(message_id)},
        {"$unset": {"image_url": ""}}
    )
    print(f"[REMOVE-IMAGE] Result: matched={result.matched_count} modified={result.modified_count}")

    _notify_auction_bot("/webhook/refresh-auction", {"message_id": message_id})

    return redirect("/auction-dashboard")



@app.route("/api/auction/end", methods=["POST"])
def end_auction_now():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    message_id = request.form.get("message_id")
    if not message_id:
        return "Missing message_id", 400

    client= get_db()
    col = client["hayday"]["auctions"]
    auction = col.find_one({"message_id": int(message_id)})
    if not auction:
        return "Auction not found", 404

    # Force end by making it expired
    col.update_one({"_id": auction["_id"]}, {
        "$set": {"end_time": datetime.utcnow() - timedelta(seconds=1)}
    })

    # Trigger full auction end logic via bot webhook.
    _notify_auction_bot("/webhook/end-auction", {"message_id": message_id})

    return redirect("/auction-dashboard")



@app.route("/api/auction/<message_id>/remove-bid", methods=["POST"])
def remove_auction_bid(message_id):
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    user_id = request.form.get("user_id")
    print("[REMOVE BID] Raw user_id from form:", user_id)

    if not user_id:
        return "Missing user_id", 400

    try:
        user_id_int = int(user_id)
    except ValueError:
        return "Invalid user_id format", 400

    print("[REMOVE BID] Target user_id to remove (int):", user_id_int)

    client= get_db()
    auctions = client["hayday"]["auctions"]
    auction = auctions.find_one({"message_id": int(message_id)})

    if not auction:
        print("[REMOVE BID] 鉂?Auction not found.")
        return "Auction not found", 404

    bid_logs = auction.get("bid_logs", [])
    print(f"[REMOVE BID] Found {len(bid_logs)} bids before removal")

    for bid in bid_logs:
        print(f"[COMPARE] bid.user_id={bid['user_id']} (type: {type(bid['user_id'])}) vs {user_id_int} (type: {type(user_id_int)})")

    updated_logs = [bid for bid in bid_logs if str(bid["user_id"]) != str(user_id_int)]
    for bid in bid_logs:
        print(f"[CHECK] str({bid['user_id']}) = {str(bid['user_id'])}, form = {str(user_id_int)}")


    print(f"[REMOVE BID] Bids after removal: {len(updated_logs)}")

    if len(updated_logs) == len(bid_logs):
        print("[REMOVE BID] ⚠️ No bid found for this user_id - nothing removed")

    # Recalculate highest bid
    if updated_logs:
        updated_logs.sort(key=lambda x: x["timestamp"])
        last = updated_logs[-1]
        current_bid = last["amount"]
        highest_bidder = last["user_id"]
    else:
        current_bid = auction.get("starting_bid", 0)
        highest_bidder = None

    result = auctions.update_one(
        {"message_id": int(message_id)},
        {"$set": {
            "bid_logs": updated_logs,
            "current_bid": current_bid,
            "highest_bidder": highest_bidder
        }}
    )

    print(f"[REMOVE BID] Mongo matched: {result.matched_count}, modified: {result.modified_count}")
    print(f"[REMOVE BID] New highest_bidder: {highest_bidder}, current_bid: {current_bid}")

    _notify_auction_bot("/webhook/refresh-auction", {"message_id": message_id})
    return redirect("/auction-dashboard")


@app.route("/api/auction/unban", methods=["POST"])
def unban_auction_user():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    user_id = (request.form.get("user_id") or "").strip()
    if not user_id:
        return "Missing user_id", 400

    AUCTION_BANNED_ROLE_ID = 1379087489779630121
    auction_banned_role_ids = [AUCTION_BANNED_ROLE_ID, str(AUCTION_BANNED_ROLE_ID)]

    client = get_db()
    user_col = client["Website"]["usernames"]
    result = user_col.update_one(
        {"_id": user_id},
        {"$pull": {"roles": {"$in": auction_banned_role_ids}}}
    )
    print(f"[AUCTION UNBAN] user_id={user_id} matched={result.matched_count} modified={result.modified_count}")

    _notify_auction_bot("/webhook/auction-unban", {"user_id": user_id})
    return redirect("/auction-dashboard")



@app.route("/webhook/refresh-auction", methods=["POST"])
def refresh_auction_webhook():
    if request.headers.get("X-Webhook-Secret") != os.getenv("BOT_WEBHOOK_KEY"):
        return "Forbidden", 403

    data = request.get_json()
    message_id = data.get("message_id")

    # TODO: Optionally add logic to notify the bot or update cache, etc.
    print(f"[Webhook] Refresh auction triggered for message ID: {message_id}")

    return "OK", 200

@app.route("/admin/refund", methods=["POST"])
def refund_purchase():
    if not is_admin():  # optionally require stricter access than is_staff()
        return "Unauthorized", 403

    purchase_id = request.form.get("purchase_id")
    if not purchase_id:
        return "Invalid request", 400

    client= get_db()
    purchases_col = client["Economy"]["Purchases"]
    eco_col = client["Economy"]["Users"]

    purchase = purchases_col.find_one({"_id": ObjectId(purchase_id)})
    if not purchase or purchase.get("refunded"):
        return "Already refunded or not found", 400

    # Refund coins
    eco_col.update_one(
        {"_id": int(purchase["user_id"])},
        {"$inc": {"coins": purchase["price"]}}
    )

    # Revert item usage if tracked
    item_id = purchase["item"]
    if item_id in ["mute_other_20m", "mute_other_30m", "mute_other_45m", "mute_other_60m", "ping_storm", "ghost_ping", "lore_post"]:
        eco_col.update_one(
            {"_id": int(purchase["user_id"])},
            {"$inc": {f"{item_id}_used": -1}}
        )
    elif item_id in ["trivia_hint", "double_daily", "boosted_trivia", "mute_immunity"]:
        eco_col.update_one(
            {"_id": int(purchase["user_id"])},
            {"$set": {item_id: False}}
        )

    purchases_col.update_one(
        {"_id": ObjectId(purchase_id)},
        {"$set": {"refunded": True, "refunded_at": datetime.utcnow()}}
    )

    flash("✅ Purchase refunded successfully.", "success")
    return redirect(url_for("view_purchases"))



@app.route("/logout")
def logout():
    next_page = request.args.get("next", "/")

    # Clear all session data
    session.clear()

    # Create a response to redirect and remove the cookie
    resp = redirect(next_page)
    resp.delete_cookie(
        key=app.config["SESSION_COOKIE_NAME"],  # Flask 2.3+ way
        path="/",
        domain=None  # or set to your domain if you explicitly set it in config
    )

    return resp




@app.route("/terms")
def terms_page():
    year = datetime.now().year
    return render_template("terms.html", year=year)


@app.route("/privacy")
def privacy_page():
    resp = make_response(render_template("privacy.html"))
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp



@app.route("/staff")
def staff_panel():
    client= get_db()
    staff = list(client["Website"]["Staff"].find())
    year = datetime.now(timezone.utc).year
    return render_template("staff.html", staff=staff, year=year)


def _gambling_username_map(user_ids):
    wanted_ids = sorted({str(user_id) for user_id in user_ids if user_id is not None})
    if not wanted_ids:
        return {}

    usernames_col = get_db("Website")["usernames"]
    docs = list(
        usernames_col.find(
            {"_id": {"$in": wanted_ids}},
            {"display_name": 1, "username": 1},
        )
    )
    return {
        str(doc.get("_id")): (doc.get("display_name") or doc.get("username") or str(doc.get("_id")))
        for doc in docs
    }


def _parse_gambling_dashboard_date(value):
    raw_value = (value or "").strip()
    if not raw_value:
        return "", None

    try:
        parsed = date.fromisoformat(raw_value)
    except ValueError:
        return "", None
    return parsed.isoformat(), parsed


def _gambling_dashboard_date_bounds(start_value=None, end_value=None):
    start_raw, start_date_value = _parse_gambling_dashboard_date(start_value)
    end_raw, end_date_value = _parse_gambling_dashboard_date(end_value)

    start_dt = (
        datetime.combine(start_date_value, datetime.min.time(), tzinfo=timezone.utc)
        if start_date_value
        else None
    )
    end_dt = (
        datetime.combine(end_date_value + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        if end_date_value
        else None
    )
    return start_raw, end_raw, start_dt, end_dt


def _gambling_result_percentages(wins=0, losses=0):
    wins = int(wins or 0)
    losses = int(losses or 0)
    decided_total = wins + losses
    if decided_total <= 0:
        return 0.0, 0.0
    return round((wins / decided_total) * 100, 1), round((losses / decided_total) * 100, 1)


def _gambling_coin_side_percentages(head_count=0, tail_count=0):
    head_count = int(head_count or 0)
    tail_count = int(tail_count or 0)
    total = head_count + tail_count
    if total <= 0:
        return 0.0, 0.0
    return round((head_count / total) * 100, 1), round((tail_count / total) * 100, 1)


def _gambling_matching_user_ids(search_term):
    normalized = (search_term or "").strip()
    if not normalized or normalized.isdigit():
        return []

    usernames_col = get_db("Website")["usernames"]
    docs = list(
        usernames_col.find(
            {
                "$or": [
                    {"display_name": {"$regex": re.escape(normalized), "$options": "i"}},
                    {"username": {"$regex": re.escape(normalized), "$options": "i"}},
                ]
            },
            {"_id": 1},
        )
    )
    return [str(doc.get("_id")) for doc in docs if doc.get("_id") is not None]


def _build_coinflip_events(*, search_term="", result_filter="all", start_dt=None, end_dt=None, page=1, per_page=12):
    econ_db = get_db("Economy")
    source_mode = "ledger"
    normalized_search = (search_term or "").strip()
    normalized_result = (result_filter or "all").strip().lower()
    ts_query = {}
    if start_dt:
        ts_query["$gte"] = start_dt
    if end_dt:
        ts_query["$lt"] = end_dt
    matching_user_ids = _gambling_matching_user_ids(normalized_search)
    matching_numeric_user_ids = [
        int(user_id)
        for user_id in matching_user_ids
        if str(user_id).isdigit()
    ]

    collection_names = set(econ_db.list_collection_names())
    if "coinflip_logs" in collection_names:
        source_mode = "collection"
        query = {}
        if ts_query:
            query["ts"] = ts_query
        if normalized_result != "all":
            query["result"] = normalized_result
        if normalized_search:
            search_clauses = [{"username": {"$regex": re.escape(normalized_search), "$options": "i"}}]
            if normalized_search.isdigit():
                numeric_search = int(normalized_search)
                search_clauses.append({"user_id": numeric_search})
                search_clauses.append({"user_id": normalized_search})
            elif matching_numeric_user_ids:
                search_clauses.append({"user_id": {"$in": matching_numeric_user_ids}})
            if search_clauses:
                query["$or"] = search_clauses

        coinflip_col = econ_db["coinflip_logs"]
        total = coinflip_col.count_documents(query)
        stats_rows = list(coinflip_col.aggregate([
            {"$match": query},
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "wins": {"$sum": {"$cond": [{"$eq": ["$result", "win"]}, 1, 0]}},
                "losses": {"$sum": {"$cond": [{"$eq": ["$result", "loss"]}, 1, 0]}},
                "heads": {"$sum": {"$cond": [{
                    "$in": [{"$toLower": {"$ifNull": ["$flip_result", ""]}}, ["head", "heads"]]
                }, 1, 0]}},
                "tails": {"$sum": {"$cond": [{
                    "$in": [{"$toLower": {"$ifNull": ["$flip_result", ""]}}, ["tail", "tails"]]
                }, 1, 0]}},
                "wagered": {"$sum": {"$ifNull": ["$bet", 0]}},
                "paid_out": {"$sum": {"$ifNull": ["$payout", 0]}},
                "profit_paid": {"$sum": {"$cond": [
                    {"$gt": [{"$ifNull": ["$payout", 0]}, {"$ifNull": ["$bet", 0]}]},
                    {"$subtract": [{"$ifNull": ["$payout", 0]}, {"$ifNull": ["$bet", 0]}]},
                    0,
                ]}},
            }},
        ]))
        stats = stats_rows[0] if stats_rows else {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "heads": 0,
            "tails": 0,
            "wagered": 0,
            "paid_out": 0,
            "profit_paid": 0,
        }

        coinflip_logs = list(
            coinflip_col.find(query)
            .sort("ts", -1)
            .skip((max(1, int(page)) - 1) * per_page)
            .limit(per_page)
        )

        usernames = _gambling_username_map(doc.get("user_id") for doc in coinflip_logs)
        paged_logs = []
        for doc in coinflip_logs:
            user_id = doc.get("user_id")
            payout = int(doc.get("payout", 0) or 0)
            bet = int(doc.get("bet", 0) or 0)
            paged_logs.append({
                "event_id": str(doc.get("_id")),
                "storage_mode": "collection",
                "ts": doc.get("ts"),
                "user_id": user_id,
                "username": usernames.get(str(user_id)) or doc.get("username") or str(user_id),
                "result": (doc.get("result") or "unknown").lower(),
                "bet": bet,
                "payout": payout,
                "profit": max(0, payout - bet) if payout else 0,
                "choice": doc.get("choice"),
                "flip_result": doc.get("flip_result"),
                "balance_after": doc.get("balance_after"),
                "source": doc.get("source") or "coinflip",
                "admin_refunded_at": doc.get("admin_refunded_at"),
                "admin_reviewed_at": doc.get("admin_reviewed_at"),
                "can_refund": (doc.get("result") or "").lower() == "loss" and not doc.get("admin_refunded_at"),
            })
        return paged_logs, stats, source_mode, total

    ledger_query = {"source": {"$in": ["coinflip:wager", "coinflip:win"]}}
    if ts_query:
        ledger_query["ts"] = ts_query
    if normalized_search:
        if normalized_search.isdigit():
            ledger_query["user_id"] = int(normalized_search)
        elif matching_numeric_user_ids:
            ledger_query["user_id"] = {"$in": matching_numeric_user_ids}
        else:
            stats = {
                "total": 0,
                "wins": 0,
                "losses": 0,
                "heads": 0,
                "tails": 0,
                "wagered": 0,
                "paid_out": 0,
                "profit_paid": 0,
            }
            return [], stats, source_mode, 0

    ledger_entries = list(
        econ_db["coin_ledger"]
        .find(ledger_query)
        .sort("ts", 1)
    )

    pending_wagers = defaultdict(list)
    events = []
    for entry in ledger_entries:
        user_id = entry.get("user_id")
        source = entry.get("source")
        meta = entry.get("meta") or {}

        if source == "coinflip:wager":
            pending_wagers[user_id].append(entry)
            continue

        if source != "coinflip:win":
            continue

        bet = int(meta.get("bet") or max(0, int(entry.get("amount", 0) or 0) // 2))
        wager = None
        for index in range(len(pending_wagers[user_id]) - 1, -1, -1):
            candidate = pending_wagers[user_id][index]
            if int(candidate.get("amount", 0) or 0) == bet:
                wager = pending_wagers[user_id].pop(index)
                break

        payout = int(entry.get("amount", 0) or 0)
        events.append({
            "event_id": str((wager or {}).get("_id") or entry.get("_id")),
            "storage_mode": "ledger",
            "ts": entry.get("ts") or (wager or {}).get("ts"),
            "user_id": user_id,
            "result": "win",
            "bet": bet,
            "payout": payout,
            "profit": max(0, payout - bet),
            "choice": meta.get("choice"),
            "flip_result": meta.get("flip_result"),
            "balance_after": entry.get("balance_after"),
            "source": "coinflip",
            "admin_refunded_at": (wager or {}).get("admin_refunded_at") or entry.get("admin_refunded_at"),
            "admin_reviewed_at": (wager or {}).get("admin_reviewed_at") or entry.get("admin_reviewed_at"),
            "can_refund": False,
        })

    for user_id, wagers in pending_wagers.items():
        for wager in wagers:
            events.append({
                "event_id": str(wager.get("_id")),
                "storage_mode": "ledger",
                "ts": wager.get("ts"),
                "user_id": user_id,
                "result": "loss",
                "bet": int(wager.get("amount", 0) or 0),
                "payout": 0,
                "profit": 0,
                "choice": None,
                "flip_result": None,
                "balance_after": wager.get("balance_after"),
                "source": "coinflip",
                "admin_refunded_at": wager.get("admin_refunded_at"),
                "admin_reviewed_at": wager.get("admin_reviewed_at"),
                "can_refund": not wager.get("admin_refunded_at"),
            })

    if normalized_result != "all":
        events = [event for event in events if event.get("result") == normalized_result]

    events.sort(
        key=lambda item: item.get("ts") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    total = len(events)
    stats = {
        "total": total,
        "wins": sum(1 for event in events if event.get("result") == "win"),
        "losses": sum(1 for event in events if event.get("result") == "loss"),
        "heads": sum(1 for event in events if str(event.get("flip_result") or "").lower() in {"head", "heads"}),
        "tails": sum(1 for event in events if str(event.get("flip_result") or "").lower() in {"tail", "tails"}),
        "wagered": sum(int(event.get("bet", 0) or 0) for event in events),
        "paid_out": sum(int(event.get("payout", 0) or 0) for event in events),
        "profit_paid": sum(int(event.get("profit", 0) or 0) for event in events),
    }
    page_start = (max(1, int(page)) - 1) * per_page
    paged_logs = events[page_start:page_start + per_page]
    usernames = _gambling_username_map(log.get("user_id") for log in paged_logs)
    for log in paged_logs:
        log["username"] = usernames.get(str(log.get("user_id"))) or str(log.get("user_id"))
    return paged_logs, stats, source_mode, total


def _gambling_credit_user(user_id, amount, *, source, meta=None):
    user_id = int(user_id)
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Refund amount must be positive")

    economy_db = get_db("Economy")
    users_col = economy_db["Users"]
    ledger_col = economy_db["coin_ledger"]

    user_doc = users_col.find_one_and_update(
        {"_id": user_id},
        {"$inc": {"coins": amount}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    new_balance = int((user_doc or {}).get("coins", 0))

    actor_id = session.get("discord_id")
    ledger_col.insert_one({
        "user_id": user_id,
        "type": "credit",
        "amount": amount,
        "balance_after": new_balance,
        "source": source,
        "actor_id": int(actor_id) if str(actor_id).isdigit() else None,
        "related_user_id": None,
        "meta": meta or {},
        "ts": datetime.now(timezone.utc),
    })
    return new_balance


BLACKJACK_SUITS = [
    ("spades", "S"),
    ("hearts", "H"),
    ("diamonds", "D"),
    ("clubs", "C"),
]
BLACKJACK_RANK_VALUES = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
    "A": 11,
}
BLACKJACK_TABLE_POLL_SECONDS = 1
BLACKJACK_MAX_BET = 250000
BLACKJACK_DEALER_ID = 1332629757828792450
BLACKJACK_DEALER_NAME = "Holy Moly"
BLACKJACK_DEFAULT_TURN_TIME_SECONDS = 60
BLACKJACK_BETTING_WINDOW_SECONDS = 20
BLACKJACK_IDLE_CLOSE_SECONDS = 300
BLACKJACK_CHAT_LIMIT = 80


def _bj_now():
    return datetime.now(timezone.utc)


def _bj_as_utc(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _bj_tables_col():
    return get_db("Economy")["blackjack_tables"]


def _bj_users_col():
    return get_db("Economy")["Users"]


def _bj_logs_col():
    return get_db("Economy")["blackjack_logs"]


def _bj_action_logs_col():
    return get_db("Economy")["blackjack_action_logs"]


def _bj_reports_col():
    return get_db("Economy")["blackjack_reports"]


def _bj_ledger_col():
    return get_db("Economy")["coin_ledger"]


def _bj_make_shoe(deck_count=4):
    shoe = []
    for _ in range(max(1, int(deck_count))):
        for suit, suit_code in BLACKJACK_SUITS:
            for rank, value in BLACKJACK_RANK_VALUES.items():
                shoe.append({
                    "rank": rank,
                    "suit": suit,
                    "suit_code": suit_code,
                    "value": value,
                    "label": f"{rank}{suit_code}",
                })
    random.shuffle(shoe)
    return shoe


def _bj_hand_state(cards):
    total = sum(int(card.get("value", 0)) for card in cards)
    aces = sum(1 for card in cards if card.get("rank") == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    soft = any(card.get("rank") == "A" for card in cards) and total <= 21 and sum(
        int(card.get("value", 0)) for card in cards
    ) != total
    blackjack = len(cards) == 2 and total == 21
    busted = total > 21
    return {
        "total": total,
        "soft": soft,
        "blackjack": blackjack,
        "busted": busted,
    }


def _bj_make_hand(cards):
    hand = {"cards": cards}
    hand.update(_bj_hand_state(cards))
    hand.setdefault("stood", False)
    hand.setdefault("result", None)
    hand.setdefault("payout", 0)
    hand.setdefault("bet_amount", 0)
    hand.setdefault("doubled", False)
    hand.setdefault("split_hand", False)
    return hand


def _bj_turn_time_seconds(value):
    try:
        seconds = int(value or BLACKJACK_DEFAULT_TURN_TIME_SECONDS)
    except (TypeError, ValueError):
        seconds = BLACKJACK_DEFAULT_TURN_TIME_SECONDS
    return max(10, min(seconds, 300))


def _bj_draw(table):
    deck = table.setdefault("deck", [])
    if not deck:
        deck.extend(_bj_make_shoe(table.get("shoe_count", 4)))
    return deck.pop()


def _bj_user_profile(user_id):
    user_id = int(user_id)
    profile = get_db("Website")["usernames"].find_one(
        {"_id": str(user_id)},
        {"display_name": 1, "username": 1, "avatar": 1},
    ) or {}
    return {
        "username": profile.get("display_name") or profile.get("username") or f"User {str(user_id)[-4:]}",
        "avatar_url": profile.get("avatar", "https://cdn.discordapp.com/embed/avatars/0.png"),
    }


def _bj_dealer_profile():
    try:
        profile = _bj_user_profile(BLACKJACK_DEALER_ID)
    except Exception:
        profile = {
            "username": BLACKJACK_DEALER_NAME,
            "avatar_url": "https://cdn.discordapp.com/embed/avatars/0.png",
        }

    profile["username"] = profile.get("username") or BLACKJACK_DEALER_NAME
    return profile


def _bj_current_balance(user_id):
    doc = _bj_users_col().find_one({"_id": int(user_id)}, {"coins": 1}) or {}
    return int(doc.get("coins", 0) or 0)


def _bj_trim_chat(table):
    chat = list(table.get("chat", []))
    if len(chat) > BLACKJACK_CHAT_LIMIT:
        chat = chat[-BLACKJACK_CHAT_LIMIT:]
    table["chat"] = chat


def _bj_add_chat_message(table, *, kind, text, user_id=None, username=None, avatar_url=None):
    chat = list(table.get("chat", []))
    chat.append({
        "id": secrets.token_hex(6),
        "kind": kind,
        "text": (text or "").strip()[:300],
        "user_id": int(user_id) if user_id is not None else None,
        "username": username,
        "avatar_url": avatar_url,
        "ts": _bj_now(),
    })
    table["chat"] = chat[-BLACKJACK_CHAT_LIMIT:]


def _bj_schedule_start(table, *, seconds=BLACKJACK_BETTING_WINDOW_SECONDS, force=False):
    if table.get("phase") == "player_turns":
        return
    if not table.get("players"):
        table["phase"] = "lobby"
        table["status"] = "waiting"
        table["auto_start_at"] = None
        table["auto_redeal_at"] = None
        table["message"] = "Waiting for players to join the table."
        return

    seconds = max(5, int(seconds or BLACKJACK_BETTING_WINDOW_SECONDS))
    target_time = _bj_now() + timedelta(seconds=seconds)
    if force or not isinstance(table.get("auto_start_at"), datetime):
        table["auto_start_at"] = target_time
    table["auto_redeal_at"] = None
    table["phase"] = "betting"
    table["status"] = "waiting"
    table["message"] = f"Betting is open. Place bets in the next {seconds} seconds."


def _bj_idle_should_close(table, *, now=None):
    if table.get("phase") in {"player_turns", "settled"}:
        return False
    players = table.get("players", [])
    observers = table.get("observers", [])
    if not players and not observers:
        return True
    if any(int(player.get("reserved_bet", 0) or 0) > 0 for player in players):
        return False
    now = now or _bj_now()
    updated_at = _bj_as_utc(table.get("updated_at"))
    created_at = _bj_as_utc(table.get("created_at"))
    reference = updated_at or created_at
    if not reference:
        return False
    return (now - reference).total_seconds() >= BLACKJACK_IDLE_CLOSE_SECONDS


def _bj_finalize_betting_window(table):
    removed_players = []
    kept_players = []
    for player in table.get("players", []):
        if int(player.get("bet", 0) or 0) > 0:
            kept_players.append(player)
            continue
        removed_players.append(player)
        _bj_move_player_to_observers(
            table,
            player,
            reason=f"{player.get('username')} missed the betting window and moved to observer.",
        )
    table["players"] = kept_players
    table["auto_start_at"] = None
    if not kept_players:
        table["phase"] = "lobby"
        table["status"] = "waiting"
        table["message"] = "Betting window closed. No seated players were ready."
        return False, removed_players
    return True, removed_players


def _bj_all_seated_players_ready(table):
    players = table.get("players", [])
    return bool(players) and all(int(player.get("bet", 0) or 0) > 0 for player in players)


def _bj_debit_user(user_id, amount, *, source, meta=None):
    user_id = int(user_id)
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Wager amount must be positive")

    user_doc = _bj_users_col().find_one_and_update(
        {"_id": user_id, "coins": {"$gte": amount}},
        {"$inc": {"coins": -amount}},
        return_document=ReturnDocument.AFTER,
    )
    if not user_doc:
        return None

    new_balance = int((user_doc or {}).get("coins", 0))
    actor_id = session.get("discord_id")
    _bj_ledger_col().insert_one({
        "user_id": user_id,
        "type": "debit",
        "amount": amount,
        "balance_after": new_balance,
        "source": source,
        "actor_id": int(actor_id) if str(actor_id).isdigit() else None,
        "related_user_id": None,
        "meta": meta or {},
        "ts": _bj_now(),
    })
    return new_balance


def _bj_credit_user(user_id, amount, *, source, meta=None):
    return _gambling_credit_user(user_id, amount, source=source, meta=meta)


def _bj_find_player(table, user_id):
    wanted = int(user_id)
    for index, player in enumerate(table.get("players", [])):
        if int(player.get("user_id", 0)) == wanted:
            return index, player
    return None, None


def _bj_find_observer(table, user_id):
    wanted = int(user_id)
    for index, observer in enumerate(table.get("observers", [])):
        if int(observer.get("user_id", 0)) == wanted:
            return index, observer
    return None, None


def _bj_make_seat_member(profile, *, min_bet, session_start_balance=None, waiting_status="waiting"):
    user_id = int(profile.get("user_id") or profile.get("_id") or 0)
    return {
        "user_id": user_id,
        "username": profile["username"],
        "avatar_url": profile["avatar_url"],
        "joined_at": _bj_now(),
        "session_start_balance": int(session_start_balance if session_start_balance is not None else _bj_current_balance(user_id)),
        "bet": 0,
        "next_bet": 0,
        "reserved_bet": 0,
        "auto_bet_enabled": False,
        "auto_bet_amount": int(min_bet),
        "hands": [],
        "active_hand_index": 0,
        "round_status": waiting_status,
    }


def _bj_make_observer(profile):
    user_id = int(profile.get("user_id") or profile.get("_id") or 0)
    return {
        "user_id": user_id,
        "username": profile["username"],
        "avatar_url": profile["avatar_url"],
        "joined_at": _bj_now(),
    }


def _bj_move_player_to_observers(table, player, *, reason=None):
    if not player:
        return
    table.setdefault("observers", [])
    observer_index, _ = _bj_find_observer(table, player.get("user_id"))
    observer = {
        "user_id": int(player.get("user_id", 0) or 0),
        "username": player.get("username"),
        "avatar_url": player.get("avatar_url"),
        "joined_at": _bj_now(),
    }
    if observer_index is None:
        table["observers"].append(observer)
    else:
        table["observers"][observer_index] = observer
    if reason:
        _bj_add_chat_message(
            table,
            kind="system",
            text=reason,
            user_id=player.get("user_id"),
            username=player.get("username"),
            avatar_url=player.get("avatar_url"),
        )


def _bj_active_hand(player):
    hands = player.get("hands") or []
    hand_index = int(player.get("active_hand_index", 0) or 0)
    if not hands:
        return None
    hand_index = max(0, min(hand_index, len(hands) - 1))
    player["active_hand_index"] = hand_index
    return hands[hand_index]


def _bj_next_playable_hand_index(player):
    hands = player.get("hands") or []
    for index, hand in enumerate(hands):
        if not (hand.get("busted") or hand.get("stood") or hand.get("blackjack")):
            return index
    return None


def _bj_insurance_offer(player):
    hands = player.get("hands") or []
    if not hands:
        return 0
    return max(0, int(hands[0].get("bet_amount", 0) or 0) // 2)


def _bj_player_needs_insurance_choice(player):
    return player.get("insurance_state") == "pending" and _bj_insurance_offer(player) > 0


def _bj_player_is_done(player):
    return _bj_next_playable_hand_index(player) is None


def _bj_refresh_player_state(player):
    hands = player.get("hands") or []
    if not hands:
        player["round_status"] = "waiting"
        return

    for hand in hands:
        hand.update(_bj_hand_state(hand.get("cards", [])))
        if hand.get("blackjack") or hand.get("busted") or hand.get("total", 0) >= 21:
            hand["stood"] = True

    next_index = _bj_next_playable_hand_index(player)
    if next_index is None:
        player["round_status"] = "done"
        player["active_hand_index"] = min(int(player.get("active_hand_index", 0) or 0), max(len(hands) - 1, 0))
    else:
        player["round_status"] = "playing"
        player["active_hand_index"] = next_index


def _bj_assign_turn(table, *, preserve_deadline=False):
    previous_user_id = int(table.get("current_turn_user_id", 0) or 0) or None
    previous_deadline = _bj_as_utc(table.get("turn_deadline_at"))
    table["current_turn_index"] = None
    table["current_turn_user_id"] = None
    table["turn_deadline_at"] = None
    if table.get("phase") not in {"player_turns", "insurance"}:
        return None

    for index, player in enumerate(table.get("players", [])):
        if table.get("phase") == "insurance":
            if not _bj_player_needs_insurance_choice(player):
                continue
        else:
            _bj_refresh_player_state(player)
            if player.get("round_status") != "playing":
                continue

        if table.get("phase") == "insurance" or player.get("round_status") == "playing":
            table["current_turn_index"] = index
            table["current_turn_user_id"] = int(player.get("user_id"))
            if preserve_deadline and previous_user_id == int(player.get("user_id")) and previous_deadline:
                table["turn_deadline_at"] = previous_deadline
            else:
                table["turn_deadline_at"] = _bj_now() + timedelta(seconds=_bj_turn_time_seconds(table.get("turn_time_seconds")))
            table["message"] = (
                f"{player.get('username')} can take insurance."
                if table.get("phase") == "insurance"
                else f"{player.get('username')} is up."
            )
            return index
    return None


def _bj_serialize_hand(hand):
    return {
        "cards": [dict(card) for card in hand.get("cards", [])],
        "total": int(hand.get("total", 0) or 0),
        "soft": bool(hand.get("soft")),
        "blackjack": bool(hand.get("blackjack")),
        "busted": bool(hand.get("busted")),
        "stood": bool(hand.get("stood")),
        "result": hand.get("result"),
        "payout": int(hand.get("payout", 0) or 0),
        "bet_amount": int(hand.get("bet_amount", 0) or 0),
        "doubled": bool(hand.get("doubled")),
        "split_hand": bool(hand.get("split_hand")),
    }


def _bj_dealer_view(table):
    hand = _bj_make_hand(list(table.get("dealer_hand", [])))
    cards = [_bj_serialize_hand(hand)["cards"][i] for i in range(len(hand.get("cards", [])))]
    hide_hole = table.get("phase") in {"player_turns", "insurance"} and len(cards) >= 2
    if hide_hole:
        cards = [cards[0], {"rank": "?", "suit": "hidden", "suit_code": "?", "value": 0, "label": "??"}]
        visible = _bj_make_hand([table.get("dealer_hand", [])[0]])
        return {
            "cards": cards,
            "total": visible.get("total", 0),
            "soft": visible.get("soft", False),
            "blackjack": False,
            "busted": False,
            "hole_hidden": True,
        }
    return {
        "cards": cards,
        "total": hand.get("total", 0),
        "soft": hand.get("soft", False),
        "blackjack": hand.get("blackjack", False),
        "busted": hand.get("busted", False),
        "hole_hidden": False,
    }


def _bj_table_state(table, viewer_id=None):
    viewer_id = int(viewer_id) if str(viewer_id).isdigit() else None
    viewer_balance = _bj_current_balance(viewer_id) if viewer_id is not None else None
    players = []
    for player in table.get("players", []):
        serialized_player = {
            "user_id": int(player.get("user_id")),
            "username": player.get("username"),
            "avatar_url": player.get("avatar_url"),
            "bet": int(player.get("bet", 0) or 0),
            "next_bet": int(player.get("next_bet", 0) or 0),
            "reserved_bet": int(player.get("reserved_bet", 0) or 0),
            "insurance_bet": int(player.get("insurance_bet", 0) or 0),
            "insurance_state": player.get("insurance_state"),
            "active_hand_index": int(player.get("active_hand_index", 0) or 0),
            "round_status": player.get("round_status", "waiting"),
            "auto_bet_enabled": bool(player.get("auto_bet_enabled")),
            "auto_bet_amount": int(player.get("auto_bet_amount", table.get("min_bet", 1)) or table.get("min_bet", 1)),
            "is_owner": int(player.get("user_id")) == int(table.get("owner_id", 0)),
            "is_turn": viewer_id is not None and int(player.get("user_id")) == int(table.get("current_turn_user_id") or 0),
            "hands": [_bj_serialize_hand(hand) for hand in player.get("hands", [])],
        }
        if viewer_id is not None and int(player.get("user_id", 0)) == viewer_id:
            session_start_balance = int(player.get("session_start_balance", viewer_balance or 0) or 0)
            serialized_player["session_start_balance"] = session_start_balance
            serialized_player["session_pnl"] = int((viewer_balance or 0) - session_start_balance)
        players.append(serialized_player)
    observers = [
        {
            "user_id": int(observer.get("user_id", 0) or 0),
            "username": observer.get("username"),
            "avatar_url": observer.get("avatar_url"),
            "is_owner": int(observer.get("user_id", 0) or 0) == int(table.get("owner_id", 0) or 0),
        }
        for observer in table.get("observers", [])
    ]

    viewer_player = None
    for player in players:
        if viewer_id is not None and player["user_id"] == viewer_id:
            viewer_player = player
            break
    viewer_observer = None
    for observer in observers:
        if viewer_id is not None and observer["user_id"] == viewer_id:
            viewer_observer = observer
            break

    return {
        "id": str(table.get("_id")),
        "name": table.get("name") or "Blackjack Table",
        "table_code": table.get("table_code"),
        "status": table.get("status", "waiting"),
        "phase": table.get("phase", "lobby"),
        "insurance_open": table.get("phase") == "insurance",
        "owner_id": int(table.get("owner_id", 0) or 0),
        "owner_name": table.get("owner_name"),
        "min_bet": int(table.get("min_bet", 1) or 1),
        "max_players": int(table.get("max_players", 5) or 5),
        "shoe_count": int(table.get("shoe_count", 4) or 4),
        "turn_time_seconds": _bj_turn_time_seconds(table.get("turn_time_seconds")),
        "message": table.get("message") or "",
        "current_turn_user_id": int(table.get("current_turn_user_id", 0) or 0) or None,
        "turn_deadline_at": _bj_as_utc(table.get("turn_deadline_at")).isoformat() if _bj_as_utc(table.get("turn_deadline_at")) else None,
        "auto_start_at": _bj_as_utc(table.get("auto_start_at")).isoformat() if _bj_as_utc(table.get("auto_start_at")) else None,
        "auto_redeal_at": _bj_as_utc(table.get("auto_redeal_at")).isoformat() if _bj_as_utc(table.get("auto_redeal_at")) else None,
        "dealer": _bj_dealer_view(table),
        "dealer_profile": _bj_dealer_profile(),
        "players": players,
        "observers": observers,
        "viewer_player": viewer_player,
        "viewer_observer": viewer_observer,
        "viewer_role": "player" if viewer_player else ("observer" if viewer_observer else "guest"),
        "chat": [
            {
                "id": message.get("id"),
                "kind": message.get("kind", "user"),
                "text": message.get("text", ""),
                "user_id": message.get("user_id"),
                "username": message.get("username"),
                "avatar_url": message.get("avatar_url"),
                "ts": _bj_as_utc(message.get("ts")).isoformat() if _bj_as_utc(message.get("ts")) else None,
            }
            for message in table.get("chat", [])
        ],
        "updated_at": _bj_as_utc(table.get("updated_at")).isoformat() if _bj_as_utc(table.get("updated_at")) else None,
        "poll_seconds": BLACKJACK_TABLE_POLL_SECONDS,
    }


def _bj_log_finished_hand(table, player, hand, dealer_hand):
    hand_bet = int(hand.get("bet_amount", 0) or 0)
    if hand_bet <= 0:
        return

    dealer_state = _bj_make_hand(list(dealer_hand))
    _bj_logs_col().insert_one({
        "user_id": int(player.get("user_id")),
        "username": player.get("username"),
        "table_id": str(table.get("_id")),
        "table_code": table.get("table_code"),
        "table_name": table.get("name"),
        "result": hand.get("result"),
        "total_wager": hand_bet,
        "payout": int(hand.get("payout", 0) or 0),
        "player_total": int(hand.get("total", 0) or 0),
        "dealer_total": int(dealer_state.get("total", 0) or 0),
        "player_cards": [card.get("label") for card in hand.get("cards", [])],
        "dealer_cards": [card.get("label") for card in dealer_hand],
        "split_used": len(player.get("hands", [])) > 1,
        "source": "web_blackjack",
        "ts": _bj_now(),
    })


def _bj_log_table_event(table, action, *, user_id=None, username=None, details=None, meta=None):
    if not table:
        return
    _bj_action_logs_col().insert_one({
        "table_id": str(table.get("_id")) if table.get("_id") else None,
        "table_code": table.get("table_code"),
        "table_name": table.get("name"),
        "owner_id": int(table.get("owner_id", 0) or 0) or None,
        "owner_name": table.get("owner_name"),
        "phase": table.get("phase"),
        "status": table.get("status"),
        "action": (action or "").strip().lower()[:60],
        "user_id": int(user_id) if user_id is not None and str(user_id).isdigit() else None,
        "username": (username or "").strip()[:120] or None,
        "details": (details or "").strip()[:500] or None,
        "meta": meta or {},
        "ts": _bj_now(),
    })


def _bj_finish_insurance_phase(table):
    if table.get("phase") != "insurance":
        return

    if _bj_assign_turn(table, preserve_deadline=True) is not None:
        return

    dealer_state = _bj_make_hand(list(table.get("dealer_hand", [])))
    if dealer_state.get("blackjack"):
        _bj_settle_round(table)
        return

    table["phase"] = "player_turns"
    if _bj_assign_turn(table) is None:
        _bj_settle_round(table)


def _bj_settle_round(table):
    if not table.get("dealer_hand"):
        return

    dealer_hand = list(table.get("dealer_hand", []))
    dealer_state = _bj_make_hand(dealer_hand)
    while dealer_state.get("total", 0) < 17:
        dealer_hand.append(_bj_draw(table))
        dealer_state = _bj_make_hand(dealer_hand)
    table["dealer_hand"] = dealer_hand

    for player in table.get("players", []):
        _bj_refresh_player_state(player)
        hands = player.get("hands") or []
        if not hands or int(player.get("reserved_bet", 0) or 0) <= 0:
            player["round_status"] = "waiting"
            continue

        insurance_bet = int(player.get("insurance_bet", 0) or 0)
        insurance_payout = 0
        if dealer_state.get("blackjack") and insurance_bet > 0:
            insurance_payout = insurance_bet * 3
            _bj_credit_user(
                player.get("user_id"),
                insurance_payout,
                source="blackjack:insurance",
                meta={
                    "table_id": str(table.get("_id")),
                    "table_name": table.get("name"),
                    "bet": insurance_bet,
                },
            )
            player["insurance_state"] = "won"
        elif insurance_bet > 0:
            player["insurance_state"] = "lost"

        for hand in hands:
            hand_bet = int(hand.get("bet_amount", 0) or 0)
            if hand_bet <= 0:
                continue

            result = "loss"
            payout = 0
            is_natural_blackjack = bool(hand.get("blackjack")) and not hand.get("split_hand")
            if is_natural_blackjack and dealer_state.get("blackjack"):
                result = "push"
                payout = hand_bet
            elif is_natural_blackjack:
                result = "blackjack"
                payout = hand_bet + ((hand_bet * 3) // 2)
            elif hand.get("busted"):
                result = "loss"
            elif dealer_state.get("busted"):
                result = "win"
                payout = hand_bet * 2
            elif hand.get("total", 0) > dealer_state.get("total", 0):
                result = "win"
                payout = hand_bet * 2
            elif hand.get("total", 0) == dealer_state.get("total", 0):
                result = "push"
                payout = hand_bet
            elif dealer_state.get("blackjack"):
                result = "dealer_blackjack"

            hand["result"] = result
            hand["payout"] = payout

            if payout > 0:
                _bj_credit_user(
                    player.get("user_id"),
                    payout,
                    source="blackjack:payout",
                    meta={
                        "table_id": str(table.get("_id")),
                        "table_name": table.get("name"),
                        "result": result,
                        "bet": hand_bet,
                    },
                )
            _bj_log_finished_hand(table, player, hand, dealer_hand)

        player["round_status"] = "done"
        player["reserved_bet"] = 0
        player["insurance_bet"] = 0
        staged_next_bet = int(player.get("next_bet", 0) or 0)
        auto_bet_enabled = bool(player.get("auto_bet_enabled"))
        auto_bet_amount = int(player.get("auto_bet_amount", 0) or 0)
        if staged_next_bet > 0:
            player["bet"] = staged_next_bet
        elif auto_bet_enabled and auto_bet_amount > 0:
            player["bet"] = auto_bet_amount
        else:
            player["bet"] = 0
        player["next_bet"] = 0

    table["phase"] = "settled"
    table["status"] = "waiting"
    table["current_turn_index"] = None
    table["current_turn_user_id"] = None
    table["turn_deadline_at"] = None
    table["settled_at"] = _bj_now()
    table["auto_redeal_at"] = None
    _bj_schedule_start(table, force=True)
    _bj_log_table_event(
        table,
        "round_settled",
        details=f"Dealer finished on {int(dealer_state.get('total', 0) or 0)}. Betting reopened.",
        meta={
            "dealer_total": int(dealer_state.get("total", 0) or 0),
            "dealer_blackjack": bool(dealer_state.get("blackjack")),
            "dealer_busted": bool(dealer_state.get("busted")),
        },
    )


def _bj_start_round(table):
    if table.get("phase") == "player_turns":
        return False, "A round is already in progress."

    active_players = []
    table["dealer_hand"] = []
    table["auto_start_at"] = None
    table["auto_redeal_at"] = None
    table["turn_deadline_at"] = None
    if len(table.get("deck", [])) < 52:
        table["deck"] = _bj_make_shoe(table.get("shoe_count", 4))

    for player in table.get("players", []):
        player["hands"] = []
        player["active_hand_index"] = 0
        player["reserved_bet"] = 0
        player["insurance_bet"] = 0
        player["insurance_state"] = "unavailable"
        player["round_status"] = "waiting"
        bet = int(player.get("bet", 0) or 0)
        if bet <= 0:
            continue

        new_balance = _bj_debit_user(
            player.get("user_id"),
            bet,
            source="blackjack:wager",
            meta={
                "table_id": str(table.get("_id")),
                "table_name": table.get("name"),
                "bet": bet,
            },
        )
        if new_balance is None:
            player["round_status"] = "insufficient_funds"
            continue

        hand = _bj_make_hand([_bj_draw(table), _bj_draw(table)])
        hand["bet_amount"] = bet
        if hand.get("blackjack") or hand.get("total", 0) >= 21:
            hand["stood"] = True
        player["hands"] = [hand]
        player["reserved_bet"] = bet
        player["bet"] = 0
        player["round_status"] = "done" if _bj_player_is_done(player) else "playing"
        active_players.append(player)

    if not active_players:
        _bj_schedule_start(table, force=True)
        if not table.get("auto_start_at"):
            table["phase"] = "lobby"
            table["status"] = "waiting"
            table["message"] = "No players with valid bets were ready."
        return False, "Nobody with a valid bet could join this hand."

    table["dealer_hand"] = [_bj_draw(table), _bj_draw(table)]
    dealer_state = _bj_make_hand(list(table.get("dealer_hand", [])))
    insurance_pending = False
    if table.get("dealer_hand") and str(table["dealer_hand"][0].get("rank")) == "A":
        for player in active_players:
            if _bj_insurance_offer(player) > 0:
                player["insurance_state"] = "pending"
                insurance_pending = True

    table["phase"] = "insurance" if insurance_pending else "player_turns"
    table["status"] = "playing"
    table["started_at"] = _bj_now()
    _bj_log_table_event(
        table,
        "round_started",
        details=f"Round started with {len(active_players)} active players.",
        meta={"active_players": len(active_players), "insurance_phase": insurance_pending},
    )
    if not insurance_pending and dealer_state.get("blackjack"):
        _bj_settle_round(table)
        return True, "Dealer blackjack."

    if _bj_assign_turn(table) is None:
        if table.get("phase") == "insurance":
            _bj_finish_insurance_phase(table)
        else:
            _bj_settle_round(table)
            return True, "All hands auto-settled."

    return True, "Round started."


def _bj_auto_stand_current_player(table):
    current_index = table.get("current_turn_index")
    if current_index is None:
        return False
    try:
        player = table.get("players", [])[int(current_index)]
    except Exception:
        return False

    hand = _bj_active_hand(player)
    if not hand:
        return False

    if table.get("phase") == "insurance":
        player["insurance_state"] = "declined"
        player["round_status"] = "playing"
        table["message"] = f"{player.get('username')} timed out on insurance."
        _bj_log_table_event(
            table,
            "insurance_timeout",
            user_id=player.get("user_id"),
            username=player.get("username"),
            details=table["message"],
        )
        _bj_finish_insurance_phase(table)
        return True

    hand["stood"] = True
    player["round_status"] = "timed_out"
    table["message"] = f"{player.get('username')} timed out. Standing automatically."
    _bj_log_table_event(
        table,
        "turn_timeout",
        user_id=player.get("user_id"),
        username=player.get("username"),
        details=table["message"],
        meta={"hand_total": int(hand.get("total", 0) or 0)},
    )
    if _bj_assign_turn(table, preserve_deadline=True) is None:
        _bj_settle_round(table)
    return True


def _bj_progress_table(table):
    changed = False
    now = _bj_now()

    while table.get("phase") in {"player_turns", "insurance"}:
        deadline = _bj_as_utc(table.get("turn_deadline_at"))
        if not deadline or deadline > now:
            break
        if not _bj_auto_stand_current_player(table):
            break
        changed = True
        now = _bj_now()

    auto_start_at = _bj_as_utc(table.get("auto_start_at"))
    if table.get("phase") in {"lobby", "waiting", "betting"} and auto_start_at and auto_start_at <= now:
        if _bj_claim_due_transition(table, allowed_phases={"lobby", "waiting", "betting"}, due_field="auto_start_at"):
            ready, _removed_players = _bj_finalize_betting_window(table)
            if not ready:
                changed = True
                return changed
            ok, message = _bj_start_round(table)
            if not ok:
                table["message"] = message
            changed = True

    return changed


def _bj_load_table_or_404(table_id, *, progress=False):
    try:
        table = _bj_tables_col().find_one({"_id": ObjectId(table_id)})
    except Exception:
        table = None
    if table and _bj_idle_should_close(table):
        _bj_tables_col().delete_one({"_id": table["_id"]})
        return None
    if table and progress and _bj_progress_table(table):
        if _bj_idle_should_close(table):
            _bj_tables_col().delete_one({"_id": table["_id"]})
            return None
        _bj_save_table(table)
    return table


def _bj_claim_due_transition(table, *, allowed_phases, due_field, next_phase="dealing"):
    if not table or not table.get("_id"):
        return False
    due_value = table.get(due_field)
    if not isinstance(allowed_phases, (list, tuple, set)):
        allowed_phases = [allowed_phases]
    query = {
        "_id": table["_id"],
        "phase": {"$in": list(allowed_phases)},
        due_field: due_value,
        "updated_at": table.get("updated_at"),
    }
    update = {
        "$set": {
            "phase": next_phase,
            "status": "waiting",
            due_field: None,
            "updated_at": _bj_now(),
        }
    }
    result = _bj_tables_col().update_one(query, update)
    if not result.modified_count:
        return False
    table["phase"] = next_phase
    table["status"] = "waiting"
    table[due_field] = None
    table["updated_at"] = _bj_now()
    return True


def _bj_save_table(table):
    table["updated_at"] = _bj_now()
    _bj_tables_col().replace_one({"_id": table["_id"]}, table, upsert=False)


@app.route("/blackjack")
def blackjack_room():
    if "discord_id" not in session:
        return redirect(url_for("login", next=url_for("blackjack_room")))

    viewer_id = int(session["discord_id"])
    coins = _bj_current_balance(viewer_id)
    active_table_id = (request.args.get("table") or "").strip()
    active_table = _bj_load_table_or_404(active_table_id, progress=True) if active_table_id else None

    return render_template(
        "blackjack.html",
        year=datetime.now().year,
        blackjack_viewer_id=viewer_id,
        blackjack_balance=coins,
        blackjack_is_admin=is_admin(),
        active_table_id=str(active_table.get("_id")) if active_table else "",
        active_table_name=active_table.get("name") if active_table else "",
    )


@csrf.exempt
@app.get("/api/blackjack/lobby")
def api_blackjack_lobby():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    viewer_id = int(session["discord_id"])
    tables = list(
        _bj_tables_col()
        .find({}, {"deck": 0})
        .sort("updated_at", -1)
        .limit(30)
    )
    payload = []
    for table in tables:
        if _bj_idle_should_close(table):
            _bj_tables_col().delete_one({"_id": table["_id"]})
            continue
        if _bj_progress_table(table):
            if _bj_idle_should_close(table):
                _bj_tables_col().delete_one({"_id": table["_id"]})
                continue
            _bj_save_table(table)
        payload.append({
            "id": str(table.get("_id")),
            "name": table.get("name") or "Blackjack Table",
            "table_code": table.get("table_code"),
            "status": table.get("status", "waiting"),
            "phase": table.get("phase", "lobby"),
            "owner_name": table.get("owner_name"),
            "min_bet": int(table.get("min_bet", 1) or 1),
            "turn_time_seconds": _bj_turn_time_seconds(table.get("turn_time_seconds")),
            "max_players": int(table.get("max_players", 5) or 5),
            "player_count": len(table.get("players", [])),
            "observer_count": len(table.get("observers", [])),
            "auto_start_at": _bj_as_utc(table.get("auto_start_at")).isoformat() if _bj_as_utc(table.get("auto_start_at")) else None,
            "viewer_joined": any(int(p.get("user_id", 0)) == viewer_id for p in table.get("players", [])),
            "viewer_observing": any(int(o.get("user_id", 0)) == viewer_id for o in table.get("observers", [])),
            "updated_at": _bj_as_utc(table.get("updated_at")).isoformat() if _bj_as_utc(table.get("updated_at")) else None,
        })

    return jsonify({
        "tables": payload,
        "viewer_id": viewer_id,
        "balance": _bj_current_balance(viewer_id),
        "poll_seconds": BLACKJACK_TABLE_POLL_SECONDS,
    })


@csrf.exempt
@app.post("/api/blackjack/create")
def api_blackjack_create():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    user_id = int(session["discord_id"])
    profile = _bj_user_profile(user_id)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "Farm Table").strip()[:40]
    try:
        min_bet = max(1, min(int(data.get("min_bet", 1) or 1), BLACKJACK_MAX_BET))
    except (TypeError, ValueError):
        min_bet = 1
    try:
        max_players = max(2, min(int(data.get("max_players", 4) or 4), 6))
    except (TypeError, ValueError):
        max_players = 4
    turn_time_seconds = _bj_turn_time_seconds(data.get("turn_time_seconds", BLACKJACK_DEFAULT_TURN_TIME_SECONDS))

    profile_with_id = {**profile, "user_id": user_id}
    player = _bj_make_seat_member(profile_with_id, min_bet=min_bet)
    table = {
        "name": name or "Farm Table",
        "table_code": secrets.token_hex(3).upper(),
        "owner_id": user_id,
        "owner_name": profile["username"],
        "status": "waiting",
        "phase": "lobby",
        "message": "Table created. Players can join and place bets.",
        "min_bet": min_bet,
        "max_players": max_players,
        "turn_time_seconds": turn_time_seconds,
        "shoe_count": 4,
        "deck": _bj_make_shoe(4),
        "dealer_hand": [],
        "current_turn_index": None,
        "current_turn_user_id": None,
        "auto_start_at": None,
        "auto_redeal_at": None,
        "chat": [],
        "players": [player],
        "observers": [],
        "created_at": _bj_now(),
        "updated_at": _bj_now(),
    }
    _bj_add_chat_message(
        table,
        kind="system",
        text=f"{profile['username']} opened the table. Place bets to start the first hand.",
        user_id=user_id,
        username=profile["username"],
        avatar_url=profile["avatar_url"],
    )
    result = _bj_tables_col().insert_one(table)
    table["_id"] = result.inserted_id
    _bj_log_table_event(
        table,
        "table_created",
        user_id=user_id,
        username=profile["username"],
        details=f"Created table with minimum bet {min_bet:,}, {max_players} seats, turn time {turn_time_seconds}s.",
    )
    _bj_schedule_start(table, force=True)
    _bj_save_table(table)
    return jsonify({"ok": True, "table_id": str(result.inserted_id)})


@csrf.exempt
@app.post("/api/blackjack/join")
def api_blackjack_join():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    table_id = (data.get("table_id") or "").strip()
    table = _bj_load_table_or_404(table_id, progress=True)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    user_id = int(session["discord_id"])
    _, existing = _bj_find_player(table, user_id)
    if existing:
        return jsonify({"ok": True, "table_id": table_id})
    observer_index, existing_observer = _bj_find_observer(table, user_id)

    if len(table.get("players", [])) >= int(table.get("max_players", 5) or 5):
        return jsonify({"error": "That table is full"}), 400

    profile = _bj_user_profile(user_id)
    waiting_status = "waiting_next_hand" if table.get("phase") == "player_turns" else "waiting"
    profile_with_id = {**profile, "user_id": user_id}
    table.setdefault("players", []).append(
        _bj_make_seat_member(
            profile_with_id,
            min_bet=int(table.get("min_bet", 1) or 1),
            waiting_status=waiting_status,
        )
    )
    if observer_index is not None:
        table["observers"].pop(observer_index)
    table["message"] = (
        f"{profile['username']} joined the table and can bet for this window."
        if waiting_status == "waiting_next_hand"
        else f"{profile['username']} took a seat at the table."
    )
    _bj_add_chat_message(
        table,
        kind="system",
        text=table["message"],
        user_id=user_id,
        username=profile["username"],
        avatar_url=profile["avatar_url"],
    )
    if table.get("phase") != "player_turns":
        _bj_schedule_start(table, force=False)
        if table.get("phase") == "betting" and _bj_all_seated_players_ready(table):
            table["auto_start_at"] = None
            ok, message = _bj_start_round(table)
            table["message"] = message if not ok else table.get("message")
    _bj_log_table_event(
        table,
        "player_joined",
        user_id=user_id,
        username=profile["username"],
        details=table["message"],
    )
    _bj_save_table(table)
    return jsonify({"ok": True, "table_id": table_id})


@csrf.exempt
@app.post("/api/blackjack/observe")
def api_blackjack_observe():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    table_id = (data.get("table_id") or "").strip()
    table = _bj_load_table_or_404(table_id, progress=True)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    user_id = int(session["discord_id"])
    _, player = _bj_find_player(table, user_id)
    if player is not None:
        return jsonify({"ok": True, "table_id": table_id})
    _, observer = _bj_find_observer(table, user_id)
    if observer is not None:
        return jsonify({"ok": True, "table_id": table_id})

    profile = _bj_user_profile(user_id)
    profile_with_id = {**profile, "user_id": user_id}
    table.setdefault("observers", []).append(_bj_make_observer(profile_with_id))
    table["message"] = f"{profile['username']} is watching the table."
    _bj_add_chat_message(
        table,
        kind="system",
        text=table["message"],
        user_id=user_id,
        username=profile["username"],
        avatar_url=profile["avatar_url"],
    )
    _bj_log_table_event(
        table,
        "observer_joined",
        user_id=user_id,
        username=profile["username"],
        details=table["message"],
    )
    _bj_save_table(table)
    return jsonify({"ok": True, "table_id": table_id})


@csrf.exempt
@app.post("/api/blackjack/leave")
def api_blackjack_leave():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    table_id = (data.get("table_id") or "").strip()
    table = _bj_load_table_or_404(table_id, progress=True)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    user_id = int(session["discord_id"])
    index, player = _bj_find_player(table, user_id)
    observer_index, observer = _bj_find_observer(table, user_id)
    if player is None and observer is None:
        return jsonify({"ok": True})
    if player is not None and table.get("phase") == "player_turns" and int(player.get("reserved_bet", 0) or 0) > 0:
        return jsonify({"error": "Finish the current hand before leaving"}), 400

    departing = player or observer
    if player is not None:
        table["players"].pop(index)
    elif observer_index is not None:
        table.setdefault("observers", []).pop(observer_index)

    if not table.get("players") and not table.get("observers"):
        _bj_log_table_event(
            table,
            "table_closed",
            user_id=user_id,
            username=departing.get("username"),
            details=f"{departing.get('username')} left and the table closed.",
        )
        _bj_tables_col().delete_one({"_id": table["_id"]})
        return jsonify({"ok": True, "deleted": True})

    if int(table.get("owner_id", 0) or 0) == user_id:
        new_owner = (table.get("players") or table.get("observers") or [None])[0]
        if new_owner:
            table["owner_id"] = int(new_owner.get("user_id"))
            table["owner_name"] = new_owner.get("username")
    table["message"] = f"{departing.get('username')} left the table."
    if table.get("phase") != "player_turns":
        _bj_schedule_start(table, force=False)
        if table.get("phase") == "betting" and _bj_all_seated_players_ready(table):
            table["auto_start_at"] = None
            ok, message = _bj_start_round(table)
            table["message"] = message if not ok else table.get("message")
    _bj_log_table_event(
        table,
        "player_left",
        user_id=user_id,
        username=departing.get("username"),
        details=table["message"],
    )
    _bj_save_table(table)
    return jsonify({"ok": True})


@csrf.exempt
@app.get("/api/blackjack/table/<table_id>")
def api_blackjack_table_state(table_id):
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    table = _bj_load_table_or_404(table_id, progress=True)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    viewer_id = int(session["discord_id"])
    return jsonify({
        "table": _bj_table_state(table, viewer_id=viewer_id),
        "viewer_id": viewer_id,
        "balance": _bj_current_balance(viewer_id),
    })


@csrf.exempt
@app.post("/api/blackjack/bet")
def api_blackjack_bet():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    table_id = (data.get("table_id") or "").strip()
    table = _bj_load_table_or_404(table_id, progress=True)
    if not table:
        return jsonify({"error": "Table not found"}), 404
    user_id = int(session["discord_id"])
    _, player = _bj_find_player(table, user_id)
    if player is None:
        return jsonify({"error": "Join the table first"}), 400
    try:
        bet = int(data.get("bet", 0) or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid bet"}), 400

    min_bet = int(table.get("min_bet", 1) or 1)
    if bet and bet < min_bet:
        return jsonify({"error": f"Minimum bet is {min_bet}"}), 400
    if bet > BLACKJACK_MAX_BET:
        return jsonify({"error": f"Maximum bet is {BLACKJACK_MAX_BET}"}), 400

    has_reserved_bet = int(player.get("reserved_bet", 0) or 0) > 0

    if has_reserved_bet:
        player["next_bet"] = bet
        if bet > 0:
            player["auto_bet_amount"] = bet
        table["message"] = f"{player.get('username')} set next hand bet to {bet:,}."
    else:
        player["bet"] = bet
        player["next_bet"] = 0
        if bet > 0:
            player["auto_bet_amount"] = bet
        table["message"] = f"{player.get('username')} set a bet of {bet:,}."

    if not has_reserved_bet and table.get("phase") not in {"player_turns", "insurance"}:
        _bj_schedule_start(table, force=False)
        if table.get("phase") == "betting" and _bj_all_seated_players_ready(table):
            table["auto_start_at"] = None
            ok, message = _bj_start_round(table)
            table["message"] = message if not ok else table.get("message")
        
    _bj_log_table_event(
        table,
        "bet_updated",
        user_id=user_id,
        username=player.get("username"),
        details=table["message"],
                meta={"bet": bet, "next_hand_only": has_reserved_bet},
    )
    _bj_save_table(table)
    return jsonify({"ok": True})


@csrf.exempt
@app.post("/api/blackjack/auto-bet")
def api_blackjack_auto_bet():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    table_id = (data.get("table_id") or "").strip()
    table = _bj_load_table_or_404(table_id, progress=True)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    user_id = int(session["discord_id"])
    _, player = _bj_find_player(table, user_id)
    if player is None:
        return jsonify({"error": "Join the table first"}), 400

    enabled = bool(data.get("enabled"))
    min_bet = int(table.get("min_bet", 1) or 1)
    amount = int(player.get("bet", 0) or player.get("auto_bet_amount", 0) or 0)
    if enabled and amount <= 0:
        return jsonify({"error": "Place a bet first, then turn on auto bet"}), 400
    player["auto_bet_enabled"] = enabled
    if amount > 0:
        player["auto_bet_amount"] = amount
    if int(player.get("reserved_bet", 0) or 0) <= 0:
        if enabled and amount > 0:
            player["bet"] = amount
        if table.get("phase") not in {"player_turns", "insurance"}:
            _bj_schedule_start(table, force=False)
            if table.get("phase") == "betting" and _bj_all_seated_players_ready(table):
                table["auto_start_at"] = None
                ok, message = _bj_start_round(table)
                table["message"] = message if not ok else table.get("message")

    table["message"] = (
        f"{player.get('username')} turned on auto bet for {amount:,}."
        if enabled
        else f"{player.get('username')} turned auto bet off."
    )
    _bj_log_table_event(
        table,
        "auto_bet_updated",
        user_id=user_id,
        username=player.get("username"),
        details=table["message"],
        meta={"enabled": enabled, "amount": amount},
    )
    _bj_save_table(table)
    return jsonify({"ok": True})


@csrf.exempt
@app.post("/api/blackjack/start")
def api_blackjack_start():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    table_id = (data.get("table_id") or "").strip()
    table = _bj_load_table_or_404(table_id, progress=True)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    user_id = int(session["discord_id"])
    if int(table.get("owner_id", 0) or 0) != user_id:
        return jsonify({"error": "Only the table owner can start the hand"}), 403

    ok, message = _bj_start_round(table)
    _bj_log_table_event(
        table,
        "manual_start_attempt",
        user_id=user_id,
        username=session.get("username"),
        details=message,
    )
    _bj_save_table(table)
    if not ok:
        return jsonify({"error": message}), 400
    return jsonify({"ok": True, "message": message})


@csrf.exempt
@app.post("/api/blackjack/delete")
def api_blackjack_delete():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401
    if not is_admin():
        return jsonify({"error": "Admin only"}), 403

    data = request.get_json(silent=True) or {}
    table_id = (data.get("table_id") or "").strip()
    table = _bj_load_table_or_404(table_id, progress=False)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    _bj_log_table_event(
        table,
        "table_deleted",
        user_id=session.get("discord_id"),
        username=session.get("username"),
        details="Admin deleted the table.",
    )
    _bj_tables_col().delete_one({"_id": table["_id"]})
    return jsonify({"ok": True, "deleted": True})


@csrf.exempt
@app.post("/api/blackjack/action")
def api_blackjack_action():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    table_id = (data.get("table_id") or "").strip()
    action = (data.get("action") or "").strip().lower()
    table = _bj_load_table_or_404(table_id, progress=True)
    if not table:
        return jsonify({"error": "Table not found"}), 404
    if table.get("phase") not in {"player_turns", "insurance"}:
        return jsonify({"error": "No active hand right now"}), 400

    user_id = int(session["discord_id"])
    if int(table.get("current_turn_user_id", 0) or 0) != user_id:
        return jsonify({"error": "It is not your turn"}), 400

    _, player = _bj_find_player(table, user_id)
    if player is None:
        return jsonify({"error": "Player not found"}), 404
    hand = _bj_active_hand(player)
    if hand is None:
        return jsonify({"error": "No active hand"}), 400

    if table.get("phase") == "insurance":
        if action == "insurance":
            insurance_bet = _bj_insurance_offer(player)
            if insurance_bet <= 0:
                return jsonify({"error": "Insurance is not available"}), 400
            if player.get("insurance_state") != "pending":
                return jsonify({"error": "Insurance was already decided"}), 400
            new_balance = _bj_debit_user(
                player.get("user_id"),
                insurance_bet,
                source="blackjack:insurance",
                meta={
                    "table_id": str(table.get("_id")),
                    "table_name": table.get("name"),
                    "bet": insurance_bet,
                },
            )
            if new_balance is None:
                return jsonify({"error": "Not enough coins for insurance"}), 400
            player["insurance_bet"] = insurance_bet
            player["insurance_state"] = "taken"
            table["message"] = f"{player.get('username')} bought insurance."
        elif action in {"insurance_decline", "no_insurance"}:
            player["insurance_state"] = "declined"
            table["message"] = f"{player.get('username')} skipped insurance."
        else:
            return jsonify({"error": "Only insurance choices are available right now"}), 400

        _bj_log_table_event(
            table,
            "insurance_choice",
            user_id=user_id,
            username=player.get("username"),
            details=table["message"],
            meta={"choice": action, "insurance_bet": int(player.get("insurance_bet", 0) or 0)},
        )
        _bj_finish_insurance_phase(table)
        _bj_save_table(table)
        return jsonify({"ok": True})

    if action == "hit":
        hand.setdefault("cards", []).append(_bj_draw(table))
        hand.update(_bj_hand_state(hand.get("cards", [])))
        if hand.get("busted") or hand.get("total", 0) >= 21:
            hand["stood"] = True
    elif action == "double":
        if len(hand.get("cards", [])) != 2 or hand.get("doubled"):
            return jsonify({"error": "Double down is only available on your first two cards"}), 400
        extra_bet = int(hand.get("bet_amount", 0) or 0)
        new_balance = _bj_debit_user(
            player.get("user_id"),
            extra_bet,
            source="blackjack:double",
            meta={
                "table_id": str(table.get("_id")),
                "table_name": table.get("name"),
                "bet": extra_bet,
            },
        )
        if new_balance is None:
            return jsonify({"error": "Not enough coins to double down"}), 400
        player["reserved_bet"] = int(player.get("reserved_bet", 0) or 0) + extra_bet
        hand["bet_amount"] = extra_bet * 2
        hand["doubled"] = True
        hand.setdefault("cards", []).append(_bj_draw(table))
        hand.update(_bj_hand_state(hand.get("cards", [])))
        hand["stood"] = True
        table["message"] = f"{player.get('username')} doubled down."
    elif action == "split":
        cards = list(hand.get("cards", []))
        if len(cards) != 2:
            return jsonify({"error": "Split is only available on your first two cards"}), 400
        if str(cards[0].get("rank")) != str(cards[1].get("rank")):
            return jsonify({"error": "You can only split matching ranks"}), 400
        split_bet = int(hand.get("bet_amount", 0) or 0)
        new_balance = _bj_debit_user(
            player.get("user_id"),
            split_bet,
            source="blackjack:split",
            meta={
                "table_id": str(table.get("_id")),
                "table_name": table.get("name"),
                "bet": split_bet,
            },
        )
        if new_balance is None:
            return jsonify({"error": "Not enough coins to split"}), 400

        player["reserved_bet"] = int(player.get("reserved_bet", 0) or 0) + split_bet
        first_hand = _bj_make_hand([cards[0], _bj_draw(table)])
        first_hand["bet_amount"] = split_bet
        first_hand["split_hand"] = True
        second_hand = _bj_make_hand([cards[1], _bj_draw(table)])
        second_hand["bet_amount"] = split_bet
        second_hand["split_hand"] = True
        if str(cards[0].get("rank")) == "A":
            first_hand["stood"] = True
            second_hand["stood"] = True

        hands = player.get("hands") or []
        hand_index = int(player.get("active_hand_index", 0) or 0)
        player["hands"] = hands[:hand_index] + [first_hand, second_hand] + hands[hand_index + 1:]
        player["active_hand_index"] = hand_index
        table["message"] = f"{player.get('username')} split their hand."
    elif action == "stand":
        hand["stood"] = True
    else:
        return jsonify({"error": "Unsupported action"}), 400

    _bj_log_table_event(
        table,
        f"player_{action}",
        user_id=user_id,
        username=player.get("username"),
        details=table.get("message") or f"{player.get('username')} used {action}.",
        meta={"hand_total": int(hand.get("total", 0) or 0), "bet_amount": int(hand.get("bet_amount", 0) or 0)},
    )
    _bj_refresh_player_state(player)
    if _bj_assign_turn(table, preserve_deadline=True) is None:
        _bj_settle_round(table)
    _bj_save_table(table)
    return jsonify({"ok": True})


@csrf.exempt
@app.post("/api/blackjack/chat")
def api_blackjack_chat():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    table_id = (data.get("table_id") or "").strip()
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400

    table = _bj_load_table_or_404(table_id, progress=True)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    user_id = int(session["discord_id"])
    _, player = _bj_find_player(table, user_id)
    if player is None:
        return jsonify({"error": "Join the table to chat"}), 400

    _bj_add_chat_message(
        table,
        kind="user",
        text=message,
        user_id=user_id,
        username=player.get("username"),
        avatar_url=player.get("avatar_url"),
    )
    _bj_log_table_event(
        table,
        "chat_message",
        user_id=user_id,
        username=player.get("username"),
        details=message[:140],
    )
    _bj_save_table(table)
    return jsonify({"ok": True})


@csrf.exempt
@app.post("/api/blackjack/report")
def api_blackjack_report():
    if "discord_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    table_id = (data.get("table_id") or "").strip()
    reason = " ".join(str(data.get("reason") or "").strip().split())
    if len(reason) < 10:
        return jsonify({"error": "Please describe the issue in a little more detail."}), 400

    table = _bj_load_table_or_404(table_id, progress=True)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    user_id = int(session["discord_id"])
    profile = _bj_user_profile(user_id)
    report_doc = {
        "table_id": str(table.get("_id")),
        "table_code": table.get("table_code"),
        "table_name": table.get("name"),
        "owner_id": int(table.get("owner_id", 0) or 0) or None,
        "owner_name": table.get("owner_name"),
        "phase": table.get("phase"),
        "status": table.get("status"),
        "message": table.get("message"),
        "reporter_user_id": user_id,
        "reporter_username": profile.get("username"),
        "reporter_avatar_url": profile.get("avatar_url"),
        "reason": reason[:1200],
        "players": [
            {
                "user_id": int(player.get("user_id", 0) or 0),
                "username": player.get("username"),
            }
            for player in table.get("players", [])
        ],
        "chat_tail": [
            {
                "kind": msg.get("kind"),
                "username": msg.get("username"),
                "text": msg.get("text"),
                "ts": _bj_as_utc(msg.get("ts")),
            }
            for msg in list(table.get("chat", []))[-8:]
        ],
        "created_at": _bj_now(),
    }
    _bj_reports_col().insert_one(report_doc)
    _bj_log_table_event(
        table,
        "report_submitted",
        user_id=user_id,
        username=profile.get("username"),
        details=reason[:220],
    )
    return jsonify({"ok": True})


def _ticket_archive_col():
    return get_db("Support")["transcripts"]


def _ticket_archive_meta_col():
    return get_db("Support")["active_tickets"]


def _ticket_archive_format_dt(value):
    if not value:
        return ""
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(COPENHAGEN_TZ).strftime("%Y-%m-%d %H:%M")
    return str(value)


def _ticket_archive_plain_text(html):
    soup = BeautifulSoup(html or "", "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def _ticket_archive_snippet(text, query, radius=150):
    text = text or ""
    if not text:
        return "Transcript has no readable text."

    q = (query or "").strip()
    if q:
        idx = text.lower().find(q.lower())
        if idx >= 0:
            start = max(0, idx - radius)
            end = min(len(text), idx + len(q) + radius)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(text) else ""
            return f"{prefix}{text[start:end].strip()}{suffix}"

    return text[:320].strip() + ("..." if len(text) > 320 else "")


def _ticket_archive_result(doc, meta_doc, query):
    channel_id = str(doc.get("_id") or "")
    html = doc.get("html") or ""
    text = _ticket_archive_plain_text(html)
    ticket_type = (meta_doc or {}).get("type")
    if not ticket_type:
        ticket_type = "Giveaway" if "giveaway details" in text.lower() else "Transcript"

    username = (meta_doc or {}).get("username") or ""
    channel_name = (meta_doc or {}).get("channel_name") or ""
    title_bits = [ticket_type]
    if username:
        title_bits.append(username)
    elif channel_name:
        title_bits.append(channel_name)

    status = ((meta_doc or {}).get("status") or "archived").title()
    status_key = re.sub(r"[^a-z0-9]+", "-", status.lower()).strip("-") or "archived"

    return {
        "channel_id": channel_id,
        "title": " - ".join(title_bits),
        "ticket_type": ticket_type,
        "status": status,
        "status_key": status_key,
        "username": username,
        "user_id": (meta_doc or {}).get("user_id") or "",
        "created_at": _ticket_archive_format_dt((meta_doc or {}).get("created_at")),
        "last_updated": _ticket_archive_format_dt(doc.get("last_updated")),
        "snippet": _ticket_archive_snippet(text, query),
    }


def _ticket_archive_safe_channel_id(channel_id):
    cid = str(channel_id or "").strip()
    if not cid.isdigit():
        abort(404)
    return cid


def _ticket_archive_allowed_asset_url(url):
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None

    host = (parsed.hostname or "").lower()
    allowed_hosts = {
        "cdn.discordapp.com",
        "media.discordapp.net",
        "images-ext-1.discordapp.net",
        "images-ext-2.discordapp.net",
        "pub-d60d332f99c6465bbf7133fadd42a702.r2.dev",
    }
    configured_public = (R2_PUBLIC_HOST or "").strip()
    if configured_public:
        configured_host = urlparse(configured_public if "://" in configured_public else f"https://{configured_public}").hostname
        if configured_host:
            allowed_hosts.add(configured_host.lower())

    if host in allowed_hosts or host.endswith(".r2.dev"):
        return parsed.geturl()
    return None


def _ticket_archive_rewrite_media_urls(html, channel_id):
    soup = BeautifulSoup(html or "", "html.parser")
    media_attrs = {
        "img": ("src",),
        "video": ("src", "poster"),
        "audio": ("src",),
        "source": ("src",),
    }
    for tag_name, attrs in media_attrs.items():
        for tag in soup.find_all(tag_name):
            for attr in attrs:
                src = tag.get(attr)
                if not _ticket_archive_allowed_asset_url(src):
                    continue
                tag[attr] = url_for("ticket_archive_asset", channel_id=channel_id, url=src)
                if tag_name == "img":
                    tag["loading"] = "lazy"
                    tag["referrerpolicy"] = "no-referrer"
    return str(soup)


def _ticket_archive_html_response(channel_id, *, as_attachment=False):
    cid = _ticket_archive_safe_channel_id(channel_id)
    doc = _ticket_archive_col().find_one({"_id": cid}, {"html": 1, "last_updated": 1})
    if not doc or not doc.get("html"):
        abort(404)

    html = doc["html"] if as_attachment else _ticket_archive_rewrite_media_urls(doc["html"], cid)
    response = make_response(html)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    disposition = "attachment" if as_attachment else "inline"
    response.headers["Content-Disposition"] = f'{disposition}; filename="transcript-{cid}.html"'
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "sandbox allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-downloads; "
        "default-src 'none'; "
        "script-src 'none'; "
        "connect-src 'none'; "
        "img-src 'self' data: blob: https: http:; "
        "media-src 'self' data: blob: https: http:; "
        "style-src 'unsafe-inline'; "
        "font-src data: https:; "
        "base-uri 'none'; "
        "form-action 'none'"
    )
    return response


@app.route("/dashboard")
def dashboard():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    client= get_db()
    settings_col = client["Website"]["bot_settings"]
    support_col = client["Website"]["Support_settings"]

    settings = settings_col.find_one({"_id": "settings"}) or {}
    support_settings = {
        doc["_id"]: doc["role_id"]
        for doc in support_col.find()
    }

    # Available roles for dropdowns
    roles = [
        {"id": 1018204467524546591, "name": "Owner"},
        {"id": 1307838468788846652, "name": "Co-Owner"},
        {"id": 1228215782312509531, "name": "Head Admin"},
        {"id": 1086135408125022218, "name": "Staff Team"},
        {"id": 1086135499787345920, "name": "Trial Moderator"},
        {"id": 1234364432252145674, "name": "Verifier Team"},
        {"id": 1251737546770088028, "name": "Giveaway Staff"},
    ]

    # List of support ticket types you want to configure
    ticket_types = [
        "Scam",
        "Giveaway Help",
        "Auction Help",
        "Bad Behaviour",
        "Verification",
        "General Help"
    ]

    return render_template(
        "dashboard.html",
        year=datetime.now().year,
        username=session.get("username", "Unknown"),
        prefix=settings.get("prefix", "!"),
        roles=roles,
        ticket_types=ticket_types,
        support_settings=support_settings
    )


@app.route("/dashboard/ticket-archives")
def ticket_archives():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    query = (request.args.get("q") or "").strip()
    try:
        page = max(1, int(request.args.get("page", 1) or 1))
    except (TypeError, ValueError):
        page = 1
    per_page = 12

    transcripts_col = _ticket_archive_col()
    meta_col = _ticket_archive_meta_col()

    mongo_query = {}
    if query and len(query) >= 2:
        safe_q = re.escape(query)
        meta_regex = {"$regex": safe_q, "$options": "i"}
        matching_meta_ids = [
            str(meta.get("_id"))
            for meta in meta_col.find(
                {
                    "$or": [
                        {"username": meta_regex},
                        {"user_id": meta_regex},
                        {"channel_name": meta_regex},
                        {"type": meta_regex},
                        {"claimed_by": meta_regex},
                    ]
                },
                {"_id": 1},
            ).limit(1000)
        ]
        search_clauses = [
            {"html": {"$regex": safe_q, "$options": "i"}},
            {"_id": {"$regex": safe_q, "$options": "i"}},
        ]
        if matching_meta_ids:
            search_clauses.append({"_id": {"$in": matching_meta_ids}})
        mongo_query = {"$or": search_clauses}
    elif query:
        mongo_query = {"_id": "__too_short__"}

    total_results = transcripts_col.count_documents(mongo_query)
    total_pages = max(1, ceil(total_results / per_page)) if total_results else 1
    if page > total_pages:
        page = total_pages

    docs = list(
        transcripts_col.find(mongo_query, {"html": 1, "last_updated": 1})
        .sort("last_updated", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    channel_ids = [str(doc.get("_id")) for doc in docs]
    meta_docs = {
        str(meta.get("_id")): meta
        for meta in meta_col.find({"_id": {"$in": channel_ids}})
    } if channel_ids else {}
    results = [
        _ticket_archive_result(doc, meta_docs.get(str(doc.get("_id"))), query)
        for doc in docs
    ]

    stats = {
        "total_transcripts": transcripts_col.estimated_document_count(),
        "support_tickets": meta_col.estimated_document_count(),
    }

    return render_template(
        "ticket_archives.html",
        year=datetime.now().year,
        query=query,
        page=page,
        total_pages=total_pages,
        total_results=total_results,
        results=results,
        stats=stats,
    )


@app.route("/dashboard/ticket-archives/<channel_id>")
def ticket_archive_view(channel_id):
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403
    return _ticket_archive_html_response(channel_id)


@app.route("/dashboard/ticket-archives/<channel_id>/asset")
def ticket_archive_asset(channel_id):
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    _ticket_archive_safe_channel_id(channel_id)
    asset_url = _ticket_archive_allowed_asset_url(request.args.get("url"))
    if not asset_url:
        abort(404)

    try:
        upstream = requests.get(
            asset_url,
            headers={
                "User-Agent": "Mozilla/5.0 HayDayTicketArchive/1.0",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            },
            timeout=12,
            stream=True,
            allow_redirects=False,
        )
        upstream.raise_for_status()
    except requests.RequestException:
        abort(502)

    content_type = upstream.headers.get("Content-Type") or mimetypes.guess_type(asset_url)[0] or "application/octet-stream"
    if not (content_type.startswith("image/") or content_type.startswith("video/") or content_type.startswith("audio/")):
        upstream.close()
        abort(415)

    def generate():
        try:
            for chunk in upstream.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    response = Response(stream_with_context(generate()), content_type=content_type)
    response.headers["Cache-Control"] = "private, max-age=3600"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/dashboard/ticket-archives/<channel_id>/download")
def ticket_archive_download(channel_id):
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403
    return _ticket_archive_html_response(channel_id, as_attachment=True)


@app.route("/dashboard/gambling")
def dashboard_gambling():
    if "discord_id" not in session or not is_admin():
        return "Unauthorized", 403

    def _safe_page(value, default=1):
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    search_term = (request.args.get("search") or "").strip()
    table_code = (request.args.get("table_code") or "").strip().upper()
    blackjack_result = (request.args.get("blackjack_result") or "all").strip().lower()
    coinflip_result = (request.args.get("coinflip_result") or "all").strip().lower()
    start_date, end_date, start_dt, end_dt = _gambling_dashboard_date_bounds(
        request.args.get("start_date"),
        request.args.get("end_date"),
    )
    blackjack_page = _safe_page(request.args.get("blackjack_page", 1) or 1)
    coinflip_page = _safe_page(request.args.get("coinflip_page", 1) or 1)
    per_page = 12

    economy_db = get_db("Economy")
    blackjack_col = economy_db["blackjack_logs"]

    blackjack_query = {}
    if blackjack_result != "all":
        blackjack_query["result"] = blackjack_result
    if table_code:
        blackjack_query["table_code"] = table_code
    if start_dt or end_dt:
        blackjack_query["ts"] = {}
        if start_dt:
            blackjack_query["ts"]["$gte"] = start_dt
        if end_dt:
            blackjack_query["ts"]["$lt"] = end_dt

    if search_term:
        search_clauses = [{"username": {"$regex": re.escape(search_term), "$options": "i"}}]
        if search_term.isdigit():
            search_clauses.append({"user_id": int(search_term)})
        blackjack_query["$or"] = search_clauses

    blackjack_total = blackjack_col.count_documents(blackjack_query)
    blackjack_logs = list(
        blackjack_col.find(blackjack_query)
        .sort("ts", -1)
        .skip((blackjack_page - 1) * per_page)
        .limit(per_page)
    )

    blackjack_stat_rows = list(blackjack_col.aggregate([
        {"$match": blackjack_query},
        {"$group": {
            "_id": None,
            "wagered": {"$sum": {"$ifNull": ["$total_wager", 0]}},
            "paid_out": {"$sum": {"$ifNull": ["$payout", 0]}},
            "wins": {"$sum": {"$cond": [{"$in": ["$result", ["win", "blackjack"]]}, 1, 0]}},
            "losses": {"$sum": {"$cond": [{"$in": ["$result", ["loss", "dealer_blackjack"]]}, 1, 0]}},
            "pushes": {"$sum": {"$cond": [{"$eq": ["$result", "push"]}, 1, 0]}},
            "splits": {"$sum": {"$cond": [{"$eq": ["$split_used", True]}, 1, 0]}},
        }},
    ]))
    blackjack_stats = blackjack_stat_rows[0] if blackjack_stat_rows else {
        "wagered": 0,
        "paid_out": 0,
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "splits": 0,
    }
    blackjack_win_rate, blackjack_loss_rate = _gambling_result_percentages(
        blackjack_stats.get("wins"),
        blackjack_stats.get("losses"),
    )
    blackjack_stats["win_rate"] = blackjack_win_rate
    blackjack_stats["loss_rate"] = blackjack_loss_rate

    blackjack_name_map = _gambling_username_map(log.get("user_id") for log in blackjack_logs)
    for log in blackjack_logs:
        log["display_username"] = (
            blackjack_name_map.get(str(log.get("user_id")))
            or log.get("username")
            or str(log.get("user_id"))
        )

    action_col = economy_db["blackjack_action_logs"]
    action_query = {}
    if table_code:
        action_query["table_code"] = table_code
    if start_dt or end_dt:
        action_query["ts"] = {}
        if start_dt:
            action_query["ts"]["$gte"] = start_dt
        if end_dt:
            action_query["ts"]["$lt"] = end_dt
    if search_term:
        action_search = [{"username": {"$regex": re.escape(search_term), "$options": "i"}}]
        if search_term.isdigit():
            action_search.append({"user_id": int(search_term)})
        action_query["$or"] = action_search
    blackjack_action_logs = list(action_col.find(action_query).sort("ts", -1).limit(80))

    report_col = economy_db["blackjack_reports"]
    report_query = {}
    if table_code:
        report_query["table_code"] = table_code
    if start_dt or end_dt:
        report_query["created_at"] = {}
        if start_dt:
            report_query["created_at"]["$gte"] = start_dt
        if end_dt:
            report_query["created_at"]["$lt"] = end_dt
    if search_term:
        report_search = [{"reporter_username": {"$regex": re.escape(search_term), "$options": "i"}}]
        if search_term.isdigit():
            report_search.append({"reporter_user_id": int(search_term)})
        report_query["$or"] = report_search
    blackjack_reports = list(report_col.find(report_query).sort("created_at", -1).limit(50))

    coinflip_logs, coinflip_stats, coinflip_mode, coinflip_total = _build_coinflip_events(
        search_term=search_term,
        result_filter=coinflip_result,
        start_dt=start_dt,
        end_dt=end_dt,
        page=coinflip_page,
        per_page=per_page,
    )
    coinflip_win_rate, coinflip_loss_rate = _gambling_result_percentages(
        coinflip_stats.get("wins"),
        coinflip_stats.get("losses"),
    )
    coinflip_head_rate, coinflip_tail_rate = _gambling_coin_side_percentages(
        coinflip_stats.get("heads"),
        coinflip_stats.get("tails"),
    )
    coinflip_stats["win_rate"] = coinflip_win_rate
    coinflip_stats["loss_rate"] = coinflip_loss_rate
    coinflip_stats["head_rate"] = coinflip_head_rate
    coinflip_stats["tail_rate"] = coinflip_tail_rate

    return render_template(
        "dashboard_gambling.html",
        year=datetime.now().year,
        search_term=search_term,
        table_code=table_code,
        blackjack_result=blackjack_result,
        coinflip_result=coinflip_result,
        start_date=start_date,
        end_date=end_date,
        blackjack_logs=blackjack_logs,
        blackjack_action_logs=blackjack_action_logs,
        blackjack_reports=blackjack_reports,
        blackjack_total=blackjack_total,
        blackjack_page=blackjack_page,
        blackjack_stats=blackjack_stats,
        coinflip_logs=coinflip_logs,
        coinflip_total=coinflip_total,
        coinflip_page=coinflip_page,
        coinflip_stats=coinflip_stats,
        coinflip_mode=coinflip_mode,
        per_page=per_page,
    )


@app.post("/admin/gambling/blackjack/refund")
def admin_gambling_blackjack_refund():
    if "discord_id" not in session or not is_admin():
        return "Unauthorized", 403

    return_to = request.form.get("return_to") or url_for("dashboard_gambling")
    log_id = (request.form.get("log_id") or "").strip()
    if not log_id:
        flash("Missing blackjack log id.", "error")
        return redirect(return_to)

    economy_db = get_db("Economy")
    blackjack_col = economy_db["blackjack_logs"]

    try:
        log = blackjack_col.find_one({"_id": ObjectId(log_id)})
    except Exception:
        log = None

    if not log:
        flash("Blackjack log not found.", "error")
        return redirect(return_to)

    if log.get("admin_refunded_at"):
        flash("That blackjack hand was already refunded.", "warning")
        return redirect(return_to)

    if log.get("result") not in {"loss", "dealer_blackjack"}:
        flash("Only losing blackjack hands can be refunded from this page.", "warning")
        return redirect(return_to)

    refund_amount = int(log.get("total_wager") or log.get("bet") or 0)
    if refund_amount <= 0:
        flash("This blackjack hand has no refundable bet amount.", "error")
        return redirect(return_to)

    new_balance = _gambling_credit_user(
        log.get("user_id"),
        refund_amount,
        source="gambling_admin_refund:blackjack",
        meta={"log_id": log_id, "game": "blackjack", "result": log.get("result")},
    )
    blackjack_col.update_one(
        {"_id": log["_id"]},
        {"$set": {
            "admin_refunded_at": datetime.now(timezone.utc),
            "admin_refunded_by": session.get("discord_id"),
            "admin_refund_amount": refund_amount,
            "admin_balance_after_refund": new_balance,
        }},
    )

    flash(f"Refunded {refund_amount} coins to user {log.get('user_id')}.", "success")
    return redirect(return_to)


@app.post("/admin/gambling/coinflip/refund")
def admin_gambling_coinflip_refund():
    if "discord_id" not in session or not is_admin():
        return "Unauthorized", 403

    return_to = request.form.get("return_to") or url_for("dashboard_gambling")
    event_id = (request.form.get("event_id") or "").strip()
    storage_mode = (request.form.get("storage_mode") or "ledger").strip().lower()

    if not event_id:
        flash("Missing coinflip event id.", "error")
        return redirect(return_to)

    economy_db = get_db("Economy")

    try:
        object_id = ObjectId(event_id)
    except Exception:
        flash("Invalid coinflip event id.", "error")
        return redirect(return_to)

    if storage_mode == "collection":
        coinflip_col = economy_db["coinflip_logs"]
        doc = coinflip_col.find_one({"_id": object_id})
        if not doc:
            flash("Coinflip log not found.", "error")
            return redirect(return_to)
        if doc.get("admin_refunded_at"):
            flash("That coinflip was already refunded.", "warning")
            return redirect(return_to)
        if (doc.get("result") or "").lower() != "loss":
            flash("Only losing coinflips can be refunded from this page.", "warning")
            return redirect(return_to)

        refund_amount = int(doc.get("bet") or 0)
        if refund_amount <= 0:
            flash("This coinflip has no refundable bet amount.", "error")
            return redirect(return_to)

        new_balance = _gambling_credit_user(
            doc.get("user_id"),
            refund_amount,
            source="gambling_admin_refund:coinflip",
            meta={"log_id": event_id, "game": "coinflip", "storage_mode": "collection"},
        )
        coinflip_col.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "admin_refunded_at": datetime.now(timezone.utc),
                "admin_refunded_by": session.get("discord_id"),
                "admin_refund_amount": refund_amount,
                "admin_balance_after_refund": new_balance,
            }},
        )
    else:
        ledger_col = economy_db["coin_ledger"]
        doc = ledger_col.find_one({"_id": object_id})
        if not doc:
            flash("Coinflip wager log not found.", "error")
            return redirect(return_to)
        if doc.get("admin_refunded_at"):
            flash("That coinflip was already refunded.", "warning")
            return redirect(return_to)
        if doc.get("source") != "coinflip:wager":
            flash("Only coinflip loss wager rows can be refunded from this page.", "warning")
            return redirect(return_to)

        refund_amount = int(doc.get("amount") or 0)
        if refund_amount <= 0:
            flash("This coinflip has no refundable bet amount.", "error")
            return redirect(return_to)

        new_balance = _gambling_credit_user(
            doc.get("user_id"),
            refund_amount,
            source="gambling_admin_refund:coinflip",
            meta={"log_id": event_id, "game": "coinflip", "storage_mode": "ledger"},
        )
        ledger_col.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "admin_refunded_at": datetime.now(timezone.utc),
                "admin_refunded_by": session.get("discord_id"),
                "admin_refund_amount": refund_amount,
                "admin_balance_after_refund": new_balance,
            }},
        )

    flash(f"Refunded {refund_amount} coins for coinflip event {event_id}.", "success")
    return redirect(return_to)


@app.post("/admin/gambling/blackjack/review")
def admin_gambling_blackjack_review():
    if "discord_id" not in session or not is_admin():
        return "Unauthorized", 403

    return_to = request.form.get("return_to") or url_for("dashboard_gambling")
    log_id = (request.form.get("log_id") or "").strip()
    if not log_id:
        flash("Missing blackjack log id.", "error")
        return redirect(return_to)

    economy_db = get_db("Economy")
    blackjack_col = economy_db["blackjack_logs"]

    try:
        result = blackjack_col.update_one(
            {"_id": ObjectId(log_id), "admin_reviewed_at": {"$exists": False}},
            {"$set": {
                "admin_reviewed_at": datetime.now(timezone.utc),
                "admin_reviewed_by": session.get("discord_id"),
            }},
        )
    except Exception:
        result = None

    if not result or result.matched_count == 0:
        flash("Blackjack hand was already reviewed or could not be found.", "warning")
        return redirect(return_to)

    flash("Blackjack hand marked as reviewed.", "success")
    return redirect(return_to)


@app.post("/admin/gambling/blackjack/report/review")
def admin_gambling_blackjack_report_review():
    if "discord_id" not in session or not is_admin():
        return "Unauthorized", 403

    report_id = (request.form.get("report_id") or "").strip()
    return_to = request.form.get("return_to") or url_for("dashboard_gambling")
    if not report_id:
        flash("Missing blackjack report id.", "error")
        return redirect(return_to)

    try:
        object_id = ObjectId(report_id)
    except Exception:
        flash("Invalid blackjack report id.", "error")
        return redirect(return_to)

    result = _bj_reports_col().update_one(
        {"_id": object_id, "admin_reviewed_at": {"$exists": False}},
        {"$set": {
            "admin_reviewed_at": datetime.now(timezone.utc),
            "admin_reviewed_by": session.get("discord_id"),
        }},
    )
    if not result.modified_count:
        flash("Blackjack report was already reviewed or could not be found.", "warning")
        return redirect(return_to)

    flash("Blackjack report marked as reviewed.", "success")
    return redirect(return_to)


@app.post("/admin/gambling/coinflip/review")
def admin_gambling_coinflip_review():
    if "discord_id" not in session or not is_admin():
        return "Unauthorized", 403

    return_to = request.form.get("return_to") or url_for("dashboard_gambling")
    event_id = (request.form.get("event_id") or "").strip()
    storage_mode = (request.form.get("storage_mode") or "ledger").strip().lower()

    if not event_id:
        flash("Missing coinflip event id.", "error")
        return redirect(return_to)

    economy_db = get_db("Economy")

    try:
        object_id = ObjectId(event_id)
    except Exception:
        flash("Invalid coinflip event id.", "error")
        return redirect(return_to)

    target_col = economy_db["coinflip_logs"] if storage_mode == "collection" else economy_db["coin_ledger"]
    result = target_col.update_one(
        {"_id": object_id, "admin_reviewed_at": {"$exists": False}},
        {"$set": {
            "admin_reviewed_at": datetime.now(timezone.utc),
            "admin_reviewed_by": session.get("discord_id"),
        }},
    )

    if result.matched_count == 0:
        flash("Coinflip event was already reviewed or could not be found.", "warning")
        return redirect(return_to)

    flash("Coinflip event marked as reviewed.", "success")
    return redirect(return_to)


@app.route("/dashboard/pets", methods=["GET", "POST"])
def dashboard_pets():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    usernames_col = get_db("Website")["usernames"]

    def _pets_redirect(search_value: str, page_value: str | int):
        return redirect(url_for("dashboard_pets", search=(search_value or "").strip(), page=page_value))

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        search_value = request.form.get("return_search", "")
        page_value = request.form.get("return_page", "1")

        try:
            discord_id = int(request.form.get("user_id", "0"))
        except (TypeError, ValueError):
            flash("❌ Invalid pet owner.", "error")
            return _pets_redirect(search_value, page_value)

        user_doc = _pet_load_user(discord_id)
        pet = user_doc.get("pet")
        if not pet:
            flash("❌ That user does not have a pet anymore.", "error")
            return _pets_redirect(search_value, page_value)

        owner_profile = usernames_col.find_one({"_id": str(discord_id)}) or {}
        owner_name = owner_profile.get("display_name") or owner_profile.get("username") or str(discord_id)

        if action == "save_pet":
            pet_name = (request.form.get("pet_name") or "").strip()
            if not pet_name:
                flash("❌ Pet name cannot be empty.", "error")
                return _pets_redirect(search_value, page_value)

            pet_type = (request.form.get("pet_type") or pet.get("type") or "").strip().lower()
            if pet_type not in PET_STARTERS:
                flash("❌ Invalid pet type.", "error")
                return _pets_redirect(search_value, page_value)

            try:
                pet_level = max(1, min(20, int(request.form.get("level", pet.get("level", 1)))))
                pet_hunger = _pet_clamp_internal(int(request.form.get("hunger", pet.get("hunger", 100))))
                pet_happiness = _pet_clamp_internal(int(request.form.get("happiness", pet.get("happiness", 100))))
                pet_cleanliness = _pet_clamp_internal(int(request.form.get("cleanliness", pet.get("cleanliness", 100))))
                raw_xp = int(request.form.get("xp", pet.get("xp", 0)))
            except (TypeError, ValueError):
                flash("❌ Pet stats must be valid numbers.", "error")
                return _pets_redirect(search_value, page_value)

            max_xp = max(0, _pet_xp_needed(pet_level) - 1)
            accent_color = (request.form.get("accent_color") or "").strip().lower()
            valid_accents = {sw["key"] for sw in PET_STYLE_SWATCHES}

            pet["name"] = pet_name[:24]
            pet["level"] = pet_level
            pet["xp"] = max(0, min(raw_xp, max_xp))
            pet["hunger"] = pet_hunger
            pet["happiness"] = pet_happiness
            pet["cleanliness"] = pet_cleanliness

            if pet.get("type") != pet_type:
                starter = PET_STARTERS[pet_type]
                pet["type"] = pet_type
                pet["emoji"] = starter["emoji"]

            if not isinstance(pet.get("web_style"), dict):
                pet["web_style"] = {"accent_color": "strawberry"}
            if accent_color in valid_accents:
                pet["web_style"]["accent_color"] = accent_color

            _pet_normalize_neglect_state(pet)
            _pet_save(discord_id, pet)
            _pet_log(discord_id, "admin_pet_update", {
                "staff_id": session.get("discord_id"),
                "staff_name": session.get("display_name") or session.get("username"),
                "owner_name": owner_name,
            })
            flash(f"✅ Updated {pet['name']} for {owner_name}.", "success")
            return _pets_redirect(search_value, page_value)

        if action == "delete_pet":
            confirm_word = (request.form.get("confirm_word") or "").strip().upper()
            if confirm_word != "DELETE":
                flash("❌ Type DELETE to remove a pet.", "error")
                return _pets_redirect(search_value, page_value)

            _pet_users_col().update_one({"_id": discord_id}, {"$unset": {"pet": ""}})
            _pet_log(discord_id, "admin_pet_delete", {
                "staff_id": session.get("discord_id"),
                "staff_name": session.get("display_name") or session.get("username"),
                "owner_name": owner_name,
                "pet_name": pet.get("name"),
            })
            flash(f"✅ Removed {pet.get('name', 'that pet')} from {owner_name}.", "success")
            return _pets_redirect(search_value, page_value)

        if action == "remove_hotel":
            if not _pet_is_in_hotel(pet):
                flash("❌ That pet is not currently in the hotel.", "error")
                return _pets_redirect(search_value, page_value)

            _pet_release_hotel(pet, force=True)
            _pet_save(discord_id, pet)
            _pet_log(discord_id, "admin_pet_hotel_remove", {
                "staff_id": session.get("discord_id"),
                "staff_name": session.get("display_name") or session.get("username"),
                "owner_name": owner_name,
            })
            flash(f"✅ Returned {pet.get('name', 'that pet')} from the hotel for {owner_name}.", "success")
            return _pets_redirect(search_value, page_value)

        flash("❌ Unknown pet admin action.", "error")
        return _pets_redirect(search_value, page_value)

    search = (request.args.get("search") or "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    page_size = 12
    query = {"pet": {"$exists": True}}

    if search:
        regex = {"$regex": re.escape(search), "$options": "i"}
        owner_ids = set()

        if search.isdigit():
            owner_ids.add(int(search))

        for profile in usernames_col.find(
            {"$or": [{"display_name": regex}, {"username": regex}]},
            {"_id": 1}
        ).limit(200):
            try:
                owner_ids.add(int(profile["_id"]))
            except (TypeError, ValueError):
                continue

        search_filters = [{"pet.name": regex}]
        if owner_ids:
            search_filters.append({"_id": {"$in": sorted(owner_ids)}})
        query["$or"] = search_filters

    total_pets = _pet_users_col().count_documents({"pet": {"$exists": True}})
    matching_pets = _pet_users_col().count_documents(query)
    total_pages = max(1, math.ceil(matching_pets / page_size))
    page = min(page, total_pages)
    skip = (page - 1) * page_size

    pet_docs = list(
        _pet_users_col()
        .find(query)
        .sort("pet.adopted_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    owner_ids = [str(doc["_id"]) for doc in pet_docs]
    owner_map = {
        doc["_id"]: doc
        for doc in usernames_col.find(
            {"_id": {"$in": owner_ids}},
            {"display_name": 1, "username": 1, "avatar": 1}
        )
    } if owner_ids else {}

    pet_rows = []
    for user_doc in pet_docs:
        pet = user_doc.get("pet")
        if not pet:
            continue
        pet_context = _pet_context_from_doc(user_doc)
        owner_profile = owner_map.get(str(user_doc["_id"]), {})
        owner_name = owner_profile.get("display_name") or owner_profile.get("username") or str(user_doc["_id"])
        pet_rows.append({
            "user_id": str(user_doc["_id"]),
            "owner_name": owner_name,
            "avatar_url": owner_profile.get("avatar", "https://cdn.discordapp.com/embed/avatars/0.png"),
            "pet": pet,
            "mood": pet_context.get("mood"),
            "visible_hunger": pet_context.get("visible_hunger"),
            "visible_happiness": pet_context.get("visible_happiness"),
            "visible_cleanliness": pet_context.get("visible_cleanliness"),
            "average_stat": _pet_visible_average_stats(pet),
            "pet_xp_needed": pet_context.get("pet_xp_needed"),
            "care_actions": pet_context.get("care_actions", {}),
            "active_boost_name": pet_context.get("active_boost_name"),
            "hotel_is_active": pet_context.get("hotel_is_active"),
            "hotel_time_left": pet_context.get("hotel_time_left"),
            "hotel_status_text": pet_context.get("hotel_status_text"),
            "hotel_return_state": pet_context.get("hotel_return_state"),
            "owned_boost_count": len(pet.get("owned_boosts", [])),
            "owned_consumable_count": len(pet.get("owned_consumables", [])),
        })

    return render_template(
        "dashboard_pets.html",
        year=datetime.now().year,
        username=session.get("username", "Unknown"),
        search=search,
        page=page,
        page_size=page_size,
        total_pets=total_pets,
        matching_pets=matching_pets,
        total_pages=total_pages,
        pet_rows=pet_rows,
        style_swatches=PET_STYLE_SWATCHES,
        pet_starters=PET_STARTERS,
    )


def _parse_verification_message(content):
    content = content or ""
    hayday_match = re.search(r"HayDay ID:\s*([#A-Z0-9]+)", content, re.I)
    level_match = re.search(r"Your level:\s*(\d+)", content, re.I)
    farm_name_match = re.search(r"Farm Name:\s*(.+)", content, re.I)
    one_piece_match = re.search(r"Likes One Piece\?:\s*(.+)", content, re.I)

    farm_name = farm_name_match.group(1).strip() if farm_name_match else None
    if farm_name and "\n" in farm_name:
        farm_name = farm_name.splitlines()[0].strip()

    one_piece = one_piece_match.group(1).strip() if one_piece_match else None
    if one_piece and "\n" in one_piece:
        one_piece = one_piece.splitlines()[0].strip()

    return {
        "hayday_id": hayday_match.group(1).strip().upper() if hayday_match else None,
        "level": int(level_match.group(1)) if level_match else None,
        "farm_name": farm_name,
        "one_piece": one_piece,
    }


def _canonical_verification_status(status):
    normalized = (status or "pending").strip().lower()
    aliases = {
        "approve": "approved",
        "approved": "approved",
        "verified": "approved",
        "verified_manual": "approved",
        "deny": "denied",
        "denied": "denied",
        "tag_not_found": "tag_not_found",
        "farmtag_not_found": "tag_not_found",
        "no_tag": "no_tag",
        "no_pfp": "no_pfp",
        "pending": "pending",
        "expired": "expired",
        "left": "left",
        "banned": "banned",
    }
    return aliases.get(normalized, normalized)


def _format_verification_doc(doc):
    parsed = _parse_verification_message(doc.get("Message content", ""))
    status = _canonical_verification_status(doc.get("status", "pending"))
    guild_id = GUILD_ID
    verify_channel_id = 1274074702712934410
    discord_message_id = doc.get("discord_message_id")
    message_link = doc.get("message_link")

    if not message_link and discord_message_id:
        message_link = (
            f"https://discord.com/channels/{guild_id}/{verify_channel_id}/{discord_message_id}"
        )

    flags = doc.get("flags") or {}
    return {
        "_id": str(doc.get("_id", "")),
        "user_name": doc.get("User Name"),
        "user_id": doc.get("id"),
        "status": status,
        "raw_status": doc.get("status", "pending"),
        "submitted_at": doc.get("submitted_at"),
        "reviewed_at": doc.get("reviewed_at"),
        "reviewed_by": doc.get("reviewed_by"),
        "reviewed_by_id": doc.get("reviewed_by_id"),
        "review_reason": doc.get("review_reason"),
        "platform": doc.get("platform"),
        "screenshot_url": doc.get("screenshot_url"),
        "discord_message_id": discord_message_id,
        "hayday_id_message_id": doc.get("hayday_id_message_id"),
        "message_link": message_link,
        "blacklisted": bool(flags.get("blacklisted")),
        "duplicate": bool(flags.get("duplicate")),
        "raw_content": doc.get("Message content", ""),
        **parsed,
    }


@app.route("/verification-dashboard")
def verification_dashboard():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    client = get_db()
    verify_col = client["log"]["verify"]

    active_status = (request.args.get("status") or "pending").strip().lower()
    search_query = (request.args.get("q") or "").strip()

    query = {}
    if active_status != "all":
        status_aliases = {
            "pending": ["pending"],
            "approved": ["approved", "approve", "verified", "verified_manual"],
            "denied": ["denied", "deny"],
            "tag_not_found": ["tag_not_found", "farmtag_not_found"],
            "no_tag": ["no_tag"],
            "no_pfp": ["no_pfp"],
        }
        query["status"] = {"$in": status_aliases.get(active_status, [active_status])}

    if search_query:
        search_filters = [
            {"User Name": {"$regex": re.escape(search_query), "$options": "i"}},
            {"Message content": {"$regex": re.escape(search_query), "$options": "i"}},
        ]

        if search_query.isdigit():
            numeric_value = int(search_query)
            search_filters.extend(
                [
                    {"id": numeric_value},
                    {"discord_message_id": numeric_value},
                ]
            )

        if query:
            query = {"$and": [query, {"$or": search_filters}]}
        else:
            query = {"$or": search_filters}

    docs = list(
        verify_col.find(query)
        .sort("submitted_at", -1)
        .limit(150)
    )

    entries = [_format_verification_doc(doc) for doc in docs]
    counts = {
        "pending": verify_col.count_documents({"status": {"$in": ["pending"]}}),
        "approved": verify_col.count_documents({"status": {"$in": ["approved", "approve", "verified", "verified_manual"]}}),
        "denied": verify_col.count_documents({"status": {"$in": ["denied", "deny"]}}),
        "tag_not_found": verify_col.count_documents({"status": {"$in": ["tag_not_found", "farmtag_not_found"]}}),
        "all": verify_col.count_documents({}),
    }

    return render_template(
        "verification_dashboard.html",
        year=datetime.now().year,
        entries=serialize_mongo(entries),
        counts=counts,
        active_status=active_status,
        search_query=search_query,
        can_action=can_manage_verifications(),
    )


@app.route("/api/verification/action", methods=["POST"])
def api_verification_action():
    if "discord_id" not in session or not can_manage_verifications():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip().lower()
    reason = (data.get("reason") or "").strip()

    if action not in {"approve", "deny", "tag_not_found", "no_tag", "no_pfp"}:
        return jsonify({"error": "Invalid action"}), 400

    try:
        message_id = int(data.get("message_id"))
        user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Missing or invalid message_id/user_id"}), 400

    bot_base = os.getenv("BOT_WEBHOOK_URL")
    bot_key = os.getenv("BOT_WEBHOOK_KEY")
    if not bot_base or not bot_key:
        return jsonify({"error": "Missing bot webhook configuration"}), 500

    payload = {
        "user_id": user_id,
        "message_id": message_id,
        "action": action,
        "reason": reason or None,
        "mod_username": session.get("username", "Website Moderator"),
        "mod_id": session.get("discord_id"),
    }

    try:
        bot_response = requests.post(
            f"{bot_base.rstrip('/')}/webhook/verify",
            json=payload,
            headers={"Authorization": bot_key},
            timeout=8,
        )
    except Exception as e:
        return jsonify({"error": f"Failed to contact bot: {e}"}), 502

    if not bot_response.ok:
        try:
            error_payload = bot_response.json()
        except Exception:
            error_payload = {"error": bot_response.text or "Bot webhook failed"}
        return jsonify(error_payload), bot_response.status_code

    status_map = {
        "approve": "approved",
        "deny": "denied",
        "tag_not_found": "tag_not_found",
        "no_tag": "no_tag",
        "no_pfp": "no_pfp",
    }

    client = get_db()
    verify_col = client["log"]["verify"]
    update_doc = {
        "status": status_map[action],
        "reviewed_at": datetime.utcnow(),
        "reviewed_by": session.get("username", "Website Moderator"),
        "reviewed_by_id": session.get("discord_id"),
    }
    if reason:
        update_doc["review_reason"] = reason

    verify_col.update_one(
        {"discord_message_id": message_id},
        {"$set": update_doc},
    )

    return jsonify({"success": True, "status": status_map[action]})


@app.route("/api/verification/delete", methods=["POST"])
def api_verification_delete():
    if "discord_id" not in session or not can_manage_verifications():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}

    try:
        message_id = int(data.get("message_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Missing or invalid message_id"}), 400

    client = get_db()
    verify_col = client["log"]["verify"]
    result = verify_col.delete_one({"discord_message_id": message_id})

    if result.deleted_count == 0:
        return jsonify({"error": "Verification record not found"}), 404

    return jsonify({"success": True, "deleted": True})



@app.route("/dashboard/update-support-role", methods=["POST"])
def update_support_role():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    # Check if JSON
    if request.is_json:
        data = request.get_json()
        ticket_type = data.get("ticket_type")
        role_id = data.get("role_id")
    else:
        ticket_type = request.form.get("ticket_type")
        role_id = request.form.get("role_id")

    if not ticket_type or not role_id:
        return "Missing ticket type or role ID", 400

    client= get_db()
    support_col = client["Website"]["Support_settings"]
    support_col.update_one(
        {"_id": ticket_type.strip()},
        {"$set": {"role_id": int(role_id)}},
        upsert=True
    )

    if request.is_json:
        return jsonify({"message": "Updated"}), 200
    return redirect("/dashboard")


@app.route("/api/update-setting", methods=["POST"])
def update_setting():
    if not is_staff():
        return "Unauthorized", 403    
    if "discord_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(force=True)
    key = data.get("key")
    value = data.get("value")

    if key != "prefix":
        return jsonify({"error": "Invalid setting"}), 400

    client= get_db()
    settings_col = client["Website"]["bot_settings"]
    settings_col.update_one({"_id": "settings"}, {"$set": {key: value}}, upsert=True)

    return jsonify({"message": "Prefix updated successfully!"})

@app.route("/giveaway-dashboard")
def giveaway_dashboard():
    if not is_staff():
        return redirect("/")

    return render_template(
        "giveaway_dashboard.html",
        BOT_WEBHOOK_KEY=os.getenv("BOT_WEBHOOK_KEY"),
        username=session.get("username", "Unknown"),
        year=datetime.now().year
    )




@app.route("/api/giveaways/edit/<message_id>", methods=["POST"])
def edit_giveaway(message_id):
    if not is_staff():
        return "Unauthorized", 403    
        
    if "discord_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.json if request.is_json else request.get_json()
        payload = {
            "message_id": message_id,
            "updates": data
        }

        webhook_url = os.getenv("BOT_WEBHOOK_URL") + "/webhook/edit-giveaway"
        headers = {"Authorization": os.getenv("BOT_WEBHOOK_KEY", "")}
        res = requests.post(webhook_url, json=payload, headers=headers)

        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@csrf.exempt
@app.route("/api/giveaways", methods=["GET"])
def get_giveaways():
    if "discord_id" not in session:
        return jsonify({"active": [], "ended": []})
    guild_id = "959220051427340379"  # your server ID
    try:
        role_mapping = fetch_role_mapping(guild_id)
    except Exception as e:
        print(f"[API Giveaways] Failed to fetch role mapping: {e}")
        role_mapping = {}


    now_ts = time.time()

    client= get_db()
    db = client["Giveaway"]
    giveaways = []
    ended_giveaways = []

    for g in db["current_giveaways"].find({"ended": False}):
        end = g.get("end_time")
        if not end:
            continue
        if end.timestamp() < now_ts:
            continue

        delta = int(end.timestamp() - now_ts)
        minutes = (delta % 3600) // 60
        ends_in = f"{delta // 3600}h {minutes}m"
        participants = g.get("participants") or {}

        giveaways.append({
            "prize": g.get("prize", "N/A"),
            "winners": g.get("winners_count", 1),
            "message_id": str(g.get("message_id")),
            "entry_count": sum(participants.values()),
            "participant_count": len(participants),
            "ends_in": ends_in,
            "host_id": g.get("host_id"),
            "required_role_id": g.get("required_role_id"),
            "required_role_name": role_mapping.get(str(g.get("required_role_id")), {}).get("name") if g.get("required_role_id") else None,
            "color": g.get("color")
        })

    recently_ended = list(
        db["current_giveaways"]
        .find({"ended": True})
        .sort("end_time", -1)
        .limit(10)
    )

    for g in recently_ended:
        end_time = g.get("end_time")
        if not end_time:
            continue

        ended_giveaways.append({
            "prize": g.get("prize", "N/A"),
            "winners": g.get("winners_count", 1),
            "message_id": str(g.get("message_id")),
            "ended_at": end_time.strftime("%Y-%m-%d %H:%M")
        })

    return jsonify({
        "active": giveaways,
        "ended": ended_giveaways
    })


@app.route("/api/giveaways/recent", methods=["GET"])
@csrf.exempt
def recent_giveaways():
    if "discord_id" not in session:
        return jsonify([])

    skip = int(request.args.get("skip", 0))
    limit = int(request.args.get("limit", 9))

    client= get_db()
    db = client["Giveaway"]
    userdb = client["Website"]["usernames"]

    ended = list(db["current_giveaways"]
                    .find({"ended": True})
                    .sort("end_time", -1)
                    .skip(skip)
                    .limit(limit))

    # Collect host + winner IDs
    host_ids = [str(g.get("host_id")) for g in ended if g.get("host_id")]
    winner_ids = [str(uid) for g in ended for uid in g.get("winners", [])]

    # Fetch profiles in one batch
    user_profiles = userdb.find({"_id": {"$in": list(set(host_ids + winner_ids))}})
    user_map = {u["_id"]: u for u in user_profiles}

    results = []
    for g in ended:
        host_id = str(g.get("host_id"))
        host = user_map.get(host_id, {})
        
        winner_buttons = []
        for uid in g.get("winners", []):
            u = user_map.get(str(uid))
            winner_buttons.append({
                "id": str(uid),
                "name": u.get("display_name") or u.get("username") if u else f"User {uid}"
            })

        results.append({
            "prize": g.get("prize", "N/A"),
            "winners": g.get("winners_count", 1),
            "message_id": str(g.get("message_id")),
            "ended_at": g.get("end_time").strftime("%Y-%m-%d %H:%M"),
            "host_name": host.get("display_name", f"<@{host_id}>"),
            "host_avatar": host.get("avatar", "https://cdn.discordapp.com/embed/avatars/0.png"),
            "winner_buttons": winner_buttons,
        })

    return jsonify(results)




@app.route("/api/giveaways/end/<message_id>", methods=["POST"])
def end_giveaway(message_id):
    if not is_staff():
        return "Unauthorized", 403    

    if "discord_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        webhook_url = os.getenv("BOT_WEBHOOK_URL") + "/webhook/end-giveaway"
        headers = {"Authorization": os.getenv("BOT_WEBHOOK_KEY", "")}
        payload = {
            "message_id": int(message_id),
            "action": "end"
        }

        res = requests.post(webhook_url, json=payload, headers=headers)
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@csrf.exempt
@app.route("/api/giveaways/winners/<message_id>")
def get_winners(message_id):
    try:
        client= get_db()
        db = client["Giveaway"]
        g = db["current_giveaways"].find_one({"message_id": int(message_id)})
        if not g or "winners" not in g or not g["winners"]:
            return jsonify([])

        user_ids = g["winners"]

        # Use the usernames collection (not hayday.level)
        user_db = client["Website"]["usernames"]
        found_users = list(user_db.find({"_id": {"$in": [str(uid) for uid in user_ids]}}))
        user_map = {str(u["_id"]): u for u in found_users}

        # Build result with avatar + display name fallback
        result = []
        for uid in user_ids:
            user = user_map.get(str(uid))
            result.append({
                "id": str(uid),
                "username": user.get("display_name", f"<@{uid}>") if user else f"<@{uid}>",
                "avatar": user.get("avatar") if user else None
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    

@app.route("/api/giveaways/delete", methods=["POST"])
def delete_giveaway():
    if not is_staff():
        return "Unauthorized", 403

    data = request.get_json()
    message_id = int(data.get("message_id"))

    if not message_id:
        return jsonify({"error": "Missing message ID"}), 400

    try:
        client= get_db()
        collection = client["Giveaway"]["current_giveaways"]
        giveaway = collection.find_one({"message_id": message_id})

        if not giveaway:
            return jsonify({"error": "Giveaway not found"}), 404

        # Delete from Discord
        bot_token = os.getenv("DISCORD_BOT_TOKEN")
        headers = {"Authorization": f"Bot {bot_token}"}
        channel_id = giveaway.get("channel_id")
        if channel_id:
            try:
                requests.delete(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}",
                    headers=headers
                )
            except Exception as e:
                print(f"[Force Delete] Discord message delete failed: {e}")

        # Delete from DB
        collection.delete_one({"message_id": message_id})
        return jsonify({"message": "Giveaway deleted successfully."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    

@app.route("/api/giveaways/reroll-specific", methods=["POST"])
def reroll_specific():
    if not is_staff():
        return "Unauthorized", 403    
    token = request.headers.get("Authorization") or session.get("discord_id")
    if not token:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    message_id = int(data["message_id"])
    user_id = int(data["user_id"])

    try:
        reroll_url = os.getenv("BOT_REROLL_URL")
        r = requests.post(
            reroll_url,
            json={"message_id": message_id, "user_id": user_id},
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
        )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/giveaways/reroll/<message_id>", methods=["POST"])
def reroll_giveaway(message_id):
    if not is_staff():
        return "Unauthorized", 403

    if "discord_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        webhook_url = os.getenv("BOT_WEBHOOK_URL") + "/webhook/reroll-giveaway"
        headers = {"Authorization": os.getenv("BOT_WEBHOOK_KEY", "")}
        payload = {"message_id": int(message_id)}

        res = requests.post(webhook_url, json=payload, headers=headers)
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@csrf.exempt
@app.route("/giveaway/join", methods=["POST"])
def join_giveaway_web():
    if "discord_id" not in session:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Not logged in"}), 401
        return redirect("/login")

    discord_id = str(session["discord_id"])
    message_id = request.form.get("message_id")

    # rate limit (same as you have)
    now = time.time()
    rate_key = f"join:{discord_id}"
    last_attempt = rate_limit_cache.get(rate_key, 0)
    if now - last_attempt < 3:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "You are joining too fast. Please wait a few seconds."}), 429
        flash("⚠️ You're joining giveaways too fast. Please wait.")
        return redirect("/giveaways")
    rate_limit_cache[rate_key] = now

    user_roles = [int(r) for r in (session.get("roles") or [])]
    booster_role_id = 975188431636418681

    client= get_db()
    col = client["Giveaway"]["current_giveaways"]
    try:
        mid = int(message_id)
    except (TypeError, ValueError):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Invalid message id"}), 400
        flash("❌ Invalid giveaway link.")
        return redirect("/giveaways")

    giveaway = col.find_one({"message_id": mid})

    if not giveaway or giveaway.get("ended"):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Giveaway ended or not found"}), 400
        flash("❌ Giveaway not found or has ended.")
        return redirect("/giveaways")

    # Support list of required role IDs (OR) with legacy fallback
    required_ids_raw = list(giveaway.get("required_role_ids") or [])
    legacy = giveaway.get("required_role_id")
    if legacy not in (None, "", 0):
        required_ids_raw.append(legacy)

    # compare as ints to match your current session role ints
    required_ids = [int(x) for x in required_ids_raw if x not in (None, "", 0)]

    # Eligibility (OR)
    has_required = (len(required_ids) == 0) or any(rid in user_roles for rid in required_ids)
    has_booster = booster_role_id in user_roles

    boosters_bypass = bool(giveaway.get("boosters_bypass", True))
    can_booster_bypass = has_booster and boosters_bypass

    # Require confirm only when using booster bypass (i.e., lacking all required but boosters can bypass)
    requires_confirm = (len(required_ids) > 0) and (not has_required) and can_booster_bypass
    if requires_confirm and request.form.get("confirm") != "on":
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Please confirm you understand the extra requirements."}), 400
        flash("⚠️ Please confirm you understand the extra requirements.")
        return redirect("/giveaways")

    # Final eligibility
    if not (has_required or can_booster_bypass):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "You don't have the required role"}), 403
        flash("❌ You don't have the required role to enter this giveaway.")
        return redirect("/giveaways")

    participants = giveaway.get("participants", {})
    if discord_id in participants:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Already entered"}), 409
        flash("❌ You are already entered in this giveaway.")
        return redirect("/giveaways")

    extra_entries = 2 if has_booster else 1
    participants[discord_id] = extra_entries

    col.update_one({"message_id": mid}, {"$set": {"participants": participants}})

    try:
        requests.post(
            os.getenv("BOT_WEBHOOK_URL") + "/webhook/refresh-giveaway",
            json={"message_id": mid},
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
            timeout=5
        )
    except Exception as e:
        print(f"⚠️ Failed to sync with bot: {e}")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "joined", "entries": extra_entries})

    flash("✅ You have joined the giveaway.")
    return redirect("/giveaways")

@csrf.exempt
@app.route("/giveaway/leave", methods=["POST"])
def leave_giveaway_web():
    if "discord_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    message_id = request.form.get("message_id")
    discord_id = str(session["discord_id"])

    client= get_db()
    col = client["Giveaway"]["current_giveaways"]

    try:
        mid = int(message_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid message id"}), 400

    giveaway = col.find_one({"message_id": mid})

    if not giveaway or giveaway.get("ended"):
        return jsonify({"error": "Giveaway not found or ended"}), 400

    participants = giveaway.get("participants", {})
    if discord_id not in participants:
        return jsonify({"error": "You're not in this giveaway."}), 400

    del participants[discord_id]
    col.update_one({"message_id": mid}, {"$set": {"participants": participants}})

    try:
        requests.post(
            os.getenv("BOT_WEBHOOK_URL") + "/webhook/refresh-giveaway",
            json={"message_id": mid},
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
            timeout=5
        )
    except Exception as e:
        print(f"⚠️ Failed to sync with bot: {e}")

    return jsonify({"success": True})


@app.route("/api/giveaways/reroll", methods=["POST"])
def reroll_giveaway_post():
    if not is_staff():
        return "Unauthorized", 403

    if "discord_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    try:
        data = request.get_json(force=True)
        message_id = int(data.get("message_id"))
        action = data.get("action", "reroll")
    except Exception as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400

    bot_url = os.getenv("BOT_WEBHOOK_URL")
    auth_header = os.getenv("BOT_WEBHOOK_KEY")

    try:
        res = requests.post(
            bot_url,
            json={"message_id": message_id, "action": action},
            headers={"Authorization": auth_header}
        )
        print("✅ Forwarded reroll to bot:", res.status_code, res.text)
        return res.json(), res.status_code
    except Exception as e:
        print("❌ Failed to contact bot:", e)
        return jsonify({"error": f"Request failed: {e}"}), 500

@app.route("/competition")
def competition_home():
    meta = page_meta(
        title="Monthly Farm Design Competition - HayDay 🐰",
        description="Submit your design and vote on the best farms. Win huge coin prizes each month!",
        image=url_for("static", filename="img/competition_share.jpg", _external=True),
        url="https://www.hayday.info/competition",
    )    
    # Reuse the same phase/comp_id logic as gallery
    phase, comp_id = _phase_today()
    from flask import g
    g.comp_id_for_theme = comp_id     # <- makes current_theme available everywhere
    theme = _theme_for(comp_id)       # <- explicit object if you want to pass it    
    cal = _comp_strings_for(comp_id, submit_end_day=25)
    # Use your preferred inline client pattern
    client= get_db()
    db = client["Website"]
    entries_col = db["CompEntries"]

    q = {"comp_id": comp_id}

    # Pull a handful for the hero (latest first)
    cursor = (
        entries_col.find(q)
        .sort("created_at", -1)
        .limit(12)
    )
    docs = list(cursor)

    # --- normalize fields for template (handles different key names)
    def _img_url(d):
        return (
            d.get("image_url")
            or d.get("cdn_url")
            or d.get("r2_url")
            or d.get("url")
            or "/static/img/placeholder.jpg"
        )

    def _username(d):
        return d.get("username") or d.get("display_name") or d.get("discord_name") or "Anonymous"

    entries = [
        {
            "image_url": _img_url(d),
            "username": _username(d),
            "submitted_at": d.get("created_at") or d.get("submitted_at"),
        }
        for d in docs
    ]

    # Optional debug logging if you still see empty results
    if not entries:
        app.logger.info(f"[competition_home] No entries for comp_id={comp_id}. "
                        f"Example doc fields? created_at/comp_id set?")
    prizes = {
        "first":  "75k Server coins + 1 month of Discord Nitro",
        "second": "50k Server coins",
        "third":  "25k Server coins",
    }
    return render_template(
        "competition_home.html",
        meta=meta,
        entries=entries,
        phase=phase,
        comp_id=comp_id,
        theme=theme, 
        prizes=prizes,  
        **cal,
    )


@csrf.exempt
@app.route("/competition/gallery")
def competition_gallery():
    phase, comp_id = _phase_today()
    from flask import g
    g.comp_id_for_theme = comp_id
    theme = _theme_for(comp_id)
    cal = _comp_strings_for(comp_id, submit_end_day=25)

    viewer_id = session.get("discord_id")
    sort_mode = request.args.get("sort", "random" if phase == "voting" else "newest")
    if phase == "voting" and sort_mode not in {"random", "newest"}:
        sort_mode = "random"
    elif phase == "results" and sort_mode not in {"newest", "random", "top"}:
        sort_mode = "newest"
    elif phase not in {"voting", "results"} and sort_mode not in {"newest", "random"}:
        sort_mode = "newest"
    PER_PAGE = 16

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1

    client= get_db()
    db = client["Website"]
    entries_col = db["CompEntries"]
    votes_col = db["CompVotes"]

    q_entries = {"comp_id": comp_id}
    total = entries_col.count_documents(q_entries)

    counts = {}
    show_vote_counts = (phase == "results")
    if show_vote_counts:
        # --- build vote counts (all keys as strings) ---
        pipeline = [
            {"$match": {"comp_id": comp_id}},
            {"$group": {"_id": "$entry_id", "count": {"$sum": 1}}},
        ]
        for doc in votes_col.aggregate(pipeline):
            counts[str(doc["_id"])] = doc["count"]

        # ensure zeros
        for _e in entries_col.find(q_entries, {"_id": 1}):
            k = str(_e["_id"])
            if k not in counts:
                counts[k] = 0

    # --- fetch entries per your sort ---
    if show_vote_counts and sort_mode == "top":
        # Vote-based sorting is only public once results are live.
        rank_pipeline = [
            {"$match": {"comp_id": comp_id}},
            {"$group": {"_id": "$entry_id", "votes": {"$sum": 1}}},
            {"$sort": {"votes": -1, "_id": 1}},
            {"$skip": (page - 1) * PER_PAGE},
            {"$limit": PER_PAGE},
        ]
        ranked = list(votes_col.aggregate(rank_pipeline))
        ranked_ids = [ObjectId(r["_id"]) for r in ranked if ObjectId.is_valid(str(r["_id"]))]

        if len(ranked_ids) < PER_PAGE:
            have = set(ranked_ids)
            zeros_cursor = entries_col.find(
                {"comp_id": comp_id, "_id": {"$nin": list(have)}}
            ).sort("created_at", -1)
            for e in zeros_cursor:
                ranked_ids.append(e["_id"])
                if len(ranked_ids) >= PER_PAGE:
                    break

        docs = list(entries_col.find({"_id": {"$in": ranked_ids}}))
        idx = {rid: i for i, rid in enumerate(ranked_ids)}
        entries = sorted(docs, key=lambda d: idx[d["_id"]])

    elif sort_mode == "newest":
        # newest with normal pagination
        entries = list(
            entries_col.find(q_entries)
            .sort("created_at", -1)
            .skip((page - 1) * PER_PAGE)
            .limit(PER_PAGE)
        )

    else:
        # --- RANDOM (default during voting) ---
        # Stable per day (Copenhagen time handled by _phase_today())
        seed_str = f"{comp_id}-{date.today().isoformat()}"
        seed_bytes = seed_str.encode("utf-8")

        # Get just IDs to avoid pulling all fields
        id_list = [doc["_id"] for doc in entries_col.find(q_entries, {"_id": 1})]

        # Deterministic hash score per _id for the day
        def rand_score(oid):
            h = hashlib.sha1(seed_bytes + str(oid).encode("utf-8")).digest()
            # use first 8 bytes as big-endian int for sorting
            return int.from_bytes(h[:8], "big")

        id_list.sort(key=rand_score)  # ascending is fine; it's "randomized"

        # paginate IDs, then fetch full docs for this page
        start = (page - 1) * PER_PAGE
        end = start + PER_PAGE
        page_ids = id_list[start:end]
        docs = list(entries_col.find({"_id": {"$in": page_ids}}))
        pos = {rid: i for i, rid in enumerate(page_ids)}
        entries = sorted(docs, key=lambda d: pos[d["_id"]])

    # --- my current vote, normalized ---
    my_vote = None
    if viewer_id:
        my_vote = votes_col.find_one({"comp_id": comp_id, "voter_id": str(viewer_id)})
        if my_vote and isinstance(my_vote.get("entry_id"), ObjectId):
            my_vote["entry_id"] = str(my_vote["entry_id"])

    return render_template(
        "competition_gallery.html",
        phase=phase,
        comp_id=comp_id,
        entries=entries,
        total=total,
        page=page,
        total_pages=max((total + PER_PAGE - 1) // PER_PAGE, 1),
        has_prev=(page > 1),
        has_next=(page * PER_PAGE < total),
        my_vote=my_vote,
        viewer_id=str(viewer_id) if viewer_id else None,
        sort_mode=sort_mode,
        vote_counts=counts,
        show_vote_counts=show_vote_counts,
        theme=theme,  
        **cal,
    )



@csrf.exempt
@app.route("/competition/submit", methods=["GET", "POST"])
def competition_submit():
    phase, comp_id = _phase_today()

    client = get_db()
    db = client["Website"]
    entries_col = db["CompEntries"]
    votes_col   = db["CompVotes"]  # <-- for "Your vote" tile

    # --- Work out submit_status for the UI ---
    discord_id = session.get("discord_id")
    roles = [str(r) for r in (session.get("roles") or [])]
    is_member = bool(session.get("is_member", False))
    submission_ban = _competition_submission_ban(comp_id, str(discord_id)) if discord_id else None

    if not discord_id:
        submit_status = "not_logged_in"
    elif submission_ban:
        submit_status = "banned"
    elif not is_member:
        submit_status = "not_in_guild"
    elif str(UNVERIFIED_ROLE_ID) in roles:
        submit_status = "not_verified"
    else:
        submit_status = "ok"

    # Common vars for template
    username = session.get("username", "Anonymous")
    try:
        month_label = datetime.strptime(comp_id, "%Y-%m").strftime("%B %Y")
    except ValueError:
        month_label = comp_id  # fallback if the format isn't YYYY-MM

    # --- GET ---
    if request.method == "GET":
        theme = _theme_for(comp_id)
        from flask import g
        g.comp_id_for_theme = comp_id
        user_key = str(discord_id) if discord_id else f"anon-{request.remote_addr}"
        entry = entries_col.find_one({"comp_id": comp_id, "user_id": user_key})
        submit_reward_claimed = _competition_has_reward_claim(comp_id, str(discord_id), "submit") if discord_id else False

        # Fetch "your vote" (during voting) and the voted image URL
        my_vote = None
        entries_map = {}
        if discord_id:
            my_vote = votes_col.find_one({"comp_id": comp_id, "voter_id": str(discord_id)})
            if my_vote:
                voted = entries_col.find_one({"_id": ObjectId(my_vote["entry_id"])})
                if voted:
                    entries_map[my_vote["entry_id"]] = voted.get("image_url", "")

        return render_template(
            "competition_submit.html",
            comp_id=comp_id,
            month_label=month_label,
            phase=phase,
            entry=entry,
            submit_status=submit_status,
            submission_ban=submission_ban,
            submit_reward_claimed=submit_reward_claimed,
            my_vote=my_vote,          # <-- enables "Your vote" section
            entries_map=entries_map,  # <-- image lookup for your vote
            GUILD_ID=GUILD_ID,        # used by template links
            theme=theme,
        )

    # --- POST (only if allowed) ---
    if submit_status != "ok":
        if submit_status == "banned":
            flash("You are blocked from entering this contest month because a previous submission was removed by staff.", "error")
            return redirect(url_for("competition_submit"))
        flash("Please log in and verify in Discord to submit.", "error")
        return redirect(url_for("competition_submit"))

    if phase != "submit":
        flash("Submissions are closed for this month.", "error")
        return redirect(url_for("competition_gallery"))

    file = request.files.get("image")
    if not file or file.filename == "":
        flash("Please choose an image.", "error")
        return redirect(url_for("competition_submit"))

    # (Optional) enforce 鈮?25 MB on the server as well
    file.seek(0, 2)  # end
    size = file.tell()
    file.seek(0)
    if size > 25 * 1024 * 1024:
        flash("Image too large (max 25 MB).", "error")
        return redirect(url_for("competition_submit"))

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in {"png", "jpg", "jpeg"}:
        flash("Invalid file type. Use PNG or JPG.", "error")
        return redirect(url_for("competition_submit"))
    
    # Pull user identity from session
    display_name  = session.get("display_name")        # e.g., server nickname or username
    username_tag  = session.get("username")            # e.g., "Vroomie#1234"
    discord_id    = session.get("discord_id")          # numeric string

    # Pull user input
    caption = request.form.get("caption", "")          # adjust to your form field name
    filename = getattr(file, "filename", "") or ""
    to_scan = " ".join(filter(None, [caption, filename]))


    if contains_identifying_text(to_scan, display_name, username_tag, discord_id):
        flash("鉂?Submissions must be anonymous. Do not include your name, Discord tag, ID, or mentions in the filename or caption.", "error")
        return redirect(url_for("competition_submit"))  # adjust endpoint name if different

    # Upload to R2 (resized)
    unique_name = uuid.uuid4().hex
    try:
        buf, content_type, ext_out = resize_to_max_edge(file)  # returns JPEG 85%
    except ValueError:
        flash("Invalid or corrupted image file. Please choose a different PNG or JPG.", "error")
        return redirect(url_for("competition_submit"))
    object_key = f"{comp_id}/{unique_name}.{ext_out}"
    image_url = r2_put_object(buf, object_key, content_type)

    # Match UI limit
    caption = (request.form.get("caption") or "").strip()[:35]

    existing_entry = entries_col.find_one({"comp_id": comp_id, "user_id": str(discord_id)}, {"_id": 1})
    entries_col.update_one(
        {"comp_id": comp_id, "user_id": str(discord_id)},
        {"$set": {
            "username": username,
            "user_id": str(discord_id),
            "image_url": image_url,
            "caption": caption,
            "created_at": datetime.now(timezone.utc),
            "ip": request.remote_addr,
        }},
        upsert=True
    )
    # clear cached results for this competition month
    for k in list(COMP_RESULTS_CACHE.keys()):
        if f":{comp_id}:" in k or k.startswith(f"results:{comp_id}:"):
            COMP_RESULTS_CACHE.pop(k, None)

    reward_granted, _ = _competition_try_grant_reward(
        comp_id,
        str(discord_id),
        "submit",
        COMP_SUBMIT_REWARD,
        meta={"entry_action": "create" if not existing_entry else "update"},
    )

    if reward_granted:
        flash(f"Submission saved! +{COMP_SUBMIT_REWARD:,} server coins awarded.", "success")
    elif existing_entry:
        flash("Submission updated!", "success")
    else:
        flash("Submission saved!", "success")
    # nicer loop: land back on Submit so they see their card (and later their vote)
    return redirect(url_for("competition_submit"))

@app.route("/competition/results")
def competition_results():
    # Allow optional override: /competition/results?comp_id=YYYY-MM
    override = request.args.get("comp_id")

    phase, comp_id = _phase_today()  # e.g. ("submit"|"voting"|"results", "2025-11")

    # Target month: results month when in results, otherwise previous month unless overridden
    display_comp_id = (
        override.strip() if override
        else (comp_id if phase == "results" else _prev_comp_id(comp_id))
    )
    # Prevent viewing results for the active month (submit/voting)
    if phase != "results" and display_comp_id == comp_id:
        # Force fallback to previous month
        display_comp_id = _prev_comp_id(comp_id)

    from flask import g
    g.comp_id_for_theme = display_comp_id
    theme = _theme_for(display_comp_id)

    cache_key = f"results:{display_comp_id}:{phase}:{comp_id}"
    cached = COMP_RESULTS_CACHE.get(cache_key)
    now_ts = time.time()

    if cached and cached["expires"] > now_ts:
        entries = cached["entries"]
        counts = cached["counts"]
        month_options = cached["month_options"]
    else:
        client= get_db()
        db = client["Website"]
        entries_col = db["CompEntries"]
        usernames_col = db["usernames"]

        entries = list(entries_col.find({"comp_id": display_comp_id}))

        needed_user_ids = list({
            str(e.get("user_id"))
            for e in entries
            if e.get("user_id")
        })

        username_map = {}
        if needed_user_ids:
            username_map = {
                str(u["_id"]): (u.get("display_name") or u.get("username") or "Anonymous")
                for u in usernames_col.find(
                    {"_id": {"$in": needed_user_ids}},
                    {"_id": 1, "display_name": 1, "username": 1}
                )
            }

        for e in entries:
            e["display_name"] = username_map.get(
                str(e.get("user_id")),
                e.get("username") or "Anonymous"
            )

        counts = _vote_counts_for(display_comp_id, client)

        comp_ids = sorted(entries_col.distinct("comp_id"), reverse=True)

        if phase != "results":
            comp_ids = [cid for cid in comp_ids if cid != comp_id]

        month_options = []
        for cid in comp_ids:
            try:
                y, m = map(int, cid.split("-"))
                label = datetime(y, m, 1).strftime("%B %Y")
            except Exception:
                label = cid
            month_options.append({"comp_id": cid, "label": label})

        COMP_RESULTS_CACHE[cache_key] = {
            "expires": now_ts + COMP_RESULTS_CACHE_TTL,
            "entries": entries,
            "counts": counts,
            "month_options": month_options,
        }

    def tie_ts(e) -> float:
        """Return a UTC timestamp for deterministic tie-breaks."""
        t = e.get("created_at")
        if t:
            # PyMongo usually returns naive UTC; normalize to aware UTC then to epoch
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            else:
                t = t.astimezone(timezone.utc)
            return t.timestamp()

        # Fallback: ObjectId.generation_time is aware UTC
        oid = e.get("_id")
        gt = getattr(oid, "generation_time", None)
        if gt:
            return gt.timestamp()

        # Last resort: very old timestamp so these sort last among same-vote ties
        return 0.0

    # Sort by votes (desc), then by earliest submission time (asc) as deterministic tie-break
    entries_sorted = sorted(
        entries,
        key=lambda e: (-counts.get(str(e["_id"]), 0), tie_ts(e), str(e["_id"])),  # tertiary by _id for extra stability
    )

    # --- helpers ---
    def paginate(items, page, per_page):
        total = len(items)
        pages = max(1, ceil(total / per_page))
        page = max(1, min(int(page or 1), pages))
        start = (page - 1) * per_page
        end = start + per_page
        return {"items": items[start:end], "page": page, "pages": pages, "total": total, "per_page": per_page}

    # Read query params
    score_page = request.args.get("score_page", 1, type=int)
    grid_page  = request.args.get("grid_page", 1, type=int)

    # Pagination
    score = paginate(entries_sorted, score_page, per_page=10)   # Full scoreboard
    grid  = paginate(entries_sorted, grid_page,  per_page=16)   # 4x4 "All entries"
    # Label for the DISPLAY month (after any fallback)
    try:
        month_label = datetime.strptime(display_comp_id, "%Y-%m").strftime("%B %Y")
    except ValueError:
        month_label = display_comp_id

    # CTA banner depends on CURRENT phase (not display month)
    banner = None
    if phase == "submit":
        banner = {"text": "Submissions are open. Upload your design now.",
                  "cta_href": url_for("competition_submit"),
                  "cta_label": "Go submit your farm"}
    elif phase == "voting":
        banner = {"text": "Voting is live. Cast your votes for this month.",
                  "cta_href": url_for("competition_gallery"),
                  "cta_label": "Go vote now"}
    prizes = {
        "first":  "75k Server coins + 1 month of Discord Nitro",
        "second": "50k Server coins",
        "third":  "25k Server coins",
    }

    return render_template(
        "competition_results.html",
        comp_id=display_comp_id,
        month_label=month_label,
        banner=banner,
        theme=theme,


        entries=entries_sorted,
        counts=counts,


        score_items=score["items"],
        score_page=score["page"],
        score_pages=score["pages"],
        score_total=score["total"],


        grid_items=grid["items"],
        grid_page=grid["page"],
        grid_pages=grid["pages"],
        grid_total=grid["total"],


        is_admin=is_staff(),
        prizes=prizes,

        month_options=month_options,
    )


@csrf.exempt
@app.route("/competition/delete", methods=["POST"])
def competition_delete():
    phase, comp_id = _phase_today()
    discord_id = session.get("discord_id")
    if not discord_id:
        return redirect(url_for("competition_submit"))

    if phase != "submit":
        flash("Edits are locked during voting/results.", "error")
        return redirect(url_for("competition_submit"))

    if _competition_has_reward_claim(comp_id, str(discord_id), "submit"):
        flash("You can't delete this submission after claiming the submit reward. You can still replace the image or edit the title.", "error")
        return redirect(url_for("competition_submit"))

    client = get_db()
    db = client["Website"]
    db["CompEntries"].delete_one({"comp_id": comp_id, "user_id": str(discord_id)})
    for k in list(COMP_RESULTS_CACHE.keys()):
        if f":{comp_id}:" in k or k.startswith(f"results:{comp_id}:"):
            COMP_RESULTS_CACHE.pop(k, None)
    flash("Submission deleted.", "success")
    return redirect(url_for("competition_submit"))

@app.get("/admin/competition/votes/<entry_id>")
def admin_competition_votes(entry_id):
    if not is_staff(): 
        return "Unauthorized", 403

    client = get_db()
    db = client["Website"]
    try:
        oid = ObjectId(entry_id)
    except Exception:
        return "Invalid entry id", 400

    entry = db["CompEntries"].find_one({"_id": oid})
    if not entry:
        abort(404)

    votes = list(db["CompVotes"]
                 .find({"comp_id": entry["comp_id"], "entry_id": str(oid)})
                 .sort("created_at", -1))
    # Optional: map usernames
    voter_ids = list({v["voter_id"] for v in votes})
    usernames = {u["_id"]: (u.get("display_name") or u.get("username") or u["_id"])
                 for u in db["usernames"].find({"_id": {"$in": voter_ids}})}
    for v in votes:
        v["voter_name"] = usernames.get(v["voter_id"], v["voter_id"])

    return render_template("competition_admin_votes.html", entry=entry, votes=votes)


@csrf.exempt
@app.post("/admin/competition/votes/<entry_id>/delete/<vote_id>")
def admin_competition_vote_delete(entry_id, vote_id):
    if not is_staff(): 
        return "Unauthorized", 403
    client = get_db()
    db = client["Website"]
    try:
        vo = ObjectId(vote_id)
    except Exception:
        return "Invalid vote id", 400
    db["CompVotes"].delete_one({"_id": vo})
    flash("Vote deleted.", "success")
    return redirect(url_for("admin_competition_votes", entry_id=entry_id))

@csrf.exempt
@app.post("/competition/update-caption")
def competition_update_caption():
    # must be logged in & during submit phase
    discord_id = session.get("discord_id")
    if not discord_id:
        return jsonify(ok=False, error="Login required."), 401

    phase, comp_id = _phase_today()
    if phase != "submit":
        return jsonify(ok=False, error="Edits are locked during voting/results."), 400
    if _competition_submission_ban(comp_id, str(discord_id)):
        return jsonify(ok=False, error="You are blocked from editing submissions for this contest month."), 403

    new_caption = (request.form.get("caption") or "").strip()[:35]

    client = get_db()
    db = client["Website"]

    # only allow editing *your own* entry for the current comp
    entry = db["CompEntries"].find_one({"comp_id": comp_id, "user_id": str(discord_id)})
    if not entry:
        return jsonify(ok=False, error="No submission found for your account."), 404

    db["CompEntries"].update_one(
        {"_id": entry["_id"]},
        {"$set": {"caption": new_caption}}
    )

    return jsonify(ok=True, caption=new_caption)

@csrf.exempt
@app.post("/admin/competition/votes/<entry_id>/delete-all")
def admin_competition_vote_delete_all(entry_id):
    if not is_staff(): 
        return "Unauthorized", 403
    client = get_db()
    db = client["Website"]
    # ensure entry exists
    try:
        oid = ObjectId(entry_id)
    except Exception:
        return "Invalid entry id", 400
    entry = db["CompEntries"].find_one({"_id": oid})
    if not entry:
        abort(404)
    db["CompVotes"].delete_many({"comp_id": entry["comp_id"], "entry_id": str(oid)})
    flash("All votes for this entry were deleted.", "success")
    return redirect(url_for("admin_competition_votes", entry_id=entry_id))

@csrf.exempt
@app.route("/competition/vote", methods=["POST"])
def competition_vote():
    phase, comp_id = _phase_today()
    if phase != "voting":
        return jsonify({"ok": False, "error": "Voting is not open."}), 400

    voter_id = session.get("discord_id")
    if not voter_id:
        return jsonify({"ok": False, "error": "Login required."}), 401
    roles = [str(r) for r in (session.get("roles") or [])]
    if not bool(session.get("is_member", False)):
        return jsonify({"ok": False, "error": "You must be in the Discord server to vote."}), 403
    if str(UNVERIFIED_ROLE_ID) in roles:
        return jsonify({"ok": False, "error": "You must be verified in Discord to vote."}), 403

    payload = request.get_json(silent=True) or {}
    entry_id = request.form.get("entry_id") or payload.get("entry_id")
    overwrite = (request.form.get("overwrite") == "true") or (payload.get("overwrite") is True)

    if not entry_id:
        return jsonify({"ok": False, "error": "Missing entry_id."}), 400
    # Guard invalid ObjectId strings
    try:
        oid = ObjectId(entry_id)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid entry_id."}), 400

    client= get_db()
    db = client["Website"]
    entries = db["CompEntries"]
    votes = db["CompVotes"]
    votes.create_index([("comp_id", 1), ("voter_id", 1)], unique=True)

    e = entries.find_one({"_id": oid, "comp_id": comp_id})
    if not e:
        return jsonify({"ok": False, "error": "Entry not found for this competition."}), 404

    if str(e.get("user_id")) == str(voter_id):
        return jsonify({"ok": False, "error": "You cannot vote for your own entry."}), 403

    existing = votes.find_one({"comp_id": comp_id, "voter_id": str(voter_id)})

    def _as_str(x):
        try:
            if isinstance(x, ObjectId):
                return str(x)
        except Exception:
            pass
        return str(x) if x is not None else None

    new_entry_id = str(e["_id"])
    existing_entry_id = _as_str(existing["entry_id"]) if existing else None

    if not existing:
        try:
            votes.insert_one({
                "comp_id": comp_id,
                "voter_id": str(voter_id),
                "entry_id": new_entry_id,
                "created_at": datetime.now(timezone.utc),
            })
            reward_granted, _ = _competition_try_grant_reward(
                comp_id,
                str(voter_id),
                "vote",
                COMP_VOTE_REWARD,
                meta={"entry_id": new_entry_id},
            )
            # 猬囷笍 was changed: False
            return jsonify({
                "ok": True,
                "entry_id": new_entry_id,
                "changed": True,
                "reward_granted": reward_granted,
                "reward_amount": COMP_VOTE_REWARD if reward_granted else 0,
            })
        except DuplicateKeyError:
            # another request inserted first - re-fetch and continue below
            existing = votes.find_one({"comp_id": comp_id, "voter_id": str(voter_id)})
            existing_entry_id = _as_str(existing["entry_id"]) if existing else None

    if existing_entry_id == new_entry_id:
        return jsonify({"ok": True, "entry_id": new_entry_id, "changed": False})

    if not overwrite:
        return jsonify({
            "ok": False,
            "error": "Already voted for another entry.",
            "conflict": True,
            "current_entry_id": existing_entry_id,
        }), 409

    votes.update_one(
        {"comp_id": comp_id, "voter_id": str(voter_id)},
        {"$set": {"entry_id": new_entry_id, "created_at": datetime.now(timezone.utc)}}
    )
    return jsonify({"ok": True, "entry_id": new_entry_id, "changed": True})

@app.get("/api/competition/phase")
def api_competition_phase():
    phase, comp_id = _phase_today()
    return jsonify(ok=True, phase=phase, comp_id=comp_id, submit_open=(phase == "submit"))

@csrf.exempt
@app.post("/api/competition/submit-from-bot")
def api_competition_submit_from_bot():
    if not _bot_auth_ok(request):
        return jsonify(ok=False, error="Unauthorized"), 401

    phase, comp_id = _phase_today()
    if phase != "submit":
        return jsonify(ok=False, error="Submissions closed"), 400

    discord_id   = (request.form.get("discord_id") or "").strip()
    caption      = (request.form.get("caption") or "").strip()[:35]
    display_name = (request.form.get("display_name") or "").strip()   # NEW
    username_tag = (request.form.get("username") or "").strip()       # NEW (legacy tag like user#1234)
    file         = request.files.get("image")

    if not discord_id:
        return jsonify(ok=False, error="Missing discord_id"), 400
    submission_ban = _competition_submission_ban(comp_id, str(discord_id))
    if submission_ban:
        return jsonify(
            ok=False,
            error="User is banned from submitting for this contest month.",
            comp_id=comp_id,
            reason=submission_ban.get("reason", ""),
            image_url=submission_ban.get("image_url", ""),
        ), 403
    if not file or file.filename == "":
        return jsonify(ok=False, error="Missing image file"), 400

    # Size/type guard
    file.seek(0, 2); size = file.tell(); file.seek(0)
    if size > 25 * 1024 * 1024:
        return jsonify(ok=False, error="Image too large (max 25 MB)"), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in {"png", "jpg", "jpeg"}:
        return jsonify(ok=False, error="Invalid file type (png/jpg)"), 400

    # Upload resized
    unique_name = uuid.uuid4().hex
    try:
        buf, content_type, ext_out = resize_to_max_edge(file)
    except ValueError:
        return jsonify(ok=False, error="Invalid or corrupted image file"), 400
    object_key = f"{comp_id}/{unique_name}.{ext_out}"
    image_url = r2_put_object(buf, object_key, content_type)

    # Store entry (+names) and upsert usernames cache
    c= get_db()
    db = c["Website"]

    existing_entry = db["CompEntries"].find_one({"comp_id": comp_id, "user_id": str(discord_id)}, {"_id": 1})
    db["CompEntries"].update_one(
        {"comp_id": comp_id, "user_id": str(discord_id)},
        {"$set": {
            "user_id": str(discord_id),
            "image_url": image_url,
            "caption": caption,
            "display_name": display_name or username_tag,  # prefer display name
            "username": username_tag,                      # keep legacy tag too
            "created_at": datetime.now(timezone.utc),
            "ip": request.remote_addr,
        }},
        upsert=True
    )

    db["usernames"].update_one(  # handy for joins/backfills elsewhere
        {"_id": str(discord_id)},
        {"$set": {
            "display_name": display_name or username_tag,
            "username": username_tag,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True
    )

    reward_granted, _ = _competition_try_grant_reward(
        comp_id,
        str(discord_id),
        "submit",
        COMP_SUBMIT_REWARD,
        meta={"entry_action": "create" if not existing_entry else "update", "via": "bot"},
    )

    return jsonify(
        ok=True,
        comp_id=comp_id,
        image_url=image_url,
        caption=caption,
        reward_granted=reward_granted,
        reward_amount=COMP_SUBMIT_REWARD if reward_granted else 0,
    )


@csrf.exempt
@app.post("/api/competition/edit-caption-from-bot")
def api_competition_edit_caption_from_bot():
    if not _bot_auth_ok(request):
        return jsonify(ok=False, error="Unauthorized"), 401
    phase, comp_id = _phase_today()
    if phase != "submit":
        return jsonify(ok=False, error="Edits locked"), 400

    payload = request.get_json(silent=True) or {}
    discord_id = (payload.get("discord_id") or "").strip()
    caption = (payload.get("caption") or "").strip()[:35]
    if not discord_id:
        return jsonify(ok=False, error="Missing discord_id"), 400
    submission_ban = _competition_submission_ban(comp_id, str(discord_id))
    if submission_ban:
        return jsonify(ok=False, error="User is banned from editing submissions for this contest month."), 403

    db = get_db("Website")
    entry = db["CompEntries"].find_one({"comp_id": comp_id, "user_id": str(discord_id)})
    if not entry:
        return jsonify(ok=False, error="No submission found"), 404
    db["CompEntries"].update_one({"_id": entry["_id"]}, {"$set": {"caption": caption}})

    return jsonify(ok=True, caption=caption)

@csrf.exempt
@app.post("/api/competition/delete-from-bot")
def api_competition_delete_from_bot():
    if not _bot_auth_ok(request):
        return jsonify(ok=False, error="Unauthorized"), 401
    phase, comp_id = _phase_today()
    if phase != "submit":
        return jsonify(ok=False, error="Edits locked"), 400

    payload = request.get_json(silent=True) or {}
    discord_id = (payload.get("discord_id") or "").strip()
    if not discord_id:
        return jsonify(ok=False, error="Missing discord_id"), 400

    if _competition_has_reward_claim(comp_id, str(discord_id), "submit"):
        return jsonify(
            ok=False,
            error="Submit reward already claimed; deletion is locked for this month. Replace the submission instead.",
        ), 409

    db = get_db("Website")
    db["CompEntries"].delete_one({"comp_id": comp_id, "user_id": str(discord_id)})

    return jsonify(ok=True, deleted=True)

# Optional thumbnail prewarm
if os.getenv("WARM_THUMBS", "0") == "1":
    try:
        threading.Thread(
            target=lambda: prewarm_thumbs(size=THUMB_SIZE_DEFAULT, max_workers=12),
            daemon=True
        ).start()
        print("[thumbs] background prewarm thread started")
    except Exception as e:
        print("[thumbs] failed to start prewarm thread:", e)

try:
    threading.Thread(target=flush_pageview_buffer, daemon=True).start()
    print("[pageviews] flush thread started")
except Exception as e:
    print("[pageviews] failed to start:", e)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    env = os.getenv("FLASK_ENV", "prod")

    if env == "dev":
        logging.getLogger("livereload").setLevel(logging.WARNING)

        server = Server(app)
        server.watch('templates/')
        server.watch('static/')
        server.serve(host='127.0.0.1', port=port)
    else:
        app.run(host="0.0.0.0", port=port, threaded=True)
