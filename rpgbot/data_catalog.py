from __future__ import annotations

"""Expanded static catalogs, game data definitions, and progression tables.

This is intentionally large and structured so it can support advanced anime RPG
features later without reworking the existing SQLite logic.
"""

from typing import Any

SERIES = {
    "Dragon Ball": {
        "icon": "🐉",
        "characters": [
            {"id": "goku", "name": "Goku", "rank": "Z", "rarity": 5, "element": "Ki", "trait": "Determined", "ability": "Kamehameha Burst", "form": "Base"},
            {"id": "vegeta", "name": "Vegeta", "rank": "Z", "rarity": 5, "element": "Ki", "trait": "Pride", "ability": "Galick Gun", "form": "Base"},
            {"id": "piccolo", "name": "Piccolo", "rank": "S", "rarity": 4, "element": "Energy", "trait": "Guardian", "ability": "Special Beam Cannon", "form": "Base"},
            {"id": "gohan", "name": "Gohan", "rank": "S", "rarity": 4, "element": "Ki", "trait": "Tutor", "ability": "Masenko", "form": "Base"},
            {"id": "trunks", "name": "Future Trunks", "rank": "S", "rarity": 4, "element": "Ki", "trait": "Heroic", "ability": "Burning Attack", "form": "Base"},
            {"id": "broly", "name": "Broly", "rank": "S", "rarity": 4, "element": "Ki", "trait": "Rage", "ability": "Gigantic Burst", "form": "Base"},
            {"id": "beerus", "name": "Beerus", "rank": "Z", "rarity": 5, "element": "Destruction", "trait": "Divine", "ability": "Hakai", "form": "Base"},
            {"id": "krillin", "name": "Krillin", "rank": "A", "rarity": 3, "element": "Ki", "trait": "Clever", "ability": "Kamehameha", "form": "Base"},
            {"id": "yamcha", "name": "Yamcha", "rank": "B", "rarity": 2, "element": "Ki", "trait": "Charming", "ability": "Wolf Fang Fist", "form": "Base"},
        ],
    },
    "Naruto": {
        "icon": "🐺",
        "characters": [
            {"id": "naruto", "name": "Naruto Uzumaki", "rank": "Z", "rarity": 5, "element": "Wind", "trait": "Determined", "ability": "Rasengan", "form": "Base"},
            {"id": "sasuke", "name": "Sasuke Uchiha", "rank": "Z", "rarity": 5, "element": "Lightning", "trait": "Ambition", "ability": "Chidori", "form": "Base"},
            {"id": "sakura", "name": "Sakura Haruno", "rank": "S", "rarity": 4, "element": "Medical", "trait": "Strong", "ability": "Chakra Punch", "form": "Base"},
            {"id": "gaara", "name": "Gaara", "rank": "S", "rarity": 4, "element": "Sand", "trait": "Stoic", "ability": "Sand Coffin", "form": "Base"},
            {"id": "kakashi", "name": "Kakashi Hatake", "rank": "S", "rarity": 4, "element": "Lightning", "trait": "Strategist", "ability": "Copy Ninja", "form": "Base"},
            {"id": "hinata", "name": "Hinata Hyuga", "rank": "A", "rarity": 3, "element": "Gentle Fist", "trait": "Determined", "ability": "Twin Lion Fists", "form": "Base"},
            {"id": "rocklee", "name": "Rock Lee", "rank": "A", "rarity": 3, "element": "Taijutsu", "trait": "Hardworking", "ability": "Primary Lotus", "form": "Base"},
            {"id": "jiraya", "name": "Jiraiya", "rank": "S", "rarity": 4, "element": "Wind", "trait": "Legend", "ability": "Toad Summon", "form": "Base"},
        ],
    },
    "One Piece": {
        "icon": "🏴‍☠️",
        "characters": [
            {"id": "luffy", "name": "Monkey D. Luffy", "rank": "Z", "rarity": 5, "element": "Rubber", "trait": "Brave", "ability": "Gomu Gomu", "form": "Base"},
            {"id": "zoro", "name": "Roronoa Zoro", "rank": "Z", "rarity": 5, "element": "Steel", "trait": "Relentless", "ability": "Three-Sword Style", "form": "Base"},
            {"id": "sanji", "name": "Sanji", "rank": "S", "rarity": 4, "element": "Fire", "trait": "Gallant", "ability": "Diable Jambe", "form": "Base"},
            {"id": "nami", "name": "Nami", "rank": "S", "rarity": 4, "element": "Weather", "trait": "Smart", "ability": "Thundercloud Tempest", "form": "Base"},
            {"id": "usopp", "name": "Usopp", "rank": "A", "rarity": 3, "element": "Trick", "trait": "Inventive", "ability": "Pop Green", "form": "Base"},
            {"id": "brook", "name": "Brook", "rank": "A", "rarity": 3, "element": "Soul", "trait": "Calm", "ability": "Soul Solid", "form": "Base"},
            {"id": "ace", "name": "Portgas D. Ace", "rank": "S", "rarity": 4, "element": "Fire", "trait": "Burning", "ability": "Flare-Flare", "form": "Base"},
        ],
    },
    "Bleach": {
        "icon": "🩸",
        "characters": [
            {"id": "ichigo", "name": "Ichigo Kurosaki", "rank": "Z", "rarity": 5, "element": "Reiatsu", "trait": "Fierce", "ability": "Getsuga Tensho", "form": "Base"},
            {"id": "byakuya", "name": "Byakuya Kuchiki", "rank": "S", "rarity": 4, "element": "Kido", "trait": "Elegant", "ability": "Senbonzakura", "form": "Base"},
            {"id": "renji", "name": "Renji Abarai", "rank": "S", "rarity": 4, "element": "Fire", "trait": "Fierce", "ability": "Sode No Shirayuki", "form": "Base"},
            {"id": "orihime", "name": "Orihime Inoue", "rank": "A", "rarity": 3, "element": "Healing", "trait": "Kind", "ability": "Santen Kesshun", "form": "Base"},
            {"id": "ulquiorra", "name": "Ulquiorra", "rank": "S", "rarity": 4, "element": "Void", "trait": "Cold", "ability": "Cero", "form": "Base"},
        ],
    },
    "Jujutsu Kaisen": {
        "icon": "💀",
        "characters": [
            {"id": "yuji", "name": "Yuji Itadori", "rank": "Z", "rarity": 5, "element": "Cursed", "trait": "Brave", "ability": "Divergent Fist", "form": "Base"},
            {"id": "megumi", "name": "Megumi Fushiguro", "rank": "Z", "rarity": 5, "element": "Shadow", "trait": "Calm", "ability": "Ten Shadows", "form": "Base"},
            {"id": "gojo", "name": "Satoru Gojo", "rank": "Z", "rarity": 5, "element": "Limitless", "trait": "Confident", "ability": "Infinity", "form": "Base"},
            {"id": "nobara", "name": "Nobara Kugisaki", "rank": "S", "rarity": 4, "element": "Strawberry", "trait": "Bold", "ability": "Hairpin Hammer", "form": "Base"},
            {"id": "sukuna", "name": "Ryomen Sukuna", "rank": "Z", "rarity": 5, "element": "Cursed", "trait": "Dread", "ability": "Cleave", "form": "Base"},
        ],
    },
}

