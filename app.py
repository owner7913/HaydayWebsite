from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, get_flashed_messages,send_file, flash, Response, make_response, abort, stream_with_context
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, HiddenField
from wtforms.validators import DataRequired
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient
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
import logging
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
import json, time, re, unicodedata, requests
from bs4 import BeautifulSoup 
from concurrent.futures import ThreadPoolExecutor
import email.utils as eut
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib, mimetypes, os
from werkzeug.utils import secure_filename
from PIL import Image
import boto3
from botocore.client import Config
import io
import certifi, os
from botocore.config import Config
import socket as _socket
from calendar import monthrange
from zoneinfo import ZoneInfo
from pymongo.errors import DuplicateKeyError
from math import ceil
import random
from flask import jsonify
from datetime import datetime, timezone
from bson.errors import InvalidId
import math
print("[DEBUG] Flask-Limiter version:", flask_limiter.__version__)

R2_PUBLIC_HOST = os.getenv("R2_PUBLIC_HOST", "")  # e.g. img.hayday.info
WORKER_UPLOAD_URL = os.getenv("WORKER_UPLOAD_URL")
WORKER_UPLOAD_SECRET = os.getenv("WORKER_UPLOAD_SECRET")

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

# VERY TEMP storage just to see things working locally
COMP_ENTRIES = {}  # comp_id -> list of {image_url, username, caption, created_at}
USER_SUBMITTED = {}  # (comp_id, user_id) -> True

# Allow up to ~6 MB uploads (PNG/JPG up to 5 MB + overhead)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXT = {"png", "jpg", "jpeg"}
UPLOAD_ROOT = os.path.join(app.root_path, "static", "uploads")  # served by Flask static

THEMES = {
    1:  {"title": "Winter Warmth",     "desc": "Cozy up your farm with fireplaces, snowmen, and frosty barns."},
    2:  {"title": "Valentine’s Farm",  "desc": "Hearts, roses, and love-filled decorations everywhere."},
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
INDEX_ITEMS = [d for d in _INDEX if d.get("category") == "item" and d.get("key") and d.get("name")]

DISPLAY_MAP = {d["key"]: d["name"] for d in INDEX_ITEMS}

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
        with MongoClient(os.getenv("MONGO_URI")) as c:
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


def page_meta(title=None, description=None, image=None, url=None):
    return {
        "title": title or "HayDay 🍀 — Community Tools & Competitions",
        "description": description or "Join events, verify accounts, and explore community tools for Hay Day.",
        "image": image or url_for("static", filename="img/share.jpg", _external=True),
        "url": url or "https://www.hayday.info/",
    }

def _phase_today():
    # Use Danish local time for cutoff (handles DST automatically)
    now = datetime.now(ZoneInfo("Europe/Copenhagen"))
    y, m, d = now.year, now.month, now.day
    last_day = monthrange(y, m)[1]

    # Submissions: day 1–25
    # Voting: day 26–(last_day - 1)
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


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# Session & cookie hardening
app.config["RATELIMIT_STORAGE_URL"] = os.environ["REDIS_URL"]
app.config["RATELIMIT_DEFAULTS"] = ["50 per minute"]
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

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
    # remove "(...)" chunks like (COMPLETED ☑️)
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
    img = Image.open(filestorage.stream).convert("RGB")
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

    # Range strings like "Oct 01–Oct 25, 2025"
    submit_range_str = f"{d1.strftime('%b %d')}–{d_submit_end_date.strftime('%b %d, %Y')}"
    voting_range_str = f"{d_vote_start_date.strftime('%b %d')}–{d_end_date.strftime('%b %d, %Y')}"

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

    # Find the big goods table(s). They’re usually 'wikitable' or 'article-table'.
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

    # Find the big goods table(s). They’re usually 'wikitable' or 'article-table'.
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
        with MongoClient(os.getenv("MONGO_URI")) as c:
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

def normalize(text):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", "", text)
    return text.lower().strip()

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
        if re.search(rf"\b{re.escape(username_base.lower())}\s*[#\-–]\s*\d{{3,5}}\b", low):
            return True

    return False

# ---- Easter event config ----
EASTER_LIVE = False 

EASTER_EVENT = {
    "title": "Hay Day Easter Egg Hunt",
    "subtitle": "A cozy spring giveaway with surprise rewards hidden inside 4 eggs.",
    "starts_at": datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
    "ends_at": datetime(2026, 4, 12, 23, 59, 59, tzinfo=timezone.utc),
    "target_total_opens": 500,
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
        "No prize this time — but the egg was cute 🐣",
        "Nothing inside… just spring vibes 🌼",
        "Empty egg — better luck on the next one!",
        "No reward found — this one was a dud 🥚",
        "Just a shell this time… try another egg!",
        "No win — but you’re still in the hunt 🍀",
        "Nothing here — the good stuff is hiding elsewhere 👀",
        "No prize — this egg was just for fun 🎁",
        "Unlucky! This one had no reward 😅",
        "No jackpot — but the next one might have it 💎",
        "Empty egg — the rare ones are still out there!",
        "No reward — this one was a miss 🌸",
        "Just a normal egg — no prize this time",
        "No win — but the hunt continues 🐰",
        "Nothing inside — the big rewards are still hiding!",
        "No reward — try again on the next egg 🥚",
        "This egg was empty — unlucky!",
        "No prize here — keep cracking eggs 🔨",
        "Nothing found — maybe the next one 👀",
        "No win — but you’re getting closer 🍀",
    ],
}

EASTER_TESTING = {
    "enabled": False,
    "bypass_unlocks": False,
    "force_result": None,
}

# add near your easter config
EASTER_PREVIEW_EVENT_ID = "2026_easter_preview"

def _has_easter_preview_access() -> bool:
    return bool(session.get("easter_wins_authed", False)) or is_staff()

def _preview_open_state(discord_id: str | None = None):
    if not discord_id:
        return {}

    client = get_mongo_client()
    col = client["Website"]["easter_user_opens"]
    try:
        doc = col.find_one({"_id": f"{EASTER_PREVIEW_EVENT_ID}:{discord_id}"})
        return (doc or {}).get("opened", {})
    finally:
        client.close()

def _save_preview_opened_egg(discord_id: str, egg_id: int, reward: str, rarity: str):
    client = get_mongo_client()
    col = client["Website"]["easter_user_opens"]
    try:
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
    finally:
        client.close()


def _easter_user_opened_col():
    client = get_mongo_client()
    return client, client["Website"]["easter_user_opens"]

def _event_open_state(discord_id: str | None = None):
    if not discord_id:
        return {}

    client, col = _easter_user_opened_col()
    try:
        doc = col.find_one({
            "_id": f"{EASTER_EVENT_ID}:{discord_id}"
        })
        return (doc or {}).get("opened", {})
    finally:
        client.close()

def _release_pending_easter_egg(discord_id: str, egg_id: int):
    client = get_mongo_client()
    col = client["Website"]["easter_user_opens"]
    try:
        col.update_one(
            {"_id": f"{EASTER_EVENT_ID}:{discord_id}"},
            {"$unset": {f"opened.{egg_id}": ""}}
        )
    finally:
        client.close()

def _save_opened_egg(discord_id: str, egg_id: int, reward: str, rarity: str):
    client = get_mongo_client()
    col = client["Website"]["easter_user_opens"]
    try:
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
    finally:
        client.close()

