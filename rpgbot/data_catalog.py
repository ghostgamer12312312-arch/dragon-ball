from __future__ import annotations

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
ALL_CHARACTERS = [dict(id=i, name=n, series=s, rank=r, rarity=q, element=e, trait=t, ability=a, hp=h, attack=atk) for i,n,s,r,q,e,t,a,h,atk in _DATA]
CHARACTERS = {c["id"]: c for c in ALL_CHARACTERS}

SKILLS = {
    "ki_blast": {"name":"Ki Blast", "power":32, "mp_cost":10, "cooldown":1, "type":"Energy"},
    "kamehameha": {"name":"Kamehameha", "power":68, "mp_cost":20, "cooldown":2, "type":"Blast"},
    "guardian_barrier": {"name":"Guardian Barrier", "power":0, "mp_cost":14, "cooldown":3, "type":"Defense"},
    "spirit_burst": {"name":"Spirit Burst", "power":55, "mp_cost":18, "cooldown":2, "type":"Energy"},
}
GEAR = {
    "saiyan_band":{"name":"Saiyan Band","slot":"ring","attack":6,"defense":2,"rarity":"Rare"},
    "shadow_armor":{"name":"Shadow Armor","slot":"armor","attack":3,"defense":12,"rarity":"Epic"},
    "dragon_blade":{"name":"Dragon Blade","slot":"weapon","attack":15,"defense":0,"rarity":"Legendary"},
    "healer_amulet":{"name":"Healer Amulet","slot":"amulet","attack":2,"defense":4,"rarity":"Rare"},
}
ITEMS = {
    "senzu":{"name":"Senzu Bean","category":"consumable","price":40,"effect":"energy","amount":40,"description":"Restore 40 energy."},
    "exp_pill":{"name":"EXP Pill","category":"consumable","price":35,"effect":"xp","amount":40,"description":"Gain 40 XP."},
    "enhance_stone":{"name":"Enhancement Stone","category":"material","price":25,"effect":"material","amount":1,"description":"A stone used to enhance equipment."},
}
PETS = {
    "fox_pup":{"name":"Fox Pup","rarity":"Rare","bonus":"+5% attack","cost":120},
    "dragon_turtle":{"name":"Dragon Turtle","rarity":"Epic","bonus":"+8% defense","cost":240},
    "phoenix_kit":{"name":"Phoenix Kit","rarity":"Legendary","bonus":"+10% critical chance","cost":600},
}
DUNGEONS = {
    "forest":{"name":"Whispering Forest","difficulty":"Normal","reward":150},
    "ruins":{"name":"Ancient Ruins","difficulty":"Hard","reward":300},
    "heaven":{"name":"Heaven Gate","difficulty":"Nightmare","reward":500},
}
BANNERS = {"starter":{"name":"Starter Banner","cost":50},"legend":{"name":"Legend Banner","cost":120},"mythic":{"name":"Mythic Banner","cost":200}}
REGIONS = {"earth":{"name":"Earth","weather":"Clear"},"namek":{"name":"Namek","weather":"Mist"},"other_world":{"name":"Other World","weather":"Starlight"}}
ENEMIES = [
    {"name":"Saibaman","hp":60,"attack":10},
    {"name":"Frieza Force Scout","hp":85,"attack":13},
    {"name":"Android Prototype","hp":110,"attack":16},
    {"name":"Galactic Raider","hp":140,"attack":19},
]
RARITY_ICONS = {5:"★★★★★",4:"★★★★☆",3:"★★★☆☆",2:"★★☆☆☆",1:"★☆☆☆☆"}
RANK_MULTIPLIERS = {"Z":1.8,"S":1.5,"A":1.2,"B":1.0,"E":0.8}