CHARACTERS = {name: data for series in SERIES.values() for name in [char["id"] for char in series["characters"]]}

for _series_name, meta in SERIES.items():
    for item in meta["characters"]:
        item["series"] = _series_name

ALL_CHARACTERS = [char for series in SERIES.values() for char in series["characters"]]

SKILLS = {
    "kamehameha": {"name": "Kamehameha", "power": 68, "mp_cost": 18, "cooldown": 2, "type": "Blast"},
    "rasengan": {"name": "Rasengan", "power": 62, "mp_cost": 16, "cooldown": 2, "type": "Burst"},
    "hit": {"name": "Heavy Hit", "power": 38, "mp_cost": 8, "cooldown": 1, "type": "Strike"},
    "heal": {"name": "Impulse Heal", "power": 24, "mp_cost": 12, "cooldown": 4, "type": "Support"},
    "tornado": {"name": "Tornado Slash", "power": 58, "mp_cost": 15, "cooldown": 2, "type": "AoE"},
    "guardian": {"name": "Guardian Barrier", "power": 0, "mp_cost": 12, "cooldown": 3, "type": "Defense"},
}

GEAR = {
    "saiyan_band": {"name": "Saiyan Band", "slot": "ring", "attack": 6, "defense": 2, "rarity": "Rare"},
    "shadow_armor": {"name": "Shadow Armor", "slot": "armor", "attack": 3, "defense": 12, "rarity": "Epic"},
    "dragon_blade": {"name": "Dragon Blade", "slot": "weapon", "attack": 15, "defense": 0, "rarity": "Legendary"},
    "healer_amulet": {"name": "Healer Amulet", "slot": "amulet", "attack": 2, "defense": 4, "rarity": "Rare"},
}

