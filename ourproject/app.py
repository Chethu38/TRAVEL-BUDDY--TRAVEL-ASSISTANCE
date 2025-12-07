# app.py — Travel Buddy (app + search + city pages, seeds cities via seed_cities.py)
import os
import random
import logging
import numpy as np
import requests
from datetime import datetime
import math

from flask import (
    Flask, request, jsonify, render_template, redirect, url_for,
    session, abort
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# For robust Mongo id handling
from bson import ObjectId
from bson.errors import InvalidId

# -----------------------------
# Basic Setup
# -----------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-key")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("travel-buddy")

app.jinja_env.globals["app"] = app

# -----------------------------
# Import seeder (cities in separate file)
# -----------------------------
try:
    from seed_cities import seed_cities
    SEED_AVAILABLE = True
except Exception as e:
    log.warning(f"Could not import seed_cities: {e}")
    seed_cities = None
    SEED_AVAILABLE = False

# -----------------------------
# Helper: to_native_number
# -----------------------------
def to_native_number(x):
    try:
        if isinstance(x, (np.generic,)):
            return float(x.item())
        if isinstance(x, np.ndarray):
            return float(x.item()) if x.size == 1 else float(x.flat[0])
        if isinstance(x, (list, tuple)) and x:
            return to_native_number(x[0])
        if hasattr(x, "numpy"):
            return float(x.numpy())
        return float(x)
    except Exception:
        return float(random.randint(20, 95))

# -----------------------------
# Import Models
# -----------------------------
try:
    from crowd_model import get_crowd_prediction
    log.info("crowd_model imported")
    CROWD_MODEL_AVAILABLE = True
except Exception as e:
    log.error(f"crowd_model import failed: {e}")
    CROWD_MODEL_AVAILABLE = False

    def get_crowd_prediction(temp, hum, wind):
        return random.randint(20, 95)

try:
    from trip_model import get_trip_recommendation
    log.info("trip_model imported")
    TRIP_MODEL_AVAILABLE = True
except Exception as e:
    log.error(f"trip_model import failed: {e}")
    TRIP_MODEL_AVAILABLE = False

    def get_trip_recommendation(user_inputs):
        return "<p>Error: Trip suggestion model unavailable.</p>"

# -----------------------------
# Import Blueprints, DB & history helpers
# -----------------------------
ASTAR_REGISTERED = False
PROFILE_REGISTERED = False
AUTH_REGISTERED = False

# A* + cities from astar_routes.py  (KEEP YOUR EXISTING CITY SETUP)
try:
    from astar_routes import astar_bp, MAJOR_CITIES, city_coordinates
    # also import helpers for wrapper route
    try:
        from astar_routes import create_city_graph, a_star, get_coordinates_for_path, full_graph
    except Exception:
        # if those symbols aren't available for some reason, wrapper will fail later with a clear error
        create_city_graph = None
        a_star = None
        get_coordinates_for_path = None
        full_graph = None

    app.register_blueprint(astar_bp, url_prefix="/api")
    ASTAR_REGISTERED = True
    log.info("✅ astar_routes blueprint registered at /api")
except Exception as e:
    log.warning(f"⚠ astar_routes not found: {e}")
    MAJOR_CITIES = []
    city_coordinates = {}
    create_city_graph = None
    a_star = None
    get_coordinates_for_path = None
    full_graph = None

# user_profile blueprint (for /api/profile, /api/history)
try:
    from user_profile import profile_bp
    app.register_blueprint(profile_bp, url_prefix="/api")
    PROFILE_REGISTERED = True
    log.info("user_profile blueprint registered at /api")
except Exception as e:
    log.warning(f"user_profile not found: {e}")

# Auth blueprint + users/history collections + helpers + db
try:
    from auth_routes import (
        auth_bp,
        users_col,
        history_col,
        hash_password,
        verify_password,
        record_activity,
        db as mongo_db,
    )
    app.register_blueprint(auth_bp, url_prefix="/auth")
    AUTH_REGISTERED = True
    log.info("auth_routes blueprint registered under /auth")
except Exception as e:
    log.warning(f"auth_routes not found or incomplete: {e}")
    auth_bp = None
    users_col = None
    history_col = None
    mongo_db = None

    def hash_password(p): return p
    def verify_password(stored, given): return True
    def record_activity(email, action, meta=None):
        print("Activity:", email, action, meta)

# Attach cities & places collections if DB exists (for dynamic city pages)
cities_col = None
places_col = None
if mongo_db is not None:
    try:
        cities_col = mongo_db["cities"]
        places_col = mongo_db["places"]
        log.info("Mongo cities/places collections attached")
    except Exception as e:
        log.warning(f"Could not attach cities/places collections: {e}")
        cities_col = None
        places_col = None

# -----------------------------
# Auto-seed cities (Ballari etc.) ON APP START
# -----------------------------
if SEED_AVAILABLE:
    try:
        seed_cities()
    except Exception as e:
        log.warning(f"Error while seeding cities from seed_cities.py: {e}")

# -----------------------------
# Helper: convert Mongo docs to template-safe dicts
# -----------------------------
def _normalize_images(img_field):
    if not img_field:
        return []
    if isinstance(img_field, list):
        return img_field
    if isinstance(img_field, str):
        # comma-separated fallback
        return [i.strip() for i in img_field.split(",") if i.strip()]
    return list(img_field)

def city_doc_to_dict(doc):
    if not doc:
        return None
    return {
        "id": str(doc.get("_id")),
        "name": doc.get("name"),
        "slug": doc.get("slug") or str(doc.get("_id")),
        "description": doc.get("description"),
        "heroImage": doc.get("heroImage") or "/static/images/city-hero-placeholder.jpg",
        "lat": float(doc["lat"]) if doc.get("lat") is not None else None,
        "lng": float(doc["lng"]) if doc.get("lng") is not None else None,
        # keep original doc for advanced templates if required
        "_raw": doc,
    }

def place_doc_to_dict(doc):
    if not doc:
        return None
    imgs = _normalize_images(doc.get("images") or doc.get("image"))
    return {
        "id": str(doc.get("_id")),
        "type": doc.get("type"),
        "name": doc.get("name"),
        "description": doc.get("description"),
        "address": doc.get("address"),
        "openTime": doc.get("openTime"),
        "closeTime": doc.get("closeTime"),
        "lat": float(doc["lat"]) if doc.get("lat") is not None else None,
        "lng": float(doc["lng"]) if doc.get("lng") is not None else None,
        "phone": doc.get("phone"),
        "website": doc.get("website"),
        "images": imgs,
        "entryFee": doc.get("entryFee"),
        "bestTime": doc.get("bestTime"),
        "category": doc.get("category"),
        "cityId": doc.get("cityId"),
        "city_slug": doc.get("city_slug"),
        "_raw": doc,
    }

# -----------------------------
# ML / Utility endpoints
# -----------------------------
@app.route("/predict_crowd")
@app.route("/predict-crowd")
def predict_crowd_route():
    city = request.args.get("city")
    if not city:
        return jsonify({"error": "City parameter is missing"}), 400

    API_KEY = os.getenv("OPENWEATHER_API_KEY", "9a09529d8cd982b4795c49bf6382d481")
    base_url = "https://api.openweathermap.org/data/2.5/weather"

    try:
        params = {"q": city, "units": "metric"}
        if API_KEY:
            params["appid"] = API_KEY
        r = requests.get(base_url, params=params, timeout=8)
        d = r.json()
        if r.status_code != 200:
            return jsonify({"error": d.get("message", "Weather fetch failed")}), 500

        temp = d["main"]["temp"]
        hum = d["main"]["humidity"]
        wind = d["wind"]["speed"] * 3.6
    except Exception:
        log.exception("Weather fetch failed")
        return jsonify({"error": "Weather fetch failed"}), 500

    try:
        val = get_crowd_prediction(temp, hum, wind)
        crowd = max(0, min(100, to_native_number(val)))
    except Exception:
        crowd = random.randint(20, 95)

    msg = "Crowd is moderate."
    if crowd > 75:
        msg = f"High crowd expected in {city}. Plan accordingly!"
    elif crowd < 40:
        msg = f"Looks clear! {city} should have low crowd."

    email = session.get("user_email")
    if email:
        record_activity(email, "predict_crowd", {
            "city": city,
            "crowd": float(round(crowd, 2))
        })

    return jsonify({"predicted_crowd": round(crowd, 2), "message": msg})


@app.route("/suggest-trip", methods=["POST"])
def suggest_trip():
    data = request.json or {}
    try:
        user_inputs = {
            "Budget_Category": data.get("budget"),
            "Trip_Type": data.get("triptype"),
            "Duration_Days": int(data.get("days") or 5),
            "Group_Size": data.get("group"),
            "Season": data.get("season"),
            "Activity_Preference": data.get("activity"),
        }
        suggestion = get_trip_recommendation(user_inputs)

        email = session.get("user_email")
        if email:
            record_activity(email, "suggest_trip", {"inputs": user_inputs})

        return jsonify({"suggestion": suggestion})
    except Exception as e:
        log.exception("Trip suggestion failed")
        return jsonify({"error": f"Failed: {e}"}), 500

# -----------------------------
# City list & coordinates (A* data)
# -----------------------------
@app.route("/get-locations")
def get_locations():
    try:
        if ASTAR_REGISTERED and MAJOR_CITIES:
            return jsonify(sorted(MAJOR_CITIES))
        if city_coordinates:
            return jsonify(sorted(city_coordinates.keys()))
        return jsonify([])
    except Exception as e:
        log.exception("Error in /get-locations")
        return jsonify([])


@app.route("/get-city-coordinates")
def get_city_coordinates():
    try:
        return jsonify(city_coordinates)
    except Exception as e:
        log.exception("Error in /get-city-coordinates")
        return jsonify({})

# -----------------------------
# Find-route: log city search history
# -----------------------------
# REPLACED: now uses deterministic A* wrapper from astar_routes.py
@app.route("/find-route", methods=["POST"])
def find_route():
    data = request.json or {}
    frm_in = (data.get("from_city") or data.get("from") or "").strip()
    to_in = (data.get("to_city") or data.get("to") or "").strip()

    if not frm_in or not to_in:
        return jsonify({"error": "from_city and to_city required"}), 400

    # If astar helpers are not available, return an informative error
    if create_city_graph is None or a_star is None or get_coordinates_for_path is None or full_graph is None:
        log.error("A* helpers not available. Ensure astar_routes.py exports create_city_graph, a_star, get_coordinates_for_path, full_graph.")
        return jsonify({
            "routes": [],
            "message": "Routing not available on server (A* helpers missing)."
        }), 500

    # Build graph using the same source graph as the astar blueprint
    try:
        city_graph = create_city_graph(full_graph, allowed_cities=None)
    except Exception:
        log.exception("Failed to build city graph for A*")
        return jsonify({"error": "Internal server error building graph"}), 500

    # case-insensitive fallback for input city names
    def match_city(name):
        if name in city_graph:
            return name
        lname = name.lower()
        for k in city_graph.keys():
            if isinstance(k, str) and k.lower() == lname:
                return k
        return None

    frm = match_city(frm_in)
    to = match_city(to_in)

    if not frm or not to:
        return jsonify({
            "routes": [],
            "message": "One or both cities not found on server."
        }), 200

    try:
        dist, path = a_star(city_graph, frm, to)
    except Exception:
        log.exception("A* search failed")
        return jsonify({"error": "Route search failed"}), 500

    if not path:
        return jsonify({
            "routes": [],
            "message": f"No route found between {frm} and {to}."
        }), 200

    coords = get_coordinates_for_path(path)
    time_est = f"{round(float(dist) / 50, 2)} hours" if dist != math.inf else "Unknown"

    route = {
        "path": path,
        "coordinates": coords,
        "distance": round(float(dist), 2),
        "time": time_est,
    }

    email = session.get("user_email")
    if email and history_col is not None:
        try:
            record_activity(email, "search_route", {
                "from": frm,
                "to": to,
                "distance_km": round(float(dist), 2)
            })
        except Exception:
            log.debug("Failed to record search history", exc_info=True)

    return jsonify({"routes": [route]})

# -----------------------------
# MAIN FLOW
# -----------------------------
@app.route("/")
def home():
    if "user_email" not in session:
        return render_template("splash.html")

    email = session.get("user_email")
    display_name = session.get("user_name")

    user_doc = None
    if users_col is not None:
        try:
            user_doc = users_col.find_one({"email": email}, {"password": 0})
        except Exception as e:
            log.warning(f"Mongo user lookup error: {e}")
            user_doc = None

    return render_template(
        "iindex.html",
        user=user_doc,
        user_email=email,
        user_name=display_name,
    )

# -----------------------------
# Login / Signup / Logout
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email or not password:
            return render_template("login.html", error="Missing email or password")

        if users_col is None:
            log.warning("users_col is None – Mongo not connected in login_page")
            return render_template(
                "login.html",
                error="Database not available. Please start MongoDB and restart the app.",
            )

        try:
            user = users_col.find_one({"email": email})
        except Exception as e:
            log.warning(f"Mongo error on login: {e}")
            user = None

        if not user:
            return render_template("login.html", error="Invalid email or password")

        stored = user.get("password") or ""
        ok = False

        try:
            if stored and check_password_hash(stored, password):
                ok = True
        except Exception:
            ok = False

        if not ok and stored == password:
            ok = True
            try:
                new_hashed = generate_password_hash(password)
                users_col.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"password": new_hashed}}
                )
                log.info(f"Auto-migrated plain text password to hash for {email}")
            except Exception as e:
                log.warning(f"Failed to migrate password hash for {email}: {e}")

        if not ok:
            return render_template("login.html", error="Invalid email or password")

        session["user_email"] = email
        session["user_name"] = user.get("name") or email.split("@")[0].capitalize()
        record_activity(email, "login", {"via": "app.login_page"})

        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not name or not email or not password:
            return render_template("signup.html", error="Please provide all fields")

        if users_col is None:
            log.warning("users_col is None – Mongo not connected in signup_page")
            return render_template(
                "signup.html",
                error="Database not available. Please start MongoDB and restart the app.",
            )

        try:
            existing = users_col.find_one({"email": email})
        except Exception as e:
            log.warning(f"Mongo error on signup check: {e}")
            existing = None

        if existing:
            return render_template("signup.html", error="Email already registered. Try logging in.")

        hashed = generate_password_hash(password)
        doc = {
            "name": name,
            "email": email,
            "password": hashed,
            "created_at": datetime.utcnow(),
        }
        try:
            users_col.insert_one(doc)
        except Exception as e:
            log.warning(f"Mongo error inserting user: {e}")
            return render_template("signup.html", error="Internal error while creating user.")

        session["user_email"] = email
        session["user_name"] = name
        record_activity(email, "signup", {"via": "app.signup_page"})

        return redirect(url_for("home"))

    return render_template("signup.html")