EASTER_EVENT_ID = "2026_easter"

def _easter_collections():
    client = get_mongo_client()
    db = client["Website"]
    return (
        client,
        db["easter_events"],
        db["easter_contributions"],
        db["easter_wins"],
        db["event_analytics"],
        db["event_analytics_log"],
    )

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
    client, _, _, _, analytics_col, _ = _easter_collections()
    try:
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
            "traffic": {
                "by_day": {},
                "by_hour": {},
            },
            "users": {
                "unique_viewers": 0,
                "unique_openers": 0,
            },
            "performance": {
                "open_requests": 0,
                "open_response_ms_total": 0,
                "last_open_response_ms": 0,
            },
        }
        analytics_col.insert_one(doc)
        return doc
    finally:
        client.close()

def _analytics_inc(event_id: str, inc_ops: dict, extra_set: dict | None = None):
    client, _, _, _, analytics_col, _ = _easter_collections()
    try:
        _ensure_event_analytics(event_id)
        update = {
            "$inc": inc_ops,
            "$set": {"updated_at": datetime.now(timezone.utc)},
        }
        if extra_set:
            update["$set"].update(extra_set)
        analytics_col.update_one({"_id": _analytics_doc_id(event_id)}, update)
    finally:
        client.close()

def _analytics_log(action: str, event_id: str = EASTER_EVENT_ID, **data):
    client, _, _, _, _, analytics_log_col = _easter_collections()
    try:
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
    finally:
        client.close()

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
    client, _, _, _, analytics_col, _ = _easter_collections()
    try:
        return analytics_col.find_one({"_id": _analytics_doc_id(event_id)}) or {}
    finally:
        client.close()

def _recent_event_logs(event_id: str = EASTER_EVENT_ID, limit: int = 50):
    client, _, _, _, _, analytics_log_col = _easter_collections()
    try:
        return list(
            analytics_log_col.find({"event_id": event_id})
            .sort("created_at", -1)
            .limit(limit)
        )
    finally:
        client.close()

def _easter_feed_entries(limit: int = 20):
    client = get_mongo_client()
    try:
        db = client["Website"]
        feed_col = db["easter_feed"]
        usernames_col = db["usernames"]

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
                or f"User {discord_id[-4:]}" if discord_id else "Unknown"
            )

            feed.append({
                "_id": str(row.get("_id")),
                "discord_id": discord_id,
                "display_name": display_name,
                "avatar": profile.get("avatar"),
                "egg_id": row.get("egg_id"),
                "reward": row.get("reward"),
                "rarity": row.get("rarity"),
                "opened_at": row.get("opened_at"),
            })

        return feed
    finally:
        client.close()


def _insert_easter_feed_entry(discord_id: str, egg_id: int, reward: str, rarity: str):
    client = get_mongo_client()
    try:
        db = client["Website"]
        feed_col = db["easter_feed"]

        feed_col.insert_one({
            "event_id": EASTER_EVENT_ID,
            "discord_id": str(discord_id),
            "egg_id": int(egg_id),
            "reward": reward,
            "rarity": rarity,
            "opened_at": datetime.now(timezone.utc),
        })
    finally:
        client.close()

def _has_easter_wins_access() -> bool:
    if is_staff():
        return True
    return bool(session.get("easter_wins_authed", False))

def _ensure_easter_event():
    client, events_col, _, _, _, _ = _easter_collections()
    try:
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
    finally:
        client.close()

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
    """
    Move all leftover stock from earlier eggs into this egg once.
    Example:
    - opening egg 4 can absorb leftovers from egg 1, 2 and 3
    - each source egg is only rolled forward once
    """
    if target_egg_id <= 1:
        return

    client, events_col, _, _, _, _ = _easter_collections()
    try:
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

    finally:
        client.close()

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

    client, events_col, contributions_col, _, _, _ = _easter_collections()
    try:
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
    finally:
        client.close()

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

    client, events_col, _, _, _, _ = _easter_collections()
    try:
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
    finally:
        client.close()


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
    client = get_mongo_client()
    col = client["Website"]["easter_user_opens"]
    try:
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
    finally:
        client.close()

def _is_easter_testing_enabled() -> bool:
    return bool(EASTER_TESTING.get("enabled", False))

def _session_role_ids() -> set[str]:
    return {str(r) for r in (session.get("roles") or [])}

def _is_easter_member() -> bool:
    return str(MEMBER_ROLE_ID) in _session_role_ids()

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

WIKI_API = "https://hayday.fandom.com/api.php"
WIKI_USER_AGENT = "HayDay🍀/wiki-products (contact: your-email@example.com)"
WIKI_CACHE_ID = "wiki_products_v1"
WIKI_TTL = 60 * 60 * 24  # 24h


def _mongo():
    return MongoClient(os.getenv("MONGO_URI"))




# Any template that contains “Infobox” and is not a navbox/template cruft counts as an item page
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
    with _mongo() as m:
        m["Website"]["cache"].update_one(
            {"_id": WIKI_CACHE_ID},
            {"$set": {"items": items, "updated_at": int(time.time())}},
            upsert=True,
        )

def _cache_fresh(doc):
    if not doc or "updated_at" not in doc: return False
    return (time.time() - doc["updated_at"]) < WIKI_TTL



def _load_cache():
    with _mongo() as m:
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
    depth=2 => Products + important subcats (e.g., Materials, Crops) – tweak as needed
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