ITEMS = {
    "senzu": {"name": "Senzu Bean", "category": "consumable", "price": 40, "effect": "energy", "amount": 40},
    "exp_pill": {"name": "EXP Pill", "category": "consumable", "price": 30, "effect": "xp", "amount": 40},
    "iron": {"name": "Iron Ore", "category": "material", "price": 12, "effect": "material", "amount": 1},
    "stone": {"name": "Enhancement Stone", "category": "material", "price": 20, "effect": "craft", "amount": 1},
}

PETS = {
    "fox_pup": {"name": "Fox Pup", "rarity": "Rare", "bonus": "+5% attack", "cost": 120},
    "dragon_turtle": {"name": "Dragon Turtle", "rarity": "Epic", "bonus": "+8% defense", "cost": 240},
    "phoenix_kit": {"name": "Phoenix Kit", "rarity": "Legendary", "bonus": "+10% crit", "cost": 600},
}

DUNGEONS = {
    "forest": {"name": "Whispering Forest", "difficulty": "Normal", "reward": 150},
    "ruins": {"name": "Ancient Ruins", "difficulty": "Hard", "reward": 300},
    "heaven": {"name": "Heaven Gate", "difficulty": "Nightmare", "reward": 500},
}

BANNERS = {
    "starter": {"name": "Starter Banner", "cost": 50, "rate": 0.8},
    "legend": {"name": "Legend Banner", "cost": 120, "rate": 0.3},
    "mythic": {"name": "Mythic Banner", "cost": 200, "rate": 0.15},
}

RANKS = ["Z", "S", "A", "B", "E"]
RARITY_ICONS = {5: "★★★★★", 4: "★★★★☆", 3: "★★★☆☆", 2: "★★☆☆☆", 1: "★☆☆☆☆"}

REGIONS = {
    "earth": {"name": "Earth", "weather": "Clear", "zone": "City District"},
    "namek": {"name": "Namek", "weather": "Mist", "zone": "Temple Plains"},
    "kaleidoscope": {"name": "Kaleidoscope Realm", "weather": "Storm", "zone": "Sky Bridge"},
}

ADMIN_STATS = {
    "rank_multipliers": {"Z": 1.8, "S": 1.5, "A": 1.2, "B": 1.0, "E": 0.8},
    "rarity_multiplier": {5: 1.8, 4: 1.5, 3: 1.2, 2: 1.0, 1: 0.8},
}


def resolve_character(key: str) -> dict[str, Any] | None:
    for char in ALL_CHARACTERS:
        if char["id"] == key or char["name"].lower() == key.lower():
            return char
    return None


def resolve_skill(name: str) -> dict[str, Any] | None:
    name = name.lower()
    for skill_name, skill in SKILLS.items():
        if skill_name == name or skill["name"].lower() == name:
            return skill
    return None