# -----------------------------
# Forgot Password
# -----------------------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        new_pw = request.form.get("password") or ""
        confirm_pw = request.form.get("password_confirm") or ""

        if not email or not new_pw or not confirm_pw:
            return render_template("forgot_password.html", error="Please fill all fields")

        if new_pw != confirm_pw:
            return render_template("forgot_password.html", error="Passwords do not match")

        if len(new_pw) < 6:
            return render_template("forgot_password.html", error="Password must be at least 6 characters")

        if users_col is None:
            return render_template("forgot_password.html", error="User database not available")

        try:
            user = users_col.find_one({"email": email})
        except Exception as e:
            log.warning(f"Mongo error finding user for reset: {e}")
            user = None

        if not user:
            return render_template("forgot_password.html", error="No account found with that email")

        try:
            hashed = generate_password_hash(new_pw)
            users_col.update_one({"email": email}, {"$set": {"password": hashed}})
            record_activity(email, "password_reset", {"via": "forgot_password"})
        except Exception as e:
            log.warning(f"Mongo error updating password: {e}")
            return render_template("forgot_password.html", error="Could not update password. Try again.")

        return render_template("forgot_password.html", success="Password updated successfully. You can now log in.")
    else:
        return render_template("forgot_password.html")


@app.route("/logout")
def logout():
    email = session.get("user_email")
    if email:
        record_activity(email, "logout", {"via": "app.logout"})
    session.clear()
    return redirect(url_for("login_page"))