def log_abuse_attempt(action, details=None):
    """Log a blocked login or callback attempt to the Interaction Logs collection."""
    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["Website"]["InteractionLogs"]
        col.insert_one({
            "action": action,
            "details": details or {},
            "username": session.get("username"),
            "discord_id": session.get("discord_id"),
            "timestamp": datetime.utcnow(),
            "user_agent": request.headers.get("User-Agent", "Unknown"),
            "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        })

def get_settings_collection(client=None):
    if client:
        return client["Website"]["settings"]
    with MongoClient(os.getenv("MONGO_URI")) as client2:
        return client2["Website"]["settings"]

def read_maintenance_banner():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["Website"]["settings"]
        doc = col.find_one({"_id": "maintenance_banner"})
        if not doc:
            return {"enabled": False, "message": "", "require_ack": False, "version": 1}
        # Normalize expected fields
        return {
            "enabled": bool(doc.get("enabled", False)),
            "message": doc.get("message", ""),
            "require_ack": bool(doc.get("require_ack", True)),
            "version": int(doc.get("version", 1)),
        }

@app.context_processor
def inject_maintenance_banner():
    # Inject into all templates
    try:
        banner = read_maintenance_banner()
    except Exception:
        banner = {"enabled": False, "message": "", "require_ack": False, "version": 1}
    return {"maintenance_banner": banner}

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
    with MongoClient(os.getenv("MONGO_URI")) as client:
        for doc in client["Security"]["banned_ips"].find():
            banned.append(f"{escape(doc['_id'])} (internal: {escape(doc.get('internal_ip', 'N/A'))}, reason: {escape(doc.get('reason', 'n/a'))}, hits: {doc.get('hit_count', '?')})")

    return f"""
        <h1>🛡️ IP Scanner Watch</h1>
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
    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["Website"]["settings"]

        # If complex object (dict) is passed for maintenance banner, store as-is
        if key == "maintenance_banner":
            if not isinstance(value, dict):
                return jsonify({"error": "maintenance_banner value must be an object"}), 400
            value["_id"] = "maintenance_banner"
            col.update_one({"_id": "maintenance_banner"}, {"$set": value}, upsert=True)
            return jsonify({"message": "Maintenance banner updated"}), 200

        # Fallback for your other scalar settings (e.g., prefix)
        col.update_one({"_id": key}, {"$set": {"_id": key, "value": value}}, upsert=True)
        return jsonify({"message": f"{key} updated"}), 200


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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
            scam_records = list(client["Scam"]["Banned"].find({}))
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
                print(f"⚠️ Ban check failed: {e}")

            usernames = client["Website"]["usernames"].find_one({"_id": user_id})

            # Find active mute if exists
            active_mute = next(
                (m for m in mute_info if m.get("muted") and m.get("mute_end") and m["mute_end"] > datetime.utcnow()),
                None
            )

            # Fetch logs and name changes
            logs = list(client["Website"]["Logs"].find({
                "$or": [{"author.id": user_id}, {"user_id": user_id}]
            }))
            name_changes = list(client["log"]["namechange"].find({"user_id": user_id}))

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

        with MongoClient(os.getenv("MONGO_URI")) as client:
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
                        headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
                    )
                except Exception as e:
                    print(f"⚠️ Failed to trigger unmute webhook: {e}")

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
                    headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
                )
            except Exception as e:
                print(f"⚠️ Failed to trigger bot mute webhook: {e}")

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
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
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
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
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

        with MongoClient(os.getenv("MONGO_URI")) as client:
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

        # 🔁 Trigger bot webhook
        try:
            requests.post(
                os.getenv("BOT_WEBHOOK_URL") + "/webhook/moderation/ban",
                json={
                    "user_id": user_id,
                    "reason": reason,
                    "staff_id": staff_id,
                    "action": action
                },
                headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
            )
        except Exception as e:
            print(f"⚠️ Failed to trigger bot ban webhook: {e}")

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500




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


@app.route("/booster-dashboard", methods=["GET", "POST"])
def booster_dashboard():
    if not is_staff():
        return "❌ Access denied. You are not staff.", 403

    discord_id = int(session["discord_id"])
    message = None

    with MongoClient(os.getenv("MONGO_URI")) as client:
        booster_col = client["hayday"]["Booster"]
        user_col = client["Website"]["usernames"]
        roles_cache = client["Website"]["roles_cache"].find_one({"_id": "live"}) or {}

        # Handle form submission
        if request.method == "POST":
            target_id = int(request.form.get("target_id"))
            role_name = request.form.get("role_name")
            role_color = request.form.get("role_color")

            if not role_name or not role_color:
                message = "❌ Both fields are required."
            else:
                try:
                    r = requests.post(
                        os.getenv("BOT_WEBHOOK_URL") + "/webhook/booster-update",
                        json={
                            "discord_id": target_id,
                            "role_name": role_name,
                            "role_color": role_color
                        },
                        headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
                    )
                    message = "✅ Role updated!" if r.status_code == 200 else "❌ Failed to update role"
                except Exception as e:
                    message = f"❌ Error: {e}"

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
                "role_name": b.get("role_name", "❓ Unknown"),
                "color": f"#{int(b.get('role_color', 0)):06x}"
            })

    return render_template("booster_dashboard.html", boosters=boosters, message=message)

@app.route("/force-logout", methods=["POST"])
def force_logout_all():
    if session.get("discord_id") != "154282062973501441":
        return "❌ Unauthorized", 403

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
    

@app.route("/api/button-toggles", methods=["GET", "POST"])
def button_toggles():
    if not is_staff():
        return "Unauthorized", 403

    if "discord_id" not in session:
        return redirect("/login-page")

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
    with MongoClient(os.getenv("MONGO_URI")) as client:
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

            # host info…
            host_id = str(g.get("host_id"))
            host = user_map.get(host_id)
            g["host_display"] = host.get("display_name", f"<@{host_id}>") if host else f"<@{host_id}>"
            g["host_avatar"] = (
                f"https://cdn.discordapp.com/avatars/{host_id}/{host.get('avatar_hash')}.png"
                if host and host.get("avatar_hash") else None
            )

            # participants info…
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["Giveaway"]["current_giveaways"]

        query = {
            "ended": True,
            "winners": {"$in": [discord_id]}
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
    COPENHAGEN_TZ = pytz_timezone("Europe/Copenhagen")
    now_ts = time.time()

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Giveaway"]
        user_db = client["Website"]["usernames"]
        raw_giveaways = list(db["current_giveaways"].find({"ended": False}))

        user_ids = set()
        for g in raw_giveaways:
            user_ids.update(g.get("participants", {}).keys())
            if "host_id" in g:
                user_ids.add(str(g["host_id"]))

        users = user_db.find({"_id": {"$in": list(user_ids)}})
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

            host_id = str(g.get("host_id"))
            host = user_map.get(host_id)

            output.append({
                "prize": g.get("prize"),
                "end_time_ts": int(end_ts),
                "host_display": host.get("username") if host else f"User {host_id}",
                "host_avatar": f"https://cdn.discordapp.com/avatars/{host_id}/{host.get('avatar_hash')}.png"
                    if host and host.get("avatar_hash") else None
            })

        return jsonify(output)


@app.route("/api/production-data")
def api_production_data():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["hayday"]["ProductionGuide"]
        data = list(col.find({}, {"_id": 0}))  # Exclude _id for frontend use
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with get_mongo_client() as client:
        wins_col = client["Website"]["easter_wins"]
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

@csrf.exempt
@app.get("/api/easter-feed")
def api_easter_feed():
    return jsonify(
        ok=True,
        feed=_json_safe(_easter_feed_entries(limit=20))
    )

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

        client, events_col, _, wins_col, _, _ = _easter_collections()
        try:
            events_col.update_one(
                {"_id": EASTER_EVENT_ID},
                {
                    "$inc": {
                        "stats.total_opens": 1,
                        f"stats.eggs.{egg_id}.total_opens": 1
                    }
                }
            )
        finally:
            client.close()

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

                client, events_col, _, wins_col, _, _ = _easter_collections()
                try:
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
                finally:
                    client.close()
            else:
                rarity = "bonus"
                reward = random.choice(EASTER_EVENT["soft_loss_rewards"])
        else:
            rarity = "bonus"
            reward = random.choice(EASTER_EVENT["soft_loss_rewards"])

        if rarity == "bonus":
            client, events_col, _, _, _, _ = _easter_collections()
            try:
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
            finally:
                client.close()

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

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Website"]
        entries = list(db["CompEntries"].find({"comp_id": comp_id}).sort("created_at", -1))
        vote_counts = _vote_counts_for(comp_id, client)  # ← reuse

        # Optional: label “who submitted” via your usernames cache
        ids = [str(e.get("user_id")) for e in entries if e.get("user_id")]
        users = list(db["usernames"].find({"_id": {"$in": ids}}))
        user_map = {u["_id"]: u for u in users}

    return render_template("admin_competition.html",
                           comp_id=comp_id, phase=phase,
                           entries=entries, vote_counts=vote_counts,
                           user_map=user_map)

@csrf.exempt
@app.post("/admin/competition/caption/<entry_id>")
def admin_competition_caption(entry_id):
    if not is_staff(): 
        return "Unauthorized", 403
    new_caption = (request.form.get("caption") or "").strip()[:35]
    with MongoClient(os.getenv("MONGO_URI")) as c:
        c["Website"]["CompEntries"].update_one(
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
    with MongoClient(os.getenv("MONGO_URI")) as c:
        db = c["Website"]
        db["CompEntries"].delete_one({"_id": ObjectId(entry_id)})
        db["CompVotes"].delete_many({"entry_id": entry_id})
    flash("Entry deleted (votes removed).", "success")
    return redirect(url_for("admin_competition", comp_id=request.args.get("comp_id")))

@app.route("/api/live-auctions")
def live_auctions():
    with MongoClient(os.getenv("MONGO_URI")) as client:
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
    print("HIT: /api/bid")   # in api_bid
    print("API BID endpoint called!")
    print("Request content-type:", request.content_type)
    print("Request data:", request.data)
    print("Request form:", request.form)
    print("Request args:", request.args)

    user_id = session.get("discord_id")
    if not user_id:
        return jsonify({"success": False, "message": "Not logged in via Discord"}), 401
    user_roles = session.get("roles", [])

    if not user_roles or str(UNVERIFIED_ROLE_ID) in user_roles:
        return jsonify({
            "success": False,
            "message": "❌ You must be a verified member of the Discord to bid. Join here: https://discord.gg/hayday"
        }), 403

    if str(MEMBER_ROLE_ID) not in user_roles:
        return jsonify({
            "success": False,
            "message": "❌ You must be a member of the Discord server to place bids. Join here: https://discord.gg/hayday"
        }), 403

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

        if str(auction["owner_id"]) == str(user_id):
            print("User tried to bid on their own auction!")
            return jsonify({"success": False, "message": "❌ You cannot bid on your own auction."}), 403

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
            # Someone else updated the bid first → tell the user to re-try with the latest number
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

    # Updated CSP — currently allowing unsafe-inline until nonce migration is ready
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
    ignore_exact = ("/robots.txt", "/favicon.ico", "/callback")  # add more if you like
    file_exts = (".js",".css",".png",".jpg",".jpeg",".gif",".webp",
                 ".svg",".ico",".json",".xml",".map",".txt",".csv")

    path = request.path

    if (request.endpoint == "static"
        or any(path.startswith(p) for p in ignore_prefixes)
        or path in ignore_exact
        or any(path.endswith(ext) for ext in file_exts)):
        return  # don’t count

    with MongoClient(os.getenv("MONGO_URI")) as client:
        client["Website"]["PageViews"].update_one({"_id": path}, {"$inc": {"count": 1}}, upsert=True)



@app.before_request
def ensure_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

@app.before_request
def set_session_lifetime():
    session.permanent = True
    user_roles = session.get("roles", [])

    if any(role in STAFF_ROLES for role in user_roles):
        # Staff — shorter lifetime
        app.permanent_session_lifetime = timedelta(days=7)
    else:
        # Normal users — longer lifetime
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

    # Load banned IPs from MongoDB once
    if not banned_ips_loaded:
        with MongoClient(os.getenv("MONGO_URI")) as client:
            banned = client["Security"]["banned_ips"].find()
            BANNED_IPS = set(doc["_id"] for doc in banned)
        banned_ips_loaded = True

    # Auto-block if IP is banned
    if real_ip in BANNED_IPS:
        with MongoClient(os.getenv("MONGO_URI")) as client:
            doc = client["Security"]["banned_ips"].find_one({"_id": real_ip})
            if doc:
                banned_at = doc.get("banned_at")
                if banned_at and (datetime.utcnow() - banned_at).total_seconds() >= BAN_TIME:
                    # Expired — unban them
                    client["Security"]["banned_ips"].delete_one({"_id": real_ip})
                    BANNED_IPS.discard(real_ip)
                    app.logger.info(f"[UNBANNED] IP {real_ip} was automatically unbanned after expiry")
                else:
                    # 🔄 Extend the ban if they hit again
                    client["Security"]["banned_ips"].update_one(
                        {"_id": real_ip},
                        {"$set": {"banned_at": datetime.utcnow()}},
                        upsert=True
                    )
                    app.logger.warning(f"[AUTO-EXTENDED BAN] {real_ip} tried {path} again — ban extended (internal: {internal_ip})")
                    abort(403)

    # Check for scanner-like behavior
    matched = next((pattern for pattern in SCANNER_PATHS if pattern in path), None)
    if matched:
        ip_hits[real_ip].append(now)
        ip_hits[real_ip] = [t for t in ip_hits[real_ip] if now - t < BAN_TIME]

        if len(ip_hits[real_ip]) >= SCAN_THRESHOLD:
            BANNED_IPS.add(real_ip)
            with MongoClient(os.getenv("MONGO_URI")) as client:
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
        <h1>🔍 IP Debug</h1>
        <p><strong>Real IP:</strong> {real_ip}</p>
        <p><strong>Internal IP:</strong> {internal_ip}</p>
    """

@app.route("/submit_bid", methods=["POST"])
def submit_bid():
    return jsonify({"error": "Deprecated. Use /api/bid"}), 410

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
    mongo_uri = os.getenv("MONGO_URI")
    with MongoClient(mongo_uri) as client:
        collection = client["hayday"]["NewsFeed"]
        items = list(collection.find({"timestamp": {"$exists": True}}).sort("timestamp", -1).limit(5))

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

@app.route("/scam-ids")
def scam_ids():
    if not is_staff():
        return "Unauthorized", 403
    
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
    meta = page_meta()
    year = datetime.now(timezone.utc).year
    return render_template("index.html", year=year, meta=meta)

@app.route("/login-page")
def login_page():
    next_path = request.args.get("next", "/")
    return redirect(url_for("login", next=next_path))

@app.route("/login")
@limiter.limit("5 per minute",key_func=get_remote_address,error_message="Too many login attempts. Please wait a minute.")
def login():
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    next_page = request.args.get("next", "/")
    session["next_page"] = next_page

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

    with MongoClient(os.getenv("MONGO_URI")) as client:
        logs = list(client["Website"]["Logs"].find(query).sort("timestamp", -1))

    # Build CSV
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Type", "Author", "Channel", "Timestamp", "Content", "Images"])

    for log in logs:
        images = ", ".join(log.get("images", [])) if "images" in log else ""
        if log["type"] == "message_edit":
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

    output = si.getvalue()
    si.close()

    filename = f"discord_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename={filename}"})


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
    per_page = 6  # 👈 adjust to how many logs per page you want

    query = {"timestamp": {"$exists": True}}

    if search_term:
        query["$or"] = [
            {"author.name": {"$regex": search_term, "$options": "i"}},
            {"author.id": search_term}
        ]

    if selected_channel:
        query["channel_name"] = selected_channel

    # ✅ Preset date filter logic
    if preset == "24h":
        query["timestamp"]["$gte"] = now - timedelta(hours=24)
    elif preset == "7d":
        query["timestamp"]["$gte"] = now - timedelta(days=7)
    elif preset == "this_week":
        start_of_week = now - timedelta(days=now.weekday())
        query["timestamp"]["$gte"] = datetime(start_of_week.year, start_of_week.month, start_of_week.day, tzinfo=timezone.utc)

    with MongoClient(os.getenv("MONGO_URI")) as client:
        logs_collection = client["Website"]["Logs"]
        all_logs = list(logs_collection.find(query).sort("timestamp", -1))

        deleted_logs = [log for log in all_logs if log.get("type") == "message_delete"]
        edited_logs = [log for log in all_logs if log.get("type") == "message_edit"]

        deleted_total = len(deleted_logs)
        edited_total = len(edited_logs)
        deleted_logs = deleted_logs[(deleted_page-1)*per_page : deleted_page*per_page]
        edited_logs = edited_logs[(edited_page-1)*per_page : edited_page*per_page]

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


