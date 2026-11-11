from __future__ import annotations

CHARACTERS = {
    "goku": {"name":"Goku","rarity":"Common","attack":14,"hp":110},
    "krillin": {"name":"Krillin","rarity":"Common","attack":12,"hp":95},
    "yamcha": {"name":"Yamcha","rarity":"Common","attack":13,"hp":100},
    "piccolo": {"name":"Piccolo","rarity":"Rare","attack":18,"hp":135},
    "gohan": {"name":"Gohan","rarity":"Rare","attack":19,"hp":130},
    "vegeta": {"name":"Vegeta","rarity":"Epic","attack":24,"hp":145},
    "trunks": {"name":"Future Trunks","rarity":"Epic","attack":23,"hp":140},
    "broly": {"name":"Broly","rarity":"Legendary","attack":31,"hp":180},
    "beerus": {"name":"Beerus","rarity":"Legendary","attack":34,"hp":165},
    "shenron": {"name":"Shenron","rarity":"Mythic","attack":39,"hp":200},
}
RARITY_WEIGHTS = (("Common", 50), ("Rare", 28), ("Epic", 14), ("Legendary", 7), ("Mythic", 1))
ENEMIES = (
    {"name":"Saibaman","attack":9,"hp":50,"coins":(12,24),"xp":(18,30)},
    {"name":"Frieza Force Scout","attack":12,"hp":68,"coins":(18,32),"xp":(25,38)},
    {"name":"Android Prototype","attack":15,"hp":82,"coins":(24,42),"xp":(32,48)},
    {"name":"Galactic Raider","attack":18,"hp":100,"coins":(32,55),"xp":(42,62)},
)
ITEMS = {
    "senzu": {"name":"Senzu Bean","description":"Restore 40 energy","price":35,"effect":"energy","amount":40},
    "orb": {"name":"Training Orb","description":"Gain 60 XP","price":50,"effect":"xp","amount":60},
    "capsule": {"name":"Energy Capsule","description":"Restore 25 energy","price":20,"effect":"energy","amount":25},
}
QUESTS = {
    "explore_3":{"name":"Scout the frontier","action":"explore","goal":3,"coins":60,"xp":35},
    "train_2":{"name":"Daily training","action":"train","goal":2,"coins":45,"xp":45},
    "battle_1":{"name":"Prove your strength","action":"battle","goal":1,"coins":55,"xp":40},
}