# -----------------------------
# History page
# -----------------------------
@app.route("/history")
def history_page():
    if "user_email" not in session:
        return redirect(url_for("login_page"))

    email = session.get("user_email")
    history_rows = []
    if history_col is not None:
        try:
            cur = history_col.find(
                {"email": email, "action": "search_route"}
            ).sort("ts", -1)
            history_rows = list(cur)
        except Exception as e:
            log.warning(f"Mongo history lookup error (history page): {e}")
            history_rows = []

    return render_template("history.html", email=email, history=history_rows)

# -----------------------------
# Profile page
# -----------------------------
@app.route("/profile")
def profile_page():
    if "user_email" not in session:
        return redirect(url_for("login_page"))

    email = session.get("user_email")
    display_name = session.get("user_name")

    user_doc = None
    if users_col is not None:
        try:
            user_doc = users_col.find_one({"email": email}, {"password": 0})
        except Exception as e:
            log.warning(f"Mongo user lookup error (profile): {e}")
            user_doc = None

    search_history = []
    if history_col is not None:
        try:
            cur = history_col.find(
                {"email": email, "action": "search_route"}
            ).sort("ts", -1)
            search_history = list(cur)
        except Exception as e:
            log.warning(f"Mongo history lookup error (profile): {e}")
            search_history = []

    return render_template(
        "profile.html",
        user=user_doc,
        user_email=email,
        user_name=display_name,
        search_history=search_history,
    )

