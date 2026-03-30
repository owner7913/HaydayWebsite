# shop_data.py
# Website-side shop catalog.
# Mirrors the bot-side SHOP_ITEMS in shop_updated.py, with extra UI metadata.
# - category: grouping in UI
# - permanent: only for “one-time / tier-unlock” items (used for "Already Owned" label)

SHOP_ITEMS = {
    # -----------------------------
    # Core / Boosts
    # -----------------------------
    "custom_role": {
        "name": "🛡️ Custom Role",
        "price": 340000,
        "description": "Requires a perfect 365-day streak. Staff will help you configure it.",
        "category": "Prestige",
        "permanent": True,
    },
    "level_boost": {
        "name": "⚡ Level Boost",
        "price": 900,
        "description": "Gives you +300 XP instantly.",
        "category": "Boosts",
        "permanent": False,
    },
    "xp_boost_6h": {
        "name": "🔥 6-Hour XP Boost",
        "price": 1800,
        "description": "Doubles XP from messages for 6 hours.",
        "category": "Boosts",
        "permanent": False,
    },
    "coin_boost_24h": {
        "name": "💰 Coin Boost (24h)",
        "price": 2000,
        "description": "Doubles all coins earned from any source for the next 24 hours.",
        "category": "Boosts",
        "permanent": False,
    },

    # -----------------------------
    # Trivia / Daily / Utility
    # -----------------------------
    "trivia_hint": {
        "name": "🧠 Trivia Hint",
        "price": 800,
        "description": "Eliminates one wrong answer from your next trivia question.",
        "category": "Utility",
        "permanent": False,
    },
    "boosted_trivia": {
        "name": "📚 Easy Trivia Mode",
        "price": 900,
        "description": "Your next trivia question will be guaranteed Easy difficulty.",
        "category": "Utility",
        "permanent": False,
    },
    "double_daily": {
        "name": "🎁 Double Daily",
        "price": 1200,
        "description": "Doubles the coins and XP from your next `/daily` claim. One-time use.",
        "category": "Daily",
        "permanent": False,
    },
    "daily_reset": {
        "name": "🔁 Daily Reset",
        "price": 1500,
        "description": "Instantly resets your `/daily` cooldown.",
        "category": "Daily",
        "permanent": False,
    },

    # -----------------------------
    # Social / Chaos
    # -----------------------------
    "gift_random": {
        "name": "🎲 Random Coin Gift",
        "price": 600,
        "description": "Gives a random server member between 10–50 coins.",
        "category": "Social",
        "permanent": False,
    },
    "mute_other_20m": {
        "name": "🔇 Mute Someone (20m)",
        "price": 1000,
        "description": "Mutes a member of your choice for 20 minutes. (Staff immune)",
        "category": "Chaos",
        "permanent": False,
    },
    "self_mute_rng": {
        "name": "🎲 Self-Mute Randomizer",
        "price": 500,
        "description": "Mutes you for a random time between 1 and 20 minutes.",
        "category": "Chaos",
        "permanent": False,
    },
    "ping_storm": {
        "name": "📡 Ping Storm",
        "price": 400,
        "description": "Sends 5 pings to someone in their DMs. Cooldown applies.",
        "category": "Chaos",
        "permanent": False,
    },
    "ghost_ping": {
        "name": "👻 Ghost Ping",
        "price": 300,
        "description": "Bot ghost-pings someone in a public channel of your choice.",
        "category": "Chaos",
        "permanent": False,
    },
    "mute_immunity": {
        "name": "🛡️ Mute Immunity",
        "price": 800,
        "description": "Protects you from the next mute used on you.",
        "category": "Defense",
        "permanent": False,
    },
    "invert_name": {
        "name": "🔁 Invert Name",
        "price": 1000,
        "description": "Reverses your nickname for 30 minutes.",
        "category": "Chaos",
        "permanent": False,
    },

    # -----------------------------
    # Cosmetics / Prestige
    # -----------------------------
    "custom_color_30d": {
        "name": "🎨 Custom Color Role (30 Days)",
        "price": 120000,
        "description": "Creates a temporary color role for 30 days. Replaces your previous color role if you have one.",
        "category": "Cosmetics",
        "permanent": False,
    },
    "wealth_flex_role": {
        "name": "💎 Wealth Flex Role",
        "price": 400000,
        "description": "Permanent prestige role. One-time purchase.",
        "category": "Prestige",
        "permanent": True,   # treat as one-time in website UI
    },
    "millionaire_club_role": {
        "name": "👑 Millionaire Club Role",
        "price": 1000000,
        "description": "Long-term endgame goal role.",
        "category": "Prestige",
        "permanent": True,   # treat as one-time in website UI
    },

    # -----------------------------
    # Upgrades / Tiers
    # -----------------------------
    "daily_upgrade_t1": {
        "name": "📈 Daily Income Upgrade Tier I",
        "price": 50000,
        "description": "+65 coins +65xp permanently added to daily reward.",
        "category": "Upgrades",
        "permanent": True,
    },
    "daily_upgrade_t2": {
        "name": "📈 Daily Income Upgrade Tier II",
        "price": 150000,
        "description": "+225 coins +225xp permanently added to daily reward.",
        "category": "Upgrades",
        "permanent": True,
    },
    "daily_upgrade_t3": {
        "name": "📈 Daily Income Upgrade Tier III",
        "price": 300000,
        "description": "+500 coins +500xp permanently added to daily reward.",
        "category": "Upgrades",
        "permanent": True,
    },

    # repeatable (max 3) => NOT permanent, otherwise your website would hide the buy button after 1 purchase
    "passive_income_t1": {
        "name": "🏦 Passive Message Income Tier I",
        "price": 200000,
        "description": "+2 coins per message. Daily cap: 400 coins/day from this source.",
        "category": "Upgrades",
        "permanent": True,
    },
    "passive_income_t2": {
        "name": "🏦 Passive Message Income Tier II",
        "price": 350000,
        "description": "+4 coins per message. Daily cap: 500 coins/day from this source.",
        "category": "Upgrades",
        "permanent": True,
    },
    "passive_income_t3": {
        "name": "🏦 Passive Message Income Tier III",
        "price": 500000,
        "description": "+6 coins per message. Daily cap: 600 coins/day from this source.",
        "category": "Upgrades",
        "permanent": True,
    },

    "perm_xp_boost_t1": {
        "name": "⭐ Permanent XP Boost Tier 1",
        "price": 75000,
        "description": "Permanent +3% XP. (Max total 10%)",
        "category": "Upgrades",
        "permanent": True,
    },
    "perm_xp_boost_t2": {
        "name": "⭐⭐ Permanent XP Boost Tier 2",
        "price": 125000,
        "description": "Permanent +3% XP. (Max total 10%)",
        "category": "Upgrades",
        "permanent": True,
    },
    "perm_xp_boost_t3": {
        "name": "⭐⭐⭐ Permanent XP Boost Tier 3",
        "price": 200000,
        "description": "Permanent +4% XP. (Max total 10%)",
        "category": "Upgrades",
        "permanent": True,
    },

    # -----------------------------
    # New tokens / crates
    # -----------------------------
    "restore_daily_streak": {
        "name": "🧩 Restore Daily Streak",
        "price": 75000,
        "description": "Restores your lost daily streak if broken within the last 48 hours. Can only be used once every 30 days.",
        "category": "Daily",
        "permanent": False,
    },
    "high_roller_crate": {
        "name": "🎰 High Roller Crate",
        "price": 50000,
        "description": "Random outcome: coin reward, XP, temporary boost, or nothing. Limit: Max 1 per 24 hours.",
        "category": "Crates",
        "permanent": False,
    },
    "nickname_chaos": {
        "name": "🌀 Nickname Chaos (24h)",
        "price": 35000,
        "description": "Scrambles a target's nickname for 24h. If they change it, it will be scrambled again.",
        "category": "Chaos",
        "permanent": False,
    },
}