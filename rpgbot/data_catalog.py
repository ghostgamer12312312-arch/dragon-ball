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

"""Static, data-only catalogs used by the Telegram RPG interface."""

SERIES = {
    "Dragon Ball": {"icon": "🐉", "characters": ["goku", "vegeta", "piccolo", "gohan", "trunks", "broly", "beerus", "krillin", "yamcha"]},
    "Naruto": {"icon": "🍥", "characters": ["naruto", "sasuke", "sakura", "kakashi", "gaara"]},
    "One Piece": {"icon": "🏴‍☠️", "characters": ["luffy", "zoro", "sanji", "nami", "ace"]},
    "Bleach": {"icon": "⚔️", "characters": ["ichigo", "byakuya", "renji", "rukia"]},
    "Jujutsu Kaisen": {"icon": "💀", "characters": ["yuji", "megumi", "gojo", "nobara", "sukuna"]},
}

_DATA = [
    ("goku", "Goku", "Dragon Ball", "Z", 5, "Ki", "Determined", "Kamehameha", 120, 22),
    ("vegeta", "Vegeta", "Dragon Ball", "Z", 5, "Ki", "Pride", "Galick Gun", 115, 24),
    ("piccolo", "Piccolo", "Dragon Ball", "S", 4, "Ki", "Guardian", "Special Beam Cannon", 135, 20),
    ("gohan", "Gohan", "Dragon Ball", "S", 4, "Ki", "Potential", "Masenko", 130, 21),
    ("trunks", "Future Trunks", "Dragon Ball", "S", 4, "Ki", "Brave", "Burning Attack", 125, 22),
    ("broly", "Broly", "Dragon Ball", "S", 4, "Ki", "Rage", "Gigantic Burst", 180, 30),
    ("beerus", "Beerus", "Dragon Ball", "Z", 5, "Destruction", "Divine", "Hakai", 165, 34),
    ("krillin", "Krillin", "Dragon Ball", "A", 3, "Ki", "Clever", "Destructo Disc", 95, 14),
    ("yamcha", "Yamcha", "Dragon Ball", "B", 2, "Ki", "Courage", "Wolf Fang Fist", 100, 13),
    ("naruto", "Naruto Uzumaki", "Naruto", "Z", 5, "Wind", "Determined", "Rasengan", 135, 24),
    ("sasuke", "Sasuke Uchiha", "Naruto", "Z", 5, "Lightning", "Focused", "Chidori", 125, 25),
    ("sakura", "Sakura Haruno", "Naruto", "A", 3, "Medical", "Strong", "Chakra Punch", 130, 18),
    ("kakashi", "Kakashi Hatake", "Naruto", "S", 4, "Lightning", "Strategist", "Raikiri", 125, 23),
    ("gaara", "Gaara", "Naruto", "S", 4, "Sand", "Calm", "Sand Coffin", 145, 21),
    ("luffy", "Monkey D. Luffy", "One Piece", "Z", 5, "Rubber", "Brave", "Gum-Gum Pistol", 145, 25),
    ("zoro", "Roronoa Zoro", "One Piece", "Z", 5, "Steel", "Relentless", "Three-Sword Style", 150, 26),
    ("sanji", "Sanji", "One Piece", "S", 4, "Fire", "Gallant", "Diable Jambe", 125, 23),
    ("nami", "Nami", "One Piece", "A", 3, "Weather", "Inventive", "Thunder Tempo", 100, 18),
    ("ace", "Portgas D. Ace", "One Piece", "S", 4, "Fire", "Loyal", "Flame Emperor", 130, 25),
    ("ichigo", "Ichigo Kurosaki", "Bleach", "Z", 5, "Reiatsu", "Fierce", "Getsuga Tensho", 145, 27),
    ("byakuya", "Byakuya Kuchiki", "Bleach", "S", 4, "Petal", "Disciplined", "Senbonzakura", 130, 23),
    ("renji", "Renji Abarai", "Bleach", "A", 3, "Reiatsu", "Loyal", "Zabimaru", 125, 21),
    ("rukia", "Rukia Kuchiki", "Bleach", "S", 4, "Ice", "Composed", "Sode no Shirayuki", 120, 22),
    ("yuji", "Yuji Itadori", "Jujutsu Kaisen", "Z", 5, "Cursed Energy", "Brave", "Divergent Fist", 140, 25),
    ("megumi", "Megumi Fushiguro", "Jujutsu Kaisen", "S", 4, "Shadow", "Thoughtful", "Ten Shadows", 125, 23),
    ("gojo", "Satoru Gojo", "Jujutsu Kaisen", "Z", 5, "Limitless", "Confident", "Limitless Void", 150, 30),
    ("nobara", "Nobara Kugisaki", "Jujutsu Kaisen", "A", 3, "Cursed Energy", "Bold", "Resonance", 115, 21),
    ("sukuna", "Ryomen Sukuna", "Jujutsu Kaisen", "Z", 5, "Cursed Energy", "Fearsome", "Cleave", 160, 32),
]
ALL_CHARACTERS = [dict(id=i, name=n, series=s, rank=r, rarity=q, element=e, trait=t, ability=a, hp=h, attack=atk) for i, n, s, r, q, e, t, a, h, atk in _DATA]
CHARACTERS = {c["id"]: c for c in ALL_CHARACTERS}

SKILLS = {
    "ki_blast": {"name": "Ki Blast", "power": 32, "mp_cost": 10, "cooldown": 1, "type": "Energy"},
    "kamehameha": {"name": "Kamehameha", "power": 68, "mp_cost": 20, "cooldown": 2, "type": "Blast"},
    "guardian_barrier": {"name": "Guardian Barrier", "power": 0, "mp_cost": 14, "cooldown": 3, "type": "Defense"},
    "spirit_burst": {"name": "Spirit Burst", "power": 55, "mp_cost": 18, "cooldown": 2, "type": "Energy"},
    "rasengan": {"name": "Rasengan", "power": 60, "mp_cost": 20, "cooldown": 2, "type": "Ninja"},
    "chidori": {"name": "Chidori", "power": 72, "mp_cost": 26, "cooldown": 3, "type": "Lightning"},
    "gum_gum_pistol": {"name": "Gum-Gum Pistol", "power": 64, "mp_cost": 22, "cooldown": 2, "type": "Striker"},
    "getsuga_tensho": {"name": "Getsuga Tensho", "power": 78, "mp_cost": 28, "cooldown": 3, "type": "Slash"},
    "cursed_reversal": {"name": "Cursed Reversal", "power": 58, "mp_cost": 18, "cooldown": 2, "type": "Barrier"},
    "healing_wave": {"name": "Healing Wave", "power": 0, "mp_cost": 14, "cooldown": 2, "type": "Support"},
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

    "village_scroll": {"name": "Village Scroll", "slot": "accessory", "attack": 5, "defense": 5, "rarity": "Rare"},
    "soul_robe": {"name": "Soul Robe", "slot": "armor", "attack": 4, "defense": 10, "rarity": "Epic"},
}
ITEMS = {
    "senzu": {"name": "Senzu Bean", "category": "consumable", "price": 40, "effect": "energy", "amount": 40, "description": "Restore 40 energy."},
    "ki_potion": {"name": "Ki Potion", "category": "consumable", "price": 60, "effect": "energy", "amount": 55, "description": "Restore 55 energy."},
    "exp_pill": {"name": "EXP Pill", "category": "consumable", "price": 35, "effect": "xp", "amount": 40, "description": "Gain 40 XP."},
    "coin_bag": {"name": "Coin Bag", "category": "consumable", "price": 80, "effect": "coins", "amount": 150, "description": "Gain 150 Zeni."},
    "stat_orb": {"name": "Stat Orb", "category": "consumable", "price": 90, "effect": "stats", "amount": 2, "description": "Add 2 stat points."},
    "enhance_stone": {"name": "Enhancement Stone", "category": "material", "price": 25, "effect": "material", "amount": 1, "description": "A stone used to enhance equipment."},
}
PETS = {
    "fox_pup": {"name": "Fox Pup", "rarity": "Rare", "bonus": "+5% attack", "cost": 120},
    "dragon_turtle": {"name": "Dragon Turtle", "rarity": "Epic", "bonus": "+8% defense", "cost": 240},
    "phoenix_kit": {"name": "Phoenix Kit", "rarity": "Legendary", "bonus": "+10% critical chance", "cost": 600},
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
BANNERS = {
    "starter": {"name": "Starter Banner", "cost": 50, "featured": ["goku", "vegeta", "krillin"]},
    "legend": {"name": "Legend Banner", "cost": 120, "featured": ["broly", "beerus", "gojo"]},
    "mythic": {"name": "Mythic Banner", "cost": 200, "featured": ["sukuna", "luffy", "naruto"]},
}
REGIONS = {"earth": {"name": "Earth", "weather": "Clear"}, "namek": {"name": "Namek", "weather": "Mist"}, "other_world": {"name": "Other World", "weather": "Starlight"}}
ENEMIES = [
    {"name": "Saibaman", "hp": 60, "attack": 10},
    {"name": "Frieza Force Scout", "hp": 85, "attack": 13},
    {"name": "Android Prototype", "hp": 110, "attack": 16},
    {"name": "Galactic Raider", "hp": 140, "attack": 19},
    {"name": "Shadow Ninja", "hp": 165, "attack": 23},
    {"name": "Soul Reaper", "hp": 190, "attack": 26},
]
RARITY_ICONS = {5: "★★★★★", 4: "★★★★☆", 3: "★★★☆☆", 2: "★★☆☆☆", 1: "★☆☆☆☆"}
RANK_MULTIPLIERS = {"Z": 1.8, "S": 1.5, "A": 1.2, "B": 1.0, "E": 0.8}

__all__ = [
    "SERIES", "ALL_CHARACTERS", "CHARACTERS", "SKILLS", "GEAR", "ITEMS",
    "PETS", "DUNGEONS", "BANNERS", "REGIONS", "ENEMIES", "RARITY_ICONS",
    "RANK_MULTIPLIERS",
]
