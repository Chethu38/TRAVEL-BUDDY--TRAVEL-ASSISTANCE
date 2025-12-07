# seed_cities.py — insert Ballari city + places into MongoDB if missing

import os
from datetime import datetime
from pymongo import MongoClient

# Use same URI as your app
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/travelbuddy")


def get_db():
    """Return a MongoDB database handle without using boolean checks."""
    client = MongoClient(MONGO_URI)

    # If URI contains a db name, this returns it; otherwise None
    db = client.get_default_database()
    if db is None:
        db = client["travelbuddy"]
    return db


def seed_cities():
    """
    Seed Ballari city and its places into MongoDB.

    Safe to call multiple times:
    - If Ballari already exists (_id='ballari'), it will NOT insert again.
    """
    db = get_db()
    cities_col = db["cities"]
    places_col = db["places"]

    # Check if Ballari already exists
    try:
        exists = cities_col.count_documents({"_id": "ballari"}, limit=1)
    except Exception as e:
        print("❌ Could not check Ballari city in DB:", e)
        return

    if exists:
        print("ℹ Ballari city already exists in DB, skipping insert.")
        return

    ballari_city = {
        "_id": "ballari",  # slug for /city/ballari
        "name": "Ballari",
        "state": "Karnataka",
        "country": "India",
        "description": (
            "Ballari (Bellary) is a historic city in Karnataka known for its ancient "
            "forts, temples, and proximity to Hampi."
        ),
        "heroImage": "/static/cities/ballari/ballari_city.jpg",
        "lat": 15.1394,
        "lng": 76.9214,
        "tags": ["historic", "forts", "temples", "heritage"],
        "created_at": datetime.utcnow(),
    }

    ballari_places = [
        {
            "cityId": "ballari",
            "type": "place",
            "name": "Ballari Fort (Kote Gudda & Fort Hill)",
            "image": "/static/cities/ballari/ballari_fort.jpg",
            "lat": 15.1501,
            "lng": 76.9218,
            "address": "Fort Area, Ballari, Karnataka",
            "openTime": "06:00",
            "closeTime": "18:30",
            "description": (
                "A historic hill fort offering panoramic views of Ballari city. "
                "Divided into Upper Fort and Lower Fort sections."
            ),
        },
        {
            "cityId": "ballari",
            "type": "place",
            "name": "Kumaraswamy Temple, Sandur",
            "image": "/static/cities/ballari/kumaraswamy_temple.jpg",
            "lat": 15.0074,
            "lng": 76.5468,
            "address": "Swamy Temple Rd, Sandur Taluk, Ballari District",
            "openTime": "06:00",
            "closeTime": "20:00",
            "description": (
                "An ancient temple dedicated to Lord Kumaraswamy, located in the scenic "
                "hills near Sandur."
            ),
        },
        {
            "cityId": "ballari",
            "type": "place",
            "name": "Hampi (UNESCO World Heritage Site)",
            "image": "/static/cities/ballari/hampi.jpg",
            "lat": 15.3350,
            "lng": 76.4600,
            "address": "Hampi, Ballari District, Karnataka",
            "openTime": "06:00",
            "closeTime": "18:00",
            "description": (
                "Ancient capital of the Vijayanagara Empire, famous for stone temples, "
                "ruins, and boulder landscapes."
            ),
        },
        {
            "cityId": "ballari",
            "type": "place",
            "name": "Tungabhadra Dam (TB Dam)",
            "image": "/static/cities/ballari/tb_dam.jpg",
            "lat": 15.2883,
            "lng": 76.4750,
            "address": "T.B. Dam, near Hospete, Ballari District",
            "openTime": "09:00",
            "closeTime": "19:00",
            "description": (
                "Large dam across the Tungabhadra river with gardens and viewpoints. "
                "Popular evening spot near Hosapete."
            ),
        },
        {
            "cityId": "ballari",
            "type": "food",
            "name": "Local Tiffin Spots (Idli, Dosa, Bonda)",
            "image": "/static/cities/ballari/ballari_tiffin.jpg",
            "lat": 15.1400,
            "lng": 76.9200,
            "address": "Various tiffin hotels around Ballari Bus Stand",
            "openTime": "06:30",
            "closeTime": "11:30",
            "description": (
                "Popular for South Indian breakfast items like idli, dosa, vada, "
                "and filter coffee."
            ),
        },
        {
            "cityId": "ballari",
            "type": "food",
            "name": "Evening Chaat & Street Food",
            "image": "/static/cities/ballari/ballari_street_food.jpg",
            "lat": 15.1420,
            "lng": 76.9250,
            "address": "Market area & major circles in Ballari city",
            "openTime": "17:00",
            "closeTime": "22:30",
            "description": (
                'Street food stalls serving chaat, pav bhaji, gobi, and other popular '
                "snacks in the evenings."
            ),
        },
    ]

    try:
        cities_col.insert_one(ballari_city)
        if ballari_places:
            places_col.insert_many(ballari_places)
        print("✅ Seeded Ballari city + places into MongoDB.")
    except Exception as e:
        print("❌ Failed to seed Ballari data:", e)


if __name__ == "__main__":
    # Optional: allow manual run too
    seed_cities()
