from flask import Flask, render_template, request, session
from flask_session import Session
import google.generativeai as genai
from geopy.geocoders import Nominatim
import requests
import os
from dotenv import load_dotenv
from functools import lru_cache
import concurrent.futures

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-lite")  # Initialize once

# Initialize Flask app
app = Flask(__name__)
app.config.update({
    "SESSION_PERMANENT": True,
    "SESSION_TYPE": "filesystem",
    "TEMPLATES_AUTO_RELOAD": True
})
Session(app)

# Configuration
autoRun = True
port = 5000
authentication = True

if authentication:
    from auth import auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

# Initialize geolocator with timeout
geolocator = Nominatim(user_agent="roamify-app", timeout=10)

# Cached functions
@lru_cache(maxsize=128)
def chat_with_gemini(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return "Unable to generate trip plan at this time."

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
        data = response.json()
        location = data['loc'].split(',')
        return float(location[0]), float(location[1])
    except Exception as e:
        print(f"IP location error: {e}")
        return (37.7749, -122.4194)  # Default fallback
    
def get_food_places_nearby(lat, lng, radius=1000):
    """Fetch nearby food places - now defined before being called"""
    try:
        food_places_url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&type=restaurant&key={API_KEY}'
        response = requests.get(food_places_url, timeout=5)
        places = response.json()
        return places.get('results', [])[:5] if places.get('status') == 'OK' else []
    except Exception as e:
        print(f"Food places error: {e}")
        return []

def get_place_image_url(place_id):
    try:
        place_details_url = f"https://maps.googleapis.com/maps/api/place/details/json?placeid={place_id}&key={API_KEY}"
        response = requests.get(place_details_url, timeout=5)
        data = response.json()
        
        if "result" in data and "photos" in data["result"]:
            photo_reference = data["result"]["photos"][0]["photo_reference"]
            return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key={API_KEY}"
        return None
    except Exception as e:
        print(f"Image URL error: {e}")
        return None

def create_trip_plan(destination, activity, keyword=""):
    prompt = (
        f"Do not make the answer in markdown format. Not in .md format, do not add asterisks. "
        f"just have regular sentences, Create a personalized trip plan to {activity} at {destination} for 1 day "
        f"{f'catered the activites to {keyword}' if keyword else ''}. Include outdoor activities and food places. "
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

    reverse_place_types = {}
    with open('types.txt', 'r') as file:
        for line in file:
            parts = line.strip().split(",", 1)  # Split on first whitespace
            if len(parts) == 2:
                first, second = parts
                reverse_place_types[second] = first

    activity_dict = {
        'name': activity['name'],
        'vicinity': activity.get('vicinity', 'N/A'),
        'latitude': activity['geometry']['location']['lat'],
        'longitude': activity['geometry']['location']['lng'],
        'place_id': activity['place_id'],
        "price_level": activity.get('price_level', 'N/A'),
        "rating": activity.get('rating', 'N/A'),
        "number_of_ratings": activity.get('user_ratings_total', 'N/A'),
        "types": reverse_place_types.get(activity.get('types', ['N/A'])[0], "Unknown Type")

    }
    
    # Process food places and image in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_food = executor.submit(get_food_places_nearby, activity_dict['latitude'], activity_dict['longitude'], radius)
        future_image = executor.submit(get_place_image_url, activity_dict['place_id'])
        future_plan = executor.submit(create_trip_plan, activity_dict['vicinity'], activity_dict['name'], keyword)
        
        activity_dict['food_places_nearby'] = future_food.result()
        activity_dict['image_url'] = future_image.result()
        activity_dict['trip_plan'] = future_plan.result()
    
    return activity_dict

def get_outdoor_activities(lat, lng, radius=1000, keyword="", outdoor_types=None):
    urls = [
        f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&type={place_type}&key={API_KEY}'
        for place_type in outdoor_types
    ]
    
    places_results = fetch_places_parallel(urls)
    activities = []
    seen_activities = set()

    for places in places_results:
        if places.get('status') == 'OK':
            for activity in places['results'][:2]:
                activity_id = (activity['name'], activity['geometry']['location']['lat'], activity['geometry']['location']['lng'])
                
                if activity_id not in seen_activities:
                    seen_activities.add(activity_id)
                    activities.append(process_activity(activity, keyword, radius))
    
    return activities

@app.route("/", methods=["GET", "POST"])
def index():
    if not authentication:
        return render_template("index.html")
    
    if not session.get("name"):
        return render_template("index.html", authentication=True)
    
    try:
        # Get location
        lat, lng = get_ip_location()
        keyword = request.args.get("keywords", "")
        place_types = request.args.getlist("place_types")

        standard_place_types = ['park', 'stadium', 'tourist_attraction', 'gym', 'hiking']

        reversed_place_types = {}

        with open('types.txt', 'r') as file:
            for line in file:
                parts = line.strip().split(",", 1)  # Split on first whitespace
                if len(parts) == 2:
                    first, second = parts
                    reversed_place_types[first] = second

        converted_place_types = [reversed_place_types.get(place_type) for place_type in place_types]

        if len(converted_place_types) > 0:
            standard_place_types = converted_place_types
        
        if address := request.args.get("address"):
            if coordinates := get_coordinates(address):
                lat, lng = coordinates
        
        # Get place types (consider moving this outside the route)
        with open('types.txt', 'r') as file:
            place_types = [line.strip().split(",")[0] for line in file.readlines()]
        
        suggestions = get_outdoor_activities(lat, lng, 1000, keyword, standard_place_types)
        return render_template("/auth/loggedIn.html", suggestions=suggestions, place_types=place_types)
    
    except Exception as e:
        print(f"Route error: {e}")
        return render_template("/auth/loggedIn.html", error="An error occurred")

if __name__ == '__main__' and autoRun:
    app.run(debug=True, port=port)