@app.route("/api/debug/session")
def debug_session():
    return jsonify({
        "has_roles": "roles" in session,
        "roles": session.get("roles"),
        "discord_id": session.get("discord_id")
    })



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
    highest_role = sorted_roles[0] if sorted_roles else None

    with MongoClient(os.getenv("MONGO_URI")) as client:
        level_col = client["hayday"]["level"]
        level_doc = level_col.find_one({"_id": discord_id})
        all_users = list(level_col.find().sort("xp", -1))

        users_collection = client["Website"]["users"]
        usernames_collection = client["Website"]["usernames"]

        user = users_collection.find_one({"_id": discord_id}) or {}
        fallback = usernames_collection.find_one({"_id": discord_id}) or {}

        display_name = fallback.get("display_name", "Unknown")

        # ✅ Always fetch avatar from synced collection
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
    lb_type = request.args.get("type", "level")
    def _viewer_page_from_rank(rank: int, per_page: int) -> int:
        if not rank or rank < 1:
            return 1
        return ((rank - 1) // per_page) + 1
    
    with MongoClient(os.getenv("MONGO_URI")) as client:
        username_col = client["Website"]["usernames"]
        username_col2 = client["Website"]["users"]
        viewer_id = session.get("discord_id")
        viewer_profile = username_col2.find_one({"_id": str(viewer_id)}) if viewer_id else None

        is_staff = False
        if viewer_profile:
            user_roles = viewer_profile.get("roles", [])
            is_staff = any((role) in STAFF_ROLE_IDS for role in user_roles)

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
                {"$group": {"_id": "$winners"}},
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

            # 🔧 Make sure all user IDs are strings
            for user in users:
                user["_id"] = str(user["id"])

            user_ids = [user["_id"] for user in users]

        elif lb_type == "coins":
            col = client["Economy"]["Users"]
            total_users = col.count_documents({"coins": {"$gt": 0}})
            users = list(col.find({"coins": {"$gt": 0}}).sort("coins", -1).skip(skip).limit(limit))
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
        #state = request.args.get("state")
        #if not state or state != session.get("oauth_state"):
        #    log_abuse_attempt("OAuth Invalid State", {
        #        "state": state,
        #        "expected_state": session.get("oauth_state"),
        #        "ip": request.headers.get("X-Forwarded-For", request.remote_addr)
        #    })
        #    return "❌ Invalid OAuth state parameter", 400
        #session.pop("oauth_state", None)

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

        member = requests.get(
            f"https://discord.com/api/users/@me/guilds/{GUILD_ID}/member",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        guild_data = requests.get(
            f"https://discord.com/api/guilds/{GUILD_ID}",
            headers={"Authorization": f"Bot {BOT_TOKEN}"}
        ).json()
        session.permanent = True
        session["guild_name"] = guild_data.get("name", "HayDay 🍀")
        member_data = {}
        if member.status_code == 200:
            member_data = member.json()
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
            staff_collection = client["Website"]["Staff"]
            staff_doc = staff_collection.find_one({"_id": user["id"]})
            if staff_doc:
                session["staff_role"] = staff_doc.get("role", None)  # Use .get safely
            else:
                session["staff_role"] = None


        next_page = session.pop("next_page", url_for("profile"))
        print("User object:", user)  # <- add this too

        return redirect(next_page)
    except Exception as e:
        traceback.print_exc()
        return f"<h1>❌ Error:</h1><pre>{e}</pre>", 500

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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    db = MongoClient(os.getenv("MONGO_URI"))["Website"]
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

        existing_user = users_col.find_one({"_id": user["_id"]})
        user["public_profile"] = user.get("public_profile", True)
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

    with MongoClient(os.getenv("MONGO_URI")) as c:
        col = c["Website"]["trading_item_overrides"]

        doc = col.find_one({"_id": item_key})
        if not doc:
            return jsonify(ok=False, error="Not found"), 404

        # ✅ Only allow deleting manual overrides
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

    with MongoClient(os.getenv("MONGO_URI")) as c:
        col = c["Website"]["trading_item_overrides"]
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
        "ts": {"$gte": since},
        "category": {"$in": ["item", "set"]}, 
    }

    if post_type in {"buy", "sell"}:
        match["post_type"] = post_type
    else:
        match["post_type"] = {"$in": ["buy", "sell"]}


    with MongoClient(os.getenv("MONGO_URI")) as c:
        db = c["hayday"]
        ticks = db["auctions.Trading.ticks"]
        mp_ticks = db["auctions.Trading.mp_ticks"]
        display_map, alias_to_key, key_to_filename, key_to_source_url, key_to_image_url = _trading_maps_with_overrides()


        pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {"k": "$item_key", "t": "$post_type"},
            "sum_qty": {"$sum": {"$ifNull": ["$qty", 0]}},
            "sum_value": {"$sum": {"$ifNull": ["$total_value", 0]}},
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

            # ✅ NEW
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
            {"$sort": {"ts": 1}},
            {"$group": {
                "_id": {"k": "$item_key", "t": "$post_type"},
                "first_price": {"$first": "$unit_price"},
                "last_price": {"$last": "$unit_price"},
            }},
        ]
        trend_rows = list(ticks.aggregate(trend_pipe))

        # --- XMP range (mp_mult) per item_key (from mp_ticks collection) ---
        mp_match = {
            "guild_id": TRADING_GUILD_ID,
            "mp_mult": {"$ne": None},
        }
        # only apply ts filter if you know mp_ticks has ts
        mp_match["ts"] = {"$gte": since}


        mp_pipe = [
            {"$match": mp_match},
            {"$group": {
                "_id": "$item_key",
                "min_mp": {"$min": "$mp_mult"},
                "max_mp": {"$max": "$mp_mult"},
                "mp_posts": {"$sum": 1},
            }},
        ]
        mp_rows = list(mp_ticks.aggregate(mp_pipe))

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

    with MongoClient(os.getenv("MONGO_URI")) as c:
        ticks = c["hayday"]["auctions.Trading.ticks"]
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
        "category": {"$in": ["item", "set"]},
        "item_key": canonical,
        "post_type": {"$in": ["buy", "sell"]} if post_type == "both" else post_type,
        "ts": {"$gte": start, "$lt": end},
    }

    # Return posts for scrolling + jump link
    with MongoClient(os.getenv("MONGO_URI")) as c:
        ticks = c["hayday"]["auctions.Trading.ticks"]
        cursor = ticks.find(match).sort("ts", -1).limit(limit)

        posts = []
        for d in cursor:
            posts.append({
                "id": str(d.get("_id")),
                "post_type": d.get("post_type"),
                "ts": d.get("ts").isoformat() if d.get("ts") else None,
                "jump_url": d.get("jump_url"),
                "author_id": str(d.get("author_id")) if d.get("author_id") is not None else None,
                "channel_id": str(d.get("channel_id")) if d.get("channel_id") is not None else None,
                "message_id": str(d.get("message_id")) if d.get("message_id") is not None else None,
                "qty": d.get("qty"),
                "unit_price": d.get("unit_price"),
                "total_value": d.get("total_value"),
                "raw_text": d.get("raw_text") or d.get("content") or d.get("text"),
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
        "category": {"$in": ["item", "set"]},
        "item_key": canonical,
        "post_type": {"$in": ["buy", "sell"]},
        "unit_price": {"$ne": None},
    }

    # Apply range filter (server-side) so the popup range dropdown works
    now = datetime.now(timezone.utc)
    if range_raw != "all":
        try:
            days = int(range_raw)
            match["ts"] = {"$gte": now - timedelta(days=days)}
        except ValueError:
            # fallback
            match["ts"] = {"$gte": now - timedelta(days=30)}

    unit = "hour" if bucket == "hour" else "day"

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {
                "d": {"$dateTrunc": {"date": "$ts", "unit": unit}},
                "t": "$post_type",
            },
            "avg_price": {"$avg": "$unit_price"},
            "posts": {"$sum": 1},
            "qty": {"$sum": {"$ifNull": ["$qty", 0]}},
        }},
        {"$sort": {"_id.d": 1}},
    ]

    with MongoClient(os.getenv("MONGO_URI")) as c:
        db = c["hayday"]
        ticks = db["auctions.Trading.ticks"]
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
        user["display_name"] = display_name  # ✅ always use latest name from usernames collection
        user["avatar"] = avatar_url          # ✅ always use latest avatar from usernames collection

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

            all_users = list(level_col.find().sort("xp", -1))
            rank = next((i + 1 for i, u in enumerate(all_users) if u["_id"] == discord_id), "?")

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
        is_owner=is_owner
    )



