# auth_routes.py
from flask import (
    Blueprint, request, render_template,
    redirect, url_for, session
)
import os
import subprocess
import time
from datetime import datetime

# --- Mongo ---
try:
    from pymongo import MongoClient
    MONGO_AVAILABLE = True
except Exception:
    MongoClient = None
    MONGO_AVAILABLE = False

# --- Bcrypt (optional, for old hashes) ---
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except Exception:
    bcrypt = None
    BCRYPT_AVAILABLE = False

# --- Werkzeug password hashing (main) ---
try:
    from werkzeug.security import generate_password_hash, check_password_hash
    WERKZEUG_AVAILABLE = True
except Exception:
    generate_password_hash = None
    check_password_hash = None
    WERKZEUG_AVAILABLE = False

auth_bp = Blueprint("auth_bp", __name__)

# ----------------------
# Helper: auto-start MongoDB
# ----------------------
def auto_start_mongo():
    """
    Try to start `mongod` as a background process.
    Requires mongod to be installed and available in PATH.
    """
    try:
        subprocess.Popen(
            ["mongod"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        print("🟢 Attempted to auto-start mongod from auth_routes.py")
    except Exception as e:
        print("⚠ Failed to auto-start mongod:", e)


def connect_mongo(uri: str):
    """
    Connect to Mongo, return (client, db) or raise.
    Avoids using truthiness on db.
    """
    client = MongoClient(uri, serverSelectionTimeoutMS=2000)
    db = client.get_default_database()
    if db is None:
        db = client["travelbuddy"]
    # force connection
    client.admin.command("ping")
    return client, db


# ----------------------
# Mongo connection
# ----------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/travelbuddy")
client = None
db = None
users_col = None
history_col = None

if MONGO_AVAILABLE:
    # first try
    try:
        client, db = connect_mongo(MONGO_URI)
        users_col = db["users"]
        history_col = db["history"]
        print("✅ Mongo connected in auth_routes (first try):", MONGO_URI)
    except Exception as e:
        print("⚠ Mongo connection failed in auth_routes (first try):", e)
        print("🔄 Trying to auto-start MongoDB (mongod)...")
        auto_start_mongo()
        # second try
        try:
            client, db = connect_mongo(MONGO_URI)
            users_col = db["users"]
            history_col = db["history"]
            print("✅ Mongo connected in auth_routes after auto-start")
        except Exception as e2:
            print("❌ Still cannot connect to Mongo after auto-start:", e2)
            client = None
            db = None
            users_col = None
            history_col = None
else:
    print("⚠ pymongo not available; using in-memory placeholders.")
    db = None


# ----------------------
# Password helpers
# ----------------------
def hash_password(password: str) -> str:
    """
    Hash password for storage.

    Priority:
      1. Werkzeug generate_password_hash (preferred)
      2. bcrypt (if available)
      3. "plain$..." fallback in dev
    """
    if not password:
        return ""

    # 1) preferred: werkzeug
    if WERKZEUG_AVAILABLE and generate_password_hash is not None:
        try:
            return generate_password_hash(password)
        except Exception as e:
            print("⚠ generate_password_hash error:", e)

    # 2) fallback: bcrypt
    if BCRYPT_AVAILABLE:
        try:
            hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
            # bcrypt v4.0.0+ returns str, older versions return bytes
            if isinstance(hashed, bytes):
                return hashed.decode("utf-8")
            return hashed
        except Exception as e:
            print("⚠ bcrypt.hashpw error:", e)

    # 3) last dev fallback: plain$
    return "plain$" + password


def verify_password(stored: str, provided: str) -> bool:
    """
    Verify password the safest way we can.

    Accepts:
      - Werkzeug hashes
      - bcrypt hashes
      - 'plain$' dev format
      - raw plain-text (for older data) as LAST fallback
    """
    if stored is None or provided is None:
        return False

    stored = str(stored)

    # 1) Dev fallback stored as plain$pass
    if stored.startswith("plain$"):
        return stored == "plain$" + provided

    # 2) Werkzeug hash (preferred)
    if WERKZEUG_AVAILABLE and check_password_hash is not None:
        try:
            if check_password_hash(stored, provided):
                return True
        except Exception:
            # If stored is not recognisable by werkzeug, ignore and continue
            pass

    # 3) bcrypt hash (legacy)
    if BCRYPT_AVAILABLE:
        try:
            # Handle both str and bytes for stored hash
            stored_bytes = stored.encode("utf-8") if isinstance(stored, str) else stored
            provided_bytes = provided.encode("utf-8") if isinstance(provided, str) else provided
            if bcrypt.checkpw(provided_bytes, stored_bytes):
                return True
        except Exception:
            pass

    # 4) Last fallback: plain text match (for very old DB where password==provided)
    if stored == provided:
        return True

    return False


# ----------------------
# Activity history
# ----------------------
def record_activity(email, action, meta=None):
    """
    Insert simple activity rows into history collection.
    ts is stored as ISO string so templates can show it directly.
    """
    if not email or history_col is None:
        return
    try:
        history_col.insert_one({
            "email": email,
            "action": action,
            "meta": meta or {},
            "ts": datetime.utcnow().isoformat()
        })
    except Exception as e:
        print("Warning: failed to write history:", e)


# ----------------------
# /auth routes (optional)
# ----------------------
@auth_bp.route("/signup", methods=["GET", "POST"])
def auth_signup():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not name or not email or not password:
            return render_template("signup.html", error="Please provide all fields")

        if users_col is not None:
            try:
                existing = users_col.find_one({"email": email})
            except Exception as e:
                print("⚠ Mongo error on auth_signup check:", e)
                existing = None

            if existing:
                return render_template("signup.html", error="Email already registered. Try logging in.")

            hashed = hash_password(password)
            doc = {
                "name": name,
                "email": email,
                "password": hashed,
                "created_at": datetime.utcnow(),
            }
            try:
                users_col.insert_one(doc)
            except Exception as e:
                print("⚠ Mongo error inserting user in auth_signup:", e)
                return render_template("signup.html", error="Internal error while creating user.")

        # set session
        session["user_email"] = email
        session["user_name"] = name
        record_activity(email, "signup", {"via": "auth_bp.signup"})
        return redirect(url_for("home"))

    return render_template("signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def auth_login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email or not password:
            return render_template("login.html", error="Missing email or password")

        user = None
        if users_col is not None:
            try:
                user = users_col.find_one({"email": email})
            except Exception as e:
                print("⚠ Mongo error on auth_login:", e)
                user = None

        if not user:
            return render_template("login.html", error="Invalid email or password")

        stored = user.get("password") or ""

        # ---- Password check with auto-migration for old plain text ----
        ok = False

        # 1) Try normal verify helper
        if verify_password(stored, password):
            ok = True
        # 2) If stored is raw plain text and matches, migrate to hash
        elif stored == password and WERKZEUG_AVAILABLE and generate_password_hash is not None:
            ok = True
            try:
                new_hashed = generate_password_hash(password)
                users_col.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"password": new_hashed}}
                )
                print(f"✅ Auto-migrated plain-text password to hash for {email} (auth_login)")
            except Exception as e:
                print(f"⚠ Failed to migrate password hash for {email} in auth_login:", e)

        if not ok:
            return render_template("login.html", error="Invalid email or password")

        session["user_email"] = email
        session["user_name"] = user.get("name") or email.split("@")[0].capitalize()
        record_activity(email, "login", {"via": "auth_bp.login"})
        return redirect(url_for("home"))

    return render_template("login.html")


@auth_bp.route("/logout")
def auth_logout():
    email = session.get("user_email")
    if email:
        record_activity(email, "logout", {"via": "auth_bp.logout"})
    session.clear()
    return redirect(url_for("login_page"))