# -----------------------------
# Settings page
# -----------------------------
@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    if "user_email" not in session:
        return redirect(url_for("login_page"))

    email = session.get("user_email")
    user_doc = None

    if users_col is not None:
        try:
            user_doc = users_col.find_one({"email": email})
        except Exception as e:
            log.warning(f"Mongo user lookup error (settings): {e}")
            user_doc = None

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        bio = (request.form.get("bio") or "").strip()
        theme = (request.form.get("theme") or "light").strip()

        if users_col is not None:
            update_fields = {
                "bio": bio,
                "theme": theme,
            }
            if name:
                update_fields["name"] = name

            try:
                users_col.update_one(
                    {"email": email},
                    {"$set": update_fields},
                    upsert=True
                )
            except Exception as e:
                log.warning(f"Mongo user update error (settings): {e}")

        if name:
            session["user_name"] = name

        if users_col is not None:
            try:
                user_doc = users_col.find_one({"email": email})
            except Exception as e:
                log.warning(f"Mongo user reload error (settings): {e}")

        return render_template("settings.html", user=user_doc, saved=True)

    return render_template("settings.html", user=user_doc, saved=False)

# -----------------------------
# City detail page (DB-based)
# -----------------------------
@app.route("/city/<slug>")
def city_page(slug):
    """
    Robust city lookup:
    - Try to find by slug field if present
    - Try to find by _id as ObjectId
    - Try to find by _id as string (many seeds use string _id equal to slug)
    After finding the city, query places for that city using common fields:
    - places where cityId matches the city's stored id
    - OR where city_slug matches the city's slug field
    - OR where city_slug matches the requested slug
    """
    if "user_email" not in session:
        return redirect(url_for("login_page"))

    if cities_col is None or places_col is None:
        return "City database not available (cities/places collection missing)", 500

    city = None

    # 1) try slug field
    try:
        city = cities_col.find_one({"slug": slug})
    except Exception:
        city = None

    # 2) try by _id (ObjectId)
    if not city:
        try:
            city = cities_col.find_one({"_id": ObjectId(slug)})
        except (InvalidId, Exception):
            city = None

    # 3) try by _id as string (some seeds make _id a plain string slug)
    if not city:
        try:
            city = cities_col.find_one({"_id": slug})
        except Exception:
            city = None

    if not city:
        return render_template("404.html"), 404

    # Build place query to cover common possibilities
    city_id_value = city.get("_id")
    city_slug_value = city.get("slug") or str(city_id_value)

    place_query = {
        "$or": [
            {"cityId": city_id_value},
            {"cityId": str(city_id_value)},
            {"city_slug": city_slug_value},
            {"city_slug": slug},
        ]
    }

    try:
        places_cursor = places_col.find(place_query)
        places = list(places_cursor)
    except Exception as e:
        log.warning(f"Mongo places lookup error: {e}")
        places = []

    # Convert docs for template safety (avoid ObjectId in templates)
    city_t = city_doc_to_dict(city)
    places_t = [place_doc_to_dict(p) for p in places]

    return render_template("city.html", city=city_t, places=places_t)

