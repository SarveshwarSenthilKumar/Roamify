from flask import Flask, render_template, request, session
from flask_session import Session
import google.generativeai as genai
from geopy.geocoders import Nominatim
import requests
import os
import time
from dotenv import load_dotenv
from functools import lru_cache
import concurrent.futures

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={
        "max_output_tokens": 2048,
        "temperature": 0.5
    }
)

# Initialize Flask app
app = Flask(__name__)
app.config.update({
    "SESSION_PERMANENT": True,
    "SESSION_TYPE": "filesystem",
    "TEMPLATES_AUTO_RELOAD": True,
})
Session(app)

# App-wide configuration
autoRun = True
port = 5000
authentication = True

# Load types once
PLACE_TYPES_MAP = {}
REVERSE_PLACE_TYPES = {}

with open('types.txt', 'r') as file:
    for line in file:
        parts = line.strip().split(",", 1)
        if len(parts) == 2:
            k, v = parts
            PLACE_TYPES_MAP[k] = v
            REVERSE_PLACE_TYPES[v] = k

# Register authentication if enabled
if authentication:
    from auth import auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

# Geolocator instance
geolocator = Nominatim(user_agent="roamify-app", timeout=10)

# Improved Gemini chat with retries and backoff
@lru_cache(maxsize=128)
def chat_with_gemini(prompt):
    max_retries = 3
    base_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt, request_options={"timeout": 120})
            return response.text.strip()
        except Exception as e:
            print(f"Gemini error (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return "Our trip planning service is currently experiencing high demand. Please try again later."
            
            # Exponential backoff
            delay = base_delay * (2 ** attempt)
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)
    
    return "Unable to generate trip plan at this time."

# Cached geocoding
@lru_cache(maxsize=128)
def get_coordinates(address):
    try:
        location = geolocator.geocode(address)
        return (location.latitude, location.longitude) if location else None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None

def get_ip_location():
    try:
        response = requests.get('https://ipinfo.io/json', timeout=3)
        location = response.json()['loc'].split(',')
        return float(location[0]), float(location[1])
    except Exception as e:
        print(f"IP location error: {e}")
        return (37.7749, -122.4194)  # Default to San Francisco coordinates

def get_food_places_nearby(lat, lng, radius=1000):
    try:
        url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&type=restaurant&key={API_KEY}'
        response = requests.get(url, timeout=5)
        places = response.json()
        return places.get('results', [])[:5] if places.get('status') == 'OK' else []
    except Exception as e:
        print(f"Food places error: {e}")
        return []

def get_place_image_url(place_id):
    try:
        url = f"https://maps.googleapis.com/maps/api/place/details/json?placeid={place_id}&key={API_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        photos = data.get("result", {}).get("photos", [])
        if photos:
            ref = photos[0]["photo_reference"]
            return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={ref}&key={API_KEY}"
    except Exception as e:
        print(f"Image URL error: {e}")
    return None

def create_trip_plan(destination, activity, keyword=""):
    prompt = (
        f"Do not make the answer in markdown format. Not in .md format, do not add asterisks. "
        f"Just have regular sentences. Create a personalized trip plan to {activity} at {destination} for 1 day "
        f"{f'catered to {keyword}' if keyword else ''}. Include outdoor activities and food places. "
        "Include the name of the place, address, and a brief description of each activity. "
        "Make sure to include at least 2 outdoor activities and 2 food places. "
        "Do not include any other information."
    )
    return chat_with_gemini(prompt)

def fetch_places_parallel(urls):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(requests.get, url, timeout=5) for url in urls]
        results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result().json())
            except Exception as e:
                print(f"Request error: {e}")
                results.append({'status': 'ERROR'})
        return results

def process_activity(activity, keyword, radius):
    location = activity['geometry']['location']
    types = activity.get('types', ['N/A'])
    return_dict = {
        'name': activity['name'],
        'vicinity': activity.get('vicinity', 'N/A'),
        'latitude': location['lat'],
        'longitude': location['lng'],
        'place_id': activity['place_id'],
        'price_level': activity.get('price_level', 'N/A'),
        'rating': activity.get('rating', 'N/A'),
        'number_of_ratings': activity.get('user_ratings_total', 'N/A'),
        'types': REVERSE_PLACE_TYPES.get(types[0], 'Unknown Type')
    }

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_food = executor.submit(get_food_places_nearby, return_dict['latitude'], return_dict['longitude'], radius)
        future_image = executor.submit(get_place_image_url, return_dict['place_id'])
        future_plan = executor.submit(create_trip_plan, return_dict['vicinity'], return_dict['name'], keyword)
        return_dict.update({
            'food_places_nearby': future_food.result(),
            'image_url': future_image.result(),
            'trip_plan': future_plan.result()
        })

    return return_dict

def get_outdoor_activities(lat, lng, radius=1000, keyword="", outdoor_types=None):
    urls = [
        f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&type={ptype}&key={API_KEY}'
        for ptype in outdoor_types
    ]
    places_results = fetch_places_parallel(urls)
    activities = []
    seen = set()

    for places in places_results:
        if places.get('status') == 'OK':
            for result in places['results'][:2]:
                uid = (result['name'], result['geometry']['location']['lat'], result['geometry']['location']['lng'])
                if uid not in seen:
                    seen.add(uid)
                    activities.append(process_activity(result, keyword, radius))
    return activities

@app.route("/", methods=["GET", "POST"])
def index():
    if not authentication:
        return render_template("index.html")
    
    if not session.get("name"):
        return render_template("index.html", authentication=True)

    try:
        lat, lng = get_ip_location()
        keyword = request.args.get("keywords", "")
        selected_types = request.args.getlist("place_types")
        radius = request.args.get("radius", default=1, type=int) * 1000  # Convert km to meters

        # Resolve types
        outdoor_types = [PLACE_TYPES_MAP.get(t) for t in selected_types if PLACE_TYPES_MAP.get(t)]
        if not outdoor_types:
            outdoor_types = ['park', 'stadium', 'tourist_attraction', 'gym', 'hiking']

        if address := request.args.get("address"):
            if coordinates := get_coordinates(address):
                lat, lng = coordinates

        suggestions = get_outdoor_activities(lat, lng, radius, keyword, outdoor_types)
        return render_template("/auth/loggedIn.html", 
                             suggestions=suggestions, 
                             place_types=list(PLACE_TYPES_MAP.keys()),
                             radius=radius//1000)  # Convert back to km for display
    
    except Exception as e:
        print(f"Route error: {e}")
        return render_template("/auth/loggedIn.html", 
                             error="Our service is currently experiencing high demand. Please try again later.",
                             place_types=list(PLACE_TYPES_MAP.keys()))

if __name__ == '__main__' and autoRun:
    app.run(debug=True, port=port)