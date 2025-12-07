# astar_routes.py
import heapq
import math
from flask import Blueprint, request, jsonify

astar_bp = Blueprint("astar_bp", __name__)

# --------------------------
# COPY OF YOUR A* DATA
# --------------------------
full_graph = {
    "Ballari": {
        "Kudatini": 20, "Daroji": 35, "Toranagallu": 30, "Emmiganur": 30,
        "Siruguppa": 55, "Royal Circle": 3, "Ballari Railway Station": 4,
        "Chitradurga": 137, "Sandur": 53, "Hospet": 60
    },
    "Hospet": {
        "Kudatini": 40, "Sandur": 30, "Gangavathi Junction": 15, "Toranagallu": 30,
        "Kampli": 35, "Koppal": 38, "Hospet Bus Stand": 2, "Tungabhadra Dam": 6,
        "Hampi": 13, "Kamalapura": 8
    },
    "Sandur": {
        "Daroji": 20, "Hospet": 30, "Toranagallu": 28, "Sandur Bus Stand": 1,
        "Donimalai": 10, "Ballari": 53
    },
    "Koppal": {
        "Gangavathi Junction": 20, "Hospet": 38, "Koppal Railway Station": 3,
        "Koppal Fort": 4, "Gadag": 61, "Hampi": 44
    },
    "Toranagallu": {
        "Ballari": 30, "Hospet": 30, "Sandur": 28, "Daroji": 22,
        "Jindal Vidyanagar Airport": 5
    },
    "Kampli": {
        "Emmiganur": 25, "Hospet": 35, "Gangavathi Junction": 35,
        "Siruguppa": 35, "Hampi": 15
    },
    "Kudatini": {"Ballari": 20, "Hospet": 40},
    "Daroji": {
        "Ballari": 35, "Sandur": 20, "Toranagallu": 22,
        "Daroji Bear Sanctuary": 16
    },
    "Emmiganur": {"Ballari": 30, "Kampli": 25},
    "Gangavathi Junction": {
        "Hospet": 15, "Koppal": 20, "Kampli": 35, "Anegundi": 14, "Raichur": 138
    },
    "Siruguppa": {"Ballari": 55, "Kampli": 35, "Adoni": 43},
    "Ballari Fort": {"Ballari Railway Station": 4, "Gadigi Palace": 2.5, "Royal Circle": 3},
    "Ballari Railway Station": {"Ballari Fort": 4, "New Bus Stand": 3, "Ballari": 4, "Royal Circle": 0.8},
    "New Bus Stand": {"Ballari Railway Station": 3, "Gadigi Palace": 5, "Royal Circle": 2},
    "Gadigi Palace": {"New Bus Stand": 5, "Ballari Fort": 2.5},
    "Royal Circle": {"Ballari Fort": 3, "New Bus Stand": 2, "Ballari": 3, "Ballari Railway Station": 0.8},
    "Hospet Railway Station": {"Hospet Bus Stand": 1, "Hospet": 2},
    "Hospet Bus Stand": {"Hospet Railway Station": 1, "Tungabhadra Dam": 5, "Hospet": 2, "Hampi": 12},
    "Tungabhadra Dam": {"Hospet Bus Stand": 5, "Hospet": 6},
    "Sandur Bus Stand": {"Kumaraswamy Temple": 12, "Narihalla Dam": 8, "Sandur": 1},
    "Kumaraswamy Temple": {"Sandur Bus Stand": 12, "Narihalla Dam": 8},
    "Narihalla Dam": {"Sandur Bus Stand": 8, "Kumaraswamy Temple": 8},
    "Koppal Railway Station": {"Koppal Bus Stand": 2, "Koppal": 3},
    "Koppal Bus Stand": {"Koppal Railway Station": 2, "Koppal Fort": 4, "Koppal": 3},
    "Koppal Fort": {"Koppal Bus Stand": 4, "Koppal": 4},
    "Hampi": {"Hospet": 13, "Kamalapura": 5, "Virupaksha Temple": 0.5, "Vijaya Vittala Temple": 2, "Gangavathi Junction": 22, "Anegundi": 20},
    "Kamalapura": {"Hospet": 8, "Hampi": 5, "Ballari": 60},
    "Virupaksha Temple": {"Hampi": 0.5, "Hospet": 13},
    "Vijaya Vittala Temple": {"Hampi": 2, "Kamalapura": 6},
    "Daroji Bear Sanctuary": {"Daroji": 16, "Hospet": 25, "Ballari": 40},
    "Anegundi": {"Gangavathi Junction": 14, "Hampi": 20},
    "Chitradurga": {"Ballari": 137},
    "Gadag": {"Koppal": 61},
    "Adoni": {"Siruguppa": 43},
    "Raichur": {"Gangavathi Junction": 138},
    "Donimalai": {"Sandur": 10},
    "Jindal Vidyanagar Airport": {"Toranagallu": 5, "Ballari": 35, "Hospet": 30}
}

MAJOR_CITIES = [
    "Ballari", "Hospet", "Sandur", "Koppal", "Toranagallu", "Kampli",
    "Kudatini", "Daroji", "Emmiganur", "Gangavathi Junction", "Siruguppa",
    "Hampi", "Kamalapura", "Anegundi", "Chitradurga", "Gadag", "Adoni",
    "Raichur", "Donimalai"
]

city_coordinates = {
    "Ballari": [15.1394, 76.9214], "Hospet": [15.2663, 76.3862], "Sandur": [15.0833, 76.5500],
    "Koppal": [15.3470, 76.1554], "Toranagallu": [15.1764, 76.6433], "Kampli": [15.4056, 76.6123],
    "Kudatini": [15.1950, 76.7836], "Daroji": [15.2573, 76.6578], "Emmiganur": [15.7333, 77.4833],
    "Gangavathi Junction": [15.4319, 76.5292], "Siruguppa": [15.6358, 76.9038], "Hampi": [15.3350, 76.4600],
    "Kamalapura": [15.3036, 76.4850], "Anegundi": [15.3534, 76.4815], "Chitradurga": [14.2250, 76.3983],
    "Gadag": [15.4299, 75.6300], "Adoni": [15.6310, 77.2764], "Raichur": [16.2076, 77.3463],
    "Donimalai": [15.0500, 76.5833]
}

# --------------------------
# GRAPH UTILITIES (A*)
# --------------------------
from math import radians, sin, cos, sqrt, asin

def haversine_distance(city1, city2):
    """
    Returns approximate great-circle distance in kilometers between two cities
    using the city_coordinates map. If either city is missing, return a
    conservative large heuristic (so A* still functions).
    """
    if city1 not in city_coordinates or city2 not in city_coordinates:
        # return a large admissible value so heuristic doesn't overestimate real edge costs
        return 1e6
    lat1, lon1 = city_coordinates[city1]
    lat2, lon2 = city_coordinates[city2]
    R = 6371.0
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    lat1r = radians(lat1)
    lat2r = radians(lat2)
    a = sin(dLat / 2)**2 + cos(lat1r) * cos(lat2r) * sin(dLon / 2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def create_city_graph(original_graph, allowed_cities=None):
    """
    Build a graph dict from original_graph. If allowed_cities is provided,
    we include nodes present in allowed_cities plus any neighbors that connect to them.
    To be robust, if allowed_cities is falsy we include all nodes in original_graph.
    """
    if allowed_cities:
        allowed_set = set(allowed_cities)
    else:
        allowed_set = set(original_graph.keys())

    city_graph = {}
    # include nodes from allowed_set and ensure neighbors that exist in original_graph are kept
    for city in list(original_graph.keys()):
        if city not in allowed_set and city not in original_graph:
            continue
        connections = original_graph.get(city, {})
        # keep neighbors that are in original_graph (so edges are well-defined)
        filtered = {}
        for neighbor, distance in connections.items():
            if neighbor in original_graph:
                try:
                    filtered[neighbor] = float(distance)
                except Exception:
                    # skip malformed distances
                    continue
        if filtered:
            city_graph[city] = filtered

    # also ensure that every neighbor included has an entry (even if empty) to avoid KeyError
    for city in list(city_graph.keys()):
        for neigh in list(city_graph[city].keys()):
            if neigh not in city_graph:
                city_graph.setdefault(neigh, {})
    return city_graph

def a_star(graph, source, target):
    """
    A* search with deterministic tie-breaking.
    Returns (distance, path) where distance is sum of edge weights (float) and path is list of nodes.
    If no path found, returns (math.inf, None).
    """
    if source not in graph or target not in graph:
        return math.inf, None

    # g = cost so far, f = g + h
    g_score = {node: math.inf for node in graph}; g_score[source] = 0.0
    f_score = {node: math.inf for node in graph}; f_score[source] = haversine_distance(source, target)

    # priority queue entries: (f_score, g_score, counter, node)
    # counter ensures deterministic ordering even when f & g equal
    pq = []
    counter = 0
    heapq.heappush(pq, (f_score[source], g_score[source], counter, source))
    came_from = {}

    while pq:
        current_f, current_g, _, u = heapq.heappop(pq)
        # stale queue item check
        if current_f > f_score.get(u, math.inf) or current_g > g_score.get(u, math.inf):
            continue

        if u == target:
            # reconstruct path
            path = []
            cur = target
            while cur != source:
                path.append(cur)
                cur = came_from.get(cur)
                if cur is None:
                    return math.inf, None
            path.append(source)
            path.reverse()
            return g_score[target], path

        for v, w in graph.get(u, {}).items():
            try:
                weight = float(w)
            except Exception:
                continue
            tentative_g = g_score[u] + weight
            if tentative_g < g_score.get(v, math.inf):
                came_from[v] = u
                g_score[v] = tentative_g
                h = haversine_distance(v, target)
                f = tentative_g + h
                f_score[v] = f
                counter += 1
                heapq.heappush(pq, (f, tentative_g, counter, v))

    return math.inf, None

def get_coordinates_for_path(path):
    coords = []
    for city in path:
        if city in city_coordinates:
            coords.append(city_coordinates[city])
        else:
            # if coordinates missing, append None to keep indices aligned
            coords.append(None)
    return coords

# --------------------------
# BLUEPRINT ENDPOINTS
# --------------------------
@astar_bp.route('/get-locations', methods=['GET'])
def get_locations():
    # return union of MAJOR_CITIES and keys discovered in full_graph for completeness
    all_cities = sorted(set(MAJOR_CITIES) | set(full_graph.keys()))
    return jsonify(all_cities)

@astar_bp.route('/get-city-coordinates', methods=['GET'])
def get_city_coordinates():
    return jsonify(city_coordinates)

@astar_bp.route('/find-route', methods=['POST'])
def find_route():
    data = request.json or {}
    from_city = data.get('from_city') or data.get('from') or data.get('frm')
    to_city = data.get('to_city') or data.get('to') or data.get('to_city_name')

    if not from_city or not to_city:
        return jsonify({"error": "Missing 'from_city' or 'to_city' in request body"}), 400

    # simple normalization: strip surrounding whitespace
    if isinstance(from_city, str):
        from_city = from_city.strip()
    if isinstance(to_city, str):
        to_city = to_city.strip()

    # Build graph including all nodes present in full_graph (robust)
    city_graph = create_city_graph(full_graph, allowed_cities=None)

    # case-insensitive matching fallback (to be forgiving with input)
    if from_city not in city_graph:
        for k in city_graph.keys():
            if isinstance(k, str) and k.lower() == from_city.lower():
                from_city = k
                break
    if to_city not in city_graph:
        for k in city_graph.keys():
            if isinstance(k, str) and k.lower() == to_city.lower():
                to_city = k
                break

    if from_city not in city_graph:
        return jsonify({"error": f"From-city '{from_city}' not found on server"}), 404
    if to_city not in city_graph:
        return jsonify({"error": f"To-city '{to_city}' not found on server"}), 404

    dist, path = a_star(city_graph, from_city, to_city)
    if not path:
        return jsonify({"error": f"No route found between {from_city} and {to_city}"}), 404

    coords = get_coordinates_for_path(path)
    routes = [{
        "id": "r1",
        "path": path,
        "coordinates": coords,
        "distance": round(float(dist), 2),
        "time": f"{round(float(dist) / 50, 2)} hours",
        "traffic": "Unknown"
    }]
    response = {"from_city_name": from_city, "to_city_name": to_city, "routes": routes}
    return jsonify(response)