@app.route("/builder")
def builder():
    return render_template("builder.html")


_TIER_RE = re.compile(r"^(?P<prefix>.+)_t(?P<tier>\d+)$")

def _sorted_shop_items(shop_items: dict):
    """
    Sort rules:
    1) Most expensive 'group' first (group = prefix before _tX)
    2) Inside a group, Tier III, II, I next to each other (highest tier first)
    3) Fallback sorting by price desc
    """
    rows = []
    for key, item in shop_items.items():
        key_l = (key or "").lower()

        m = _TIER_RE.match(key_l)
        group = m.group("prefix") if m else key_l
        tier = int(m.group("tier")) if m else 0
        price = int(item.get("price", 0) or 0)

        rows.append((key, item, group, tier, price))

    # group max price (so grouped tier sets sort by their strongest tier)
    group_max = {}
    for _, _, group, _, price in rows:
        group_max[group] = max(group_max.get(group, 0), price)

    # Sort: group expensive first, then tier high->low, then price high->low
    rows.sort(key=lambda r: (-group_max[r[2]], -r[3], -r[4], r[0]))

    # Return list of (key, item) tuples for Jinja: {% for key, item in items %}
    return [(k, it) for (k, it, _, _, _) in rows]


@app.route("/shop")
def shop():
    if "discord_id" not in session:
        return redirect("/login")

    user_id = int(session["discord_id"])
    coins = 0
    owned_items = set()

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
        flash("⚠️ You need to log in to make a purchase.", "error")
        return redirect(url_for("login"))

    item_id = (request.form.get("item_id") or "").strip().lower()
    if not item_id or item_id not in SHOP_ITEMS:
        flash("❌ Unknown item.", "error")
        return redirect(url_for("shop"))

    user_id = int(session["discord_id"])

    bot_base = os.getenv("BOT_BASE_URL")
    bot_key = os.getenv("BOT_WEBHOOK_KEY")

    print("[SHOP] buy_item user_id=", user_id, "item_id=", item_id)
    print("[SHOP] BOT_BASE_URL=", bot_base, "BOT_WEBHOOK_KEY set?", bool(bot_key))

    if not bot_base or not bot_key:
        flash("❌ Missing BOT_BASE_URL / BOT_WEBHOOK_KEY on website.", "error")
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
        flash(f"❌ Purchase failed: {data.get('error', 'Unknown error')}", "error")
        return redirect(url_for("shop"))

    flash(f"✅ Purchase complete: {SHOP_ITEMS[item_id]['name']}", "success")
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

            # ✅ Add these two lines:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

        # ✅ Top pages tracking
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["hayday"]["starboard"]
        result = col.delete_one({"starboard_message_id": message_id})

    if result.deleted_count > 0:
        return jsonify({"message": "✅ Starboard message deleted."})
    else:
        return jsonify({"message": "❌ Message not found."})
    

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

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["hayday"]
        user_col = client["Website"]["usernames"]
        log_col = client["Website"]["Logs"]

        active_auctions_all = list(db["auctions"].find({"status": "active"}))
        active_auctions_json = fix_ids(active_auctions_all)
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
        banned_users = list(
            user_col.find({"roles": AUCTION_BANNED_ROLE_ID})
            .skip(skip_bans).limit(limit)
        )

        # Count total documents
        active_total = db["auctions"].count_documents({"status": "active"})
        ended_total = db["auctions"].count_documents({"status": {"$in": ["ended", "no_bids"]}})
        log_total = log_col.count_documents({"type": {"$regex": "^auction_"}})
        ban_total = user_col.count_documents({"roles": AUCTION_BANNED_ROLE_ID})

        active_total_pages = max((active_total + limit - 1) // limit, 1)
        ended_total_pages = max((ended_total + limit - 1) // limit, 1)
        log_total_pages = max((log_total + limit - 1) // limit, 1)
        ban_total_pages = max((ban_total + limit - 1) // limit, 1)

        # 🧠 Collect all user IDs
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


@app.route("/api/auction/cancel", methods=["POST"])
def cancel_auction():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    message_id = request.form.get("message_id")
    reason = request.form.get("reason") or "No reason provided."

    if not message_id:
        return "Missing message_id", 400

    # Update auction status to 'cancelled'
    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["hayday"]["auctions"]
        auction = col.find_one({"message_id": int(message_id)})
        if not auction:
            return "Auction not found", 404

        col.update_one({"_id": auction["_id"]}, {"$set": {"status": "cancelled"}})

    # Notify bot to delete the Discord message and log
    requests.post(
        os.getenv("BOT_WEBHOOK_URL") + "/webhook/cancel-auction",
        json={
            "message_id": message_id,
            "reason": reason,
        },
        headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
    )

    return redirect("/auction-dashboard")



@app.route("/api/auction/<message_id>/bids")
def get_auction_bids(message_id):
    if not is_staff():
        return "Unauthorized", 403

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
                "user_id": str(bid["user_id"]),  # ← change from int() to str()
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

        with MongoClient(os.getenv("MONGO_URI")) as client:
            col = client["hayday"]["auctions"]
            existing = col.find_one({"message_id": message_id})
            if not existing:
                return "Auction not found", 404

            update_fields = {}
            for k, v in data.items():
                if k == "message_id":
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

        # Notify bot
        requests.post(
            os.getenv("BOT_WEBHOOK_URL") + "/webhook/refresh-auction",
            json={"message_id": message_id},
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
        )
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

    with MongoClient("MONGO_URI") as client:
        col = client["Auction"]["auctions"]
        result = col.update_one(
            {"message_id": int(message_id)},
            {"$unset": {"buyout_offer": ""}}
        )
        print(f"[BUYOUT REMOVE] message_id={message_id} matched={result.matched_count} modified={result.modified_count}")

    # Optionally trigger embed update via webhook
    try:
        requests.post(
            f"{os.getenv('WEBHOOK_BASE_URL')}/webhook/refresh-auction",
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
            json={"message_id": message_id}
        )
    except Exception as e:
        print(f"[WARN] Failed to refresh embed: {e}")

    return redirect("/auction-dashboard")


@app.route("/api/auction/remove-image", methods=["POST"])
def remove_auction_image():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403
        
    message_id = request.form.get("message_id")

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["hayday"]["auctions"]
        result = db.update_one(
            {"message_id": int(message_id)},
            {"$unset": {"image_url": ""}}
        )
        print(f"[REMOVE-IMAGE] Result: matched={result.matched_count} modified={result.modified_count}")

    # Optional: refresh bot embed
    try:
        requests.post(
            f"{os.getenv('BOT_WEBHOOK_URL')}/webhook/refresh-auction",
            headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")},
            json={"message_id": message_id}
        )
    except Exception as e:
        print("Failed to refresh embed:", e)

    return redirect("/auction-dashboard")



@app.route("/api/auction/end", methods=["POST"])
def end_auction_now():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    message_id = request.form.get("message_id")
    if not message_id:
        return "Missing message_id", 400

    with MongoClient(os.getenv("MONGO_URI")) as client:
        col = client["hayday"]["auctions"]
        auction = col.find_one({"message_id": int(message_id)})
        if not auction:
            return "Auction not found", 404

        # Force end by making it expired
        col.update_one({"_id": auction["_id"]}, {
            "$set": {"end_time": datetime.utcnow() - timedelta(seconds=1)}
        })

    # Trigger full auction end logic via bot webhook
    requests.post(
        os.getenv("BOT_WEBHOOK_URL") + "/webhook/end-auction",
        json={"message_id": message_id},
        headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
    )

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

    with MongoClient(os.getenv("MONGO_URI")) as client:
        auctions = client["hayday"]["auctions"]
        auction = auctions.find_one({"message_id": int(message_id)})

        if not auction:
            print("[REMOVE BID] ❌ Auction not found.")
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
            print("[REMOVE BID] ⚠ No bid found for this user_id — nothing removed")

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

    # Trigger refresh
    refresh_resp = requests.post(
        os.getenv("BOT_WEBHOOK_URL") + "/webhook/refresh-auction",
        json={"message_id": message_id},
        headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
    )

    print(f"[REMOVE BID] Webhook refresh response: {refresh_resp.status_code}")
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
        if item_id in ["mute_other_20m", "ping_storm", "ghost_ping", "lore_post"]:
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
    year = datetime.now().year
    return render_template("privacy.html", year=year)



@app.route("/staff")
def staff_panel():
    with MongoClient(os.getenv("MONGO_URI")) as client:
        staff = list(client["Website"]["Staff"].find())
    year = datetime.now(timezone.utc).year
    return render_template("staff.html", staff=staff, year=year)

@app.route("/dashboard")
def dashboard():
    if "discord_id" not in session or not is_staff():
        return "Unauthorized", 403

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
        return jsonify([])
    guild_id = "959220051427340379"  # your server ID
    try:
        role_mapping = fetch_role_mapping(guild_id)
    except Exception as e:
        print(f"[API Giveaways] Failed to fetch role mapping: {e}")
        role_mapping = {}


    now_ts = time.time()

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Giveaway"]
        giveaways = []

        for g in db["current_giveaways"].find({"ended": False}):
            end = g.get("end_time")
            if not end:
                continue
            if end.timestamp() < now_ts:
                continue

            delta = int(end.timestamp() - now_ts)
            minutes = (delta % 3600) // 60
            ends_in = f"{delta // 3600}h {minutes}m"

            giveaways.append({
                "prize": g.get("prize", "N/A"),
                "winners": g.get("winners_count", 1),
                "message_id": str(g.get("message_id")),
                "entry_count": sum(g.get("participants", {}).values()),
                "participant_count": len(g.get("participants", {})),
                "ends_in": ends_in,
                "host_id": g.get("host_id"),
                "required_role_id": g.get("required_role_id"),
                "required_role_name": role_mapping.get(str(g.get("required_role_id")), {}).get("name") if g.get("required_role_id") else None,
                "color": g.get("color")
            })

        # ✅ This part must be OUTSIDE the loop
        recently_ended = list(
            db["current_giveaways"]
            .find({"ended": True})
            .sort("end_time", -1)
            .limit(10)
        )

        ended_giveaways = []
        for g in recently_ended:
            ended_giveaways.append({
                "prize": g.get("prize", "N/A"),
                "winners": g.get("winners_count", 1),
                "message_id": str(g.get("message_id")),
                "ended_at": g.get("end_time").strftime("%Y-%m-%d %H:%M")
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
        with MongoClient(os.getenv("MONGO_URI")) as client:
            db = client["Giveaway"]
            g = db["current_giveaways"].find_one({"message_id": int(message_id)})
            if not g or "winners" not in g or not g["winners"]:
                return jsonify([])

            user_ids = g["winners"]

            # ✅ Use the usernames collection (not hayday.level)
            user_db = client["Website"]["usernames"]
            found_users = list(user_db.find({"_id": {"$in": [str(uid) for uid in user_ids]}}))
            user_map = {str(u["_id"]): u for u in found_users}

            # ✅ Build result with avatar + display name fallback
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
        with MongoClient(os.getenv("MONGO_URI")) as client:
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
                return jsonify({"error": "You don’t have the required role"}), 403
            flash("❌ You don’t have the required role to enter this giveaway.")
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
                headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
            return jsonify({"error": "You’re not in this giveaway."}), 400

        del participants[discord_id]
        col.update_one({"message_id": mid}, {"$set": {"participants": participants}})

        try:
            requests.post(
                os.getenv("BOT_WEBHOOK_URL") + "/webhook/refresh-giveaway",
                json={"message_id": mid},
                headers={"Authorization": os.getenv("BOT_WEBHOOK_KEY")}
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
        title="Monthly Farm Design Competition — HayDay 🍀",
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
    with MongoClient(os.getenv("MONGO_URI")) as client:
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
        "first":  "1,000,000 coins + 1 month of Discord Nitro",
        "second": "700,000 coins",
        "third":  "500,000 coins",
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
    PER_PAGE = 16

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Website"]
        entries_col = db["CompEntries"]
        votes_col = db["CompVotes"]

        q_entries = {"comp_id": comp_id}
        total = entries_col.count_documents(q_entries)

        # --- build vote counts (all keys as strings) ---
        pipeline = [
            {"$match": {"comp_id": comp_id}},
            {"$group": {"_id": "$entry_id", "count": {"$sum": 1}}},
        ]
        counts = {}
        for doc in votes_col.aggregate(pipeline):
            counts[str(doc["_id"])] = doc["count"]

        # ensure zeros
        for _e in entries_col.find(q_entries, {"_id": 1}):
            k = str(_e["_id"])
            if k not in counts:
                counts[k] = 0

        # --- fetch entries per your sort ---
        if phase == "voting" and sort_mode == "top":
            # existing TOP logic (unchanged)
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
        theme=theme,  
        **cal,
    )



@csrf.exempt
@app.route("/competition/submit", methods=["GET", "POST"])
def competition_submit():
    phase, comp_id = _phase_today()

    client = get_mongo_client()
    db = client["Website"]
    entries_col = db["CompEntries"]
    votes_col   = db["CompVotes"]  # <-- for "Your vote" tile

    # --- Work out submit_status for the UI ---
    discord_id = session.get("discord_id")
    roles = [str(r) for r in (session.get("roles") or [])]

    if not discord_id:
        submit_status = "not_logged_in"
    elif str(MEMBER_ROLE_ID) not in roles:
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
            my_vote=my_vote,          # <-- enables "Your vote" section
            entries_map=entries_map,  # <-- image lookup for your vote
            GUILD_ID=GUILD_ID,        # used by template links
            theme=theme,  
        )

    # --- POST (only if allowed) ---
    if submit_status != "ok":
        flash("Please log in and verify in Discord to submit.", "error")
        return redirect(url_for("competition_submit"))

    if phase != "submit":
        flash("Submissions are closed for this month.", "error")
        return redirect(url_for("competition_gallery"))

    file = request.files.get("image")
    if not file or file.filename == "":
        flash("Please choose an image.", "error")
        return redirect(url_for("competition_submit"))

    # (Optional) enforce ≤ 25 MB on the server as well
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
        flash("❌ Submissions must be anonymous. Do not include your name, Discord tag, ID, or mentions in the filename or caption.", "error")
        return redirect(url_for("competition_submit"))  # adjust endpoint name if different

    # Upload to R2 (resized)
    unique_name = uuid.uuid4().hex
    buf, content_type, ext_out = resize_to_max_edge(file)  # returns JPEG 85%
    object_key = f"{comp_id}/{unique_name}.{ext_out}"
    image_url = r2_put_object(buf, object_key, content_type)

    # Match UI limit
    caption = (request.form.get("caption") or "").strip()[:35]

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

    flash("Submission saved!", "success")
    # nicer loop: land back on Submit so they see their card (and later their vote)
    return redirect(url_for("competition_submit"))

@app.route("/competition/results")
def competition_results():
    # Allow optional override: /competition/results?comp_id=YYYY-MM
    override = request.args.get("comp_id")

    phase, comp_id = _phase_today()  # e.g. ("submit"|"voting"|"results", "2025-11")

    # Target month: results month when in results, otherwise previous month… unless overridden
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
        db = client["Website"]
        entries_col = db["CompEntries"]
        usernames_col = db["usernames"]  # or "super_trusted" if that's where display names live

        entries = list(entries_col.find({"comp_id": display_comp_id}))

        # Build a lookup: { discord_id: display_name }
        username_map = {
            str(u["_id"]): u.get("display_name") or u.get("username")
            for u in usernames_col.find({}, {"_id": 1, "display_name": 1, "username": 1})
        }

        # Attach display_name to entries
        for e in entries:
            e["display_name"] = username_map.get(str(e.get("user_id")), e.get("username") or "Anonymous")

        counts = _vote_counts_for(display_comp_id, client)

        comp_ids = sorted(
            entries_col.distinct("comp_id"),
            reverse=True  # newest first
        )

        # 🔒 Hide the *ongoing* competition month (current comp_id)
        # while we're still in submit/voting for that month.
        if phase != "results":
            comp_ids = [cid for cid in comp_ids if cid != comp_id]

        month_options = []
        for cid in comp_ids:
            try:
                y, m = map(int, cid.split("-"))
                label = datetime(y, m, 1).strftime("%B %Y")  # "October 2025"
            except Exception:
                label = cid
            month_options.append({"comp_id": cid, "label": label})

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
    grid  = paginate(entries_sorted, grid_page,  per_page=16)   # 4×4 “All entries”

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
        "first":  "1,000,000 coins + 1 month of Discord Nitro",
        "second": "700,000 coins",
        "third":  "500,000 coins",
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

    client = get_mongo_client()
    db = client["Website"]
    db["CompEntries"].delete_one({"comp_id": comp_id, "user_id": str(discord_id)})

    flash("Submission deleted.", "success")
    return redirect(url_for("competition_submit"))

@app.get("/admin/competition/votes/<entry_id>")
def admin_competition_votes(entry_id):
    if not is_staff(): 
        return "Unauthorized", 403

    client = get_mongo_client()
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
    client = get_mongo_client()
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

    new_caption = (request.form.get("caption") or "").strip()[:35]

    client = get_mongo_client()
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
    client = get_mongo_client()
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

    with MongoClient(os.getenv("MONGO_URI")) as client:
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
                # ⬇️ was changed: False
                return jsonify({"ok": True, "entry_id": new_entry_id, "changed": True})
            except DuplicateKeyError:
                # another request inserted first — re-fetch and continue below
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
    display_name = (request.form.get("display_name") or "").strip()   # ✅ NEW
    username_tag = (request.form.get("username") or "").strip()       # ✅ NEW (legacy tag like user#1234)
    file         = request.files.get("image")

    if not discord_id:
        return jsonify(ok=False, error="Missing discord_id"), 400
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
    buf, content_type, ext_out = resize_to_max_edge(file)
    object_key = f"{comp_id}/{unique_name}.{ext_out}"
    image_url = r2_put_object(buf, object_key, content_type)

    # Store entry (+names) and upsert usernames cache
    with MongoClient(os.getenv("MONGO_URI")) as c:
        db = c["Website"]

        db["CompEntries"].update_one(
            {"comp_id": comp_id, "user_id": str(discord_id)},
            {"$set": {
                "user_id": str(discord_id),
                "image_url": image_url,
                "caption": caption,
                "display_name": display_name or username_tag,  # ✅ prefer display name
                "username": username_tag,                      # ✅ keep legacy tag too
                "created_at": datetime.now(timezone.utc),
                "ip": request.remote_addr,
            }},
            upsert=True
        )

        db["usernames"].update_one(  # ✅ handy for joins/backfills elsewhere
            {"_id": str(discord_id)},
            {"$set": {
                "display_name": display_name or username_tag,
                "username": username_tag,
                "updated_at": datetime.now(timezone.utc),
            }},
            upsert=True
        )

    return jsonify(ok=True, comp_id=comp_id, image_url=image_url, caption=caption)


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

    with MongoClient(os.getenv("MONGO_URI")) as c:
        db = c["Website"]
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

    with MongoClient(os.getenv("MONGO_URI")) as c:
        db = c["Website"]
        db["CompEntries"].delete_one({"comp_id": comp_id, "user_id": str(discord_id)})

    return jsonify(ok=True, deleted=True)

# Start prewarm (sync or async based on env flag)
if os.getenv("WARM_THUMBS_SYNC", "0") == "1":
    # ✅ block until all thumbs are cached; fastest first paint
    prewarm_thumbs(size=THUMB_SIZE_DEFAULT, max_workers=12)
else:
    # background warm (still fine once app is “hot”)
    try:
        threading.Thread(target=lambda: prewarm_thumbs(size=THUMB_SIZE_DEFAULT, max_workers=12),
                         daemon=True).start()
        print("[thumbs] background prewarm thread started")
    except Exception as e:
        print("[thumbs] failed to start prewarm thread:", e)



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    env = os.getenv("FLASK_ENV", "prod")

    if env == "dev":
        # Local dev with livereload

        logging.getLogger("livereload").setLevel(logging.WARNING)

        server = Server(app)
        server.watch('templates/')
        server.watch('static/')
        server.serve(host='127.0.0.1', port=port)
    else:
        # Production for Fly.io
        app.run(host="0.0.0.0", port=port, threaded=True)

