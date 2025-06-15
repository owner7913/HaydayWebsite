# 🌾 HayDay 🍀 Web App

Flask-based community portal integrated with a Discord bot for linking Hay Day IDs, managing giveaways, auctions, and more.

---

## ✅ Features

### 🌐 Frontpage Widgets
- Blurred minimalistic background with theme toggle
- 🎁 **Live Giveaways** with avatars, fade-in animations, scroll
- 📰 **News Feed** from YouTube, Twitter, Instagram (RSS-based)
- 📦 **Latest Auctions** (placeholder with live data support coming)

### 👤 User Tools
- Discord login with session support
- Profile view with level, XP, boost timer, and rank
- Scam ID checking and moderation tools
- Mute, ban, and unban web interface
- Staff-only ticket viewer and reply system

---

## 🛠️ Local Development

### 🔧 Requirements
- Python 3.10+
- MongoDB connection
- Discord bot + tokens

### ▶️ Run Locally

```bash
git clone https://github.com/yourname/hayday-verification.git
cd hayday-verification
pip install -r requirements.txt
cp .env.example .env  # or manually create .env
python app.py
```

The app runs at:  
👉 http://127.0.0.1:8080

To enable **live reloading**, the app uses `livereload` if `FLASK_ENV=dev` is set.

---

## 🚀 Deployment on Fly.io

### 🐳 Docker-based Fly Setup

```bash
fly deploy
```

Make sure `.env` has:

```
FLASK_ENV=prod
PORT=8080
```

The app will be hosted at `https://<your-app-name>.fly.dev`

---

## 🗂️ Project Structure

```
/templates             # Jinja2 HTML templates (header, footer, index, etc.)
/static/css/theme.css  # Light/dark mode styles
/static/js             # Widget loaders and client logic
app.py                 # Flask web app (routes, APIs)
Dockerfile             # Fly.io-compatible Docker config
.env                   # Environment variables
```

---

## 🧪 Integrated Discord Bot

The bot supports:
- Sending auction/giveaway updates to Discord
- News fetch from RSS and syncing with MongoDB
- Reaction roles, mute/unmute, and sync logic

> News entries update only if new OR missing thumbnails.

---

## 📸 Visual Highlights

- ✨ Modern UI using blurred background and grid layout
- 🧑 Avatars on giveaways and staff listings
- 🔄 Smooth transitions and entry animations
- ⚙️ Responsive design for mobile/tablet

---

## 🙌 Credits

Created by [xavi] for the Hay Day Discord Community  
Assets © Supercell  
Bot backend hosted with Fly.io  
Web app powered by Flask + MongoDB
