# user_profile.py
from flask import Blueprint, request, jsonify
import os
import time

try:
    from pymongo import MongoClient
    MONGO_AVAILABLE = True
except Exception:
    MongoClient = None
    MONGO_AVAILABLE = False

profile_bp = Blueprint("profile_bp", __name__)

# In-memory fallback if Mongo is not available
_in_memory_db = {
    "profiles": {},
    "history": [],
}


def get_mongo():
    """
    Returns a MongoDB database handle or None if not available.
    Avoids using truthiness on db objects.
    """
    if not MONGO_AVAILABLE or MongoClient is None:
        return None

    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/travelbuddy")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        db = client.get_default_database()
        if db is None:
            db = client["travelbuddy"]
        # force connection
        client.admin.command("ping")
        return db
    except Exception as e:
        print("⚠ get_mongo failed:", e)
        return None


# -----------------------------
# Profile endpoints
# -----------------------------
@profile_bp.route("/profile", methods=["GET", "POST"])
def profile():
    """
    Profile API used by profile.html

    GET  /api/profile?email=...
        → { "ok": true, "user": { ... } }
        If no profile found, returns default object (not 404).

    POST /api/profile
        JSON: {
          "email": "...",
          "fullName": "...",
          "phone": "...",
          "timezone": "...",
          "bio": "...",
          "avatarDataUrl": "data:image/...base64" (optional)
        }
        → { "ok": true, "user": { ... } }
    """
    db = get_mongo()

    # --------- SAVE PROFILE (POST) ---------
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        email = (data.get("email") or "").strip().lower()

        if not email:
            return jsonify({"ok": False, "error": "Email is required"}), 400

        doc = {
            "email": email,
            "fullName": data.get("fullName", ""),
            "phone": data.get("phone", ""),
            "timezone": data.get("timezone", "Asia/Kolkata"),
            "bio": data.get("bio", ""),
            "avatarDataUrl": data.get("avatarDataUrl") or None,
            "updated_at": time.time(),
        }

        if db is not None:
            try:
                db.profiles.update_one({"email": email}, {"$set": doc}, upsert=True)
            except Exception as e:
                print("⚠ Mongo error saving profile:", e)
                _in_memory_db["profiles"][email] = doc
        else:
            _in_memory_db["profiles"][email] = doc

        return jsonify({"ok": True, "user": doc})

    # --------- LOAD PROFILE (GET) ---------
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok": False, "error": "Email query parameter is required"}), 400

    row = None
    if db is not None:
        try:
            row = db.profiles.find_one({"email": email}, {"_id": 0})
        except Exception as e:
            print("⚠ Mongo error loading profile:", e)
            row = None
    else:
        row = _in_memory_db["profiles"].get(email)

    if not row:
        # No profile yet → return default shape
        row = {
            "email": email,
            "fullName": "",
            "phone": "",
            "timezone": "Asia/Kolkata",
            "bio": "",
            "avatarDataUrl": None,
            "updated_at": time.time(),
        }

    return jsonify({"ok": True, "user": row})


# -----------------------------
# History endpoints
# -----------------------------
@profile_bp.route("/history", methods=["POST"])
def add_history():
    """
    POST /api/history
    Body JSON:
    { "email": "...", "action": "...", "meta": {...} }
    """
    db = get_mongo()
    payload = request.get_json(force=True, silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    action = payload.get("action") or "unknown"
    meta = payload.get("meta") or {}

    entry = {
        "email": email,
        "action": action,
        "meta": meta,
        "ts": time.time(),
    }

    if db is not None:
        try:
            db.history.insert_one(entry)
        except Exception as e:
            print("⚠ Mongo error inserting history:", e)
            _in_memory_db["history"].append(entry)
    else:
        _in_memory_db["history"].append(entry)

    return jsonify({"ok": True})


@profile_bp.route("/history", methods=["GET"])
def get_history():
    """
    GET /api/history?email=...

    Returns:
      { "ok": true, "history": [ ... ] }
    """
    db = get_mongo()
    email = (request.args.get("email") or "").strip().lower()

    rows = []
    if db is not None:
        try:
            rows = list(
                db.history.find({"email": email}, {"_id": 0})
                .sort("ts", -1)
                .limit(200)
            )
        except Exception as e:
            print("⚠ Mongo error loading history:", e)
            rows = []
    else:
        rows = [h for h in _in_memory_db["history"] if h.get("email") == email]
        rows = sorted(rows, key=lambda r: r["ts"], reverse=True)

    return jsonify({"ok": True, "history": rows})