# -----------------------------
# Search page
# -----------------------------
@app.route("/search")
def search_page():
    if "user_email" not in session:
        return redirect(url_for("login_page"))
    return render_template("search.html")

# -----------------------------
# AI planner
# -----------------------------
@app.route("/ai-planner")
def ai_planner():
    if "user_email" not in session:
        return redirect(url_for("login_page"))
    return render_template("ai_planner.html")

# -----------------------------
# Place detail page (view)
# -----------------------------
@app.route("/view/<place_id>")
@app.route("/view/<place_type>/<place_id>")
def view_place(place_type=None, place_id=None):
    """
    Shows full details for a place.
    Accepts:
      /view/<place_id>
      /view/<place_type>/<place_id>

    Lookup tries:
      - _id as ObjectId
      - _id as string
    Optionally restrict by place_type if provided.
    """
    if "user_email" not in session:
        return redirect(url_for("login_page"))

    if places_col is None:
        return "Places database not available", 500

    # Build query
    query = None
    try:
        query = {"_id": ObjectId(place_id)}
    except (InvalidId, Exception):
        query = {"_id": place_id}

    if place_type:
        query["type"] = place_type

    try:
        doc = places_col.find_one(query)
    except Exception as e:
        log.warning(f"Mongo lookup error in view_place: {e}")
        doc = None

    if not doc:
        return render_template("404.html"), 404

    place_t = place_doc_to_dict(doc)

    # If doc lacks city info, attempt to enrich with city slug if possible
    # NOTE: avoid truth-testing the collection object — compare to None
    if (not place_t.get("city_slug")) and place_t.get("cityId") and (cities_col is not None):
        try:
            # cityId in place_t may be stored as ObjectId or string, try both
            city_query = None
            try:
                city_query = {"_id": ObjectId(place_t.get("cityId"))}
            except Exception:
                city_query = {"_id": place_t.get("cityId")}

            c = cities_col.find_one(city_query)
            if c:
                place_t["city_slug"] = c.get("slug") or str(c.get("_id"))
        except Exception:
            # swallowing errors is intentional — enrichment is optional
            log.debug("Could not enrich place with city slug", exc_info=True)

    return render_template("view.html", place=place_t)

# -----------------------------
# Dynamic template route
# -----------------------------
@app.route("/<path:page>", methods=["GET", "HEAD"])
def serve_dynamic_page(page):
    name = page.rsplit("/", 1)[-1].lower()
    known = {
        "",
        "search",
        "ai-planner",
        "profile",
        "login",
        "signup",
        "settings",
        "logout",
        "forgot-password",
        "history",
        "predict_crowd",
        "predict-crowd",
        "suggest-trip",
        "get-locations",
        "get-city-coordinates",
        "find-route",
        "health",
        "city",
    }
    if name in known:
        return abort(404)

    tmpl_dir = app.template_folder or "templates"
    candidate = os.path.join(tmpl_dir, f"{name}.html")
    if os.path.exists(candidate):
        return render_template(f"{name}.html")

    return abort(404)

# -----------------------------
# Health check
# -----------------------------
@app.route("/health")
def health():
    return jsonify({"status": "ok", "message": "Travel Buddy is running fine"})

# -----------------------------
# Main entry
# -----------------------------
if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base)
    log.info(f"Working dir: {base}")
    log.info(f"Templates dir: {app.template_folder}")
    log.info("Starting Flask server at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
