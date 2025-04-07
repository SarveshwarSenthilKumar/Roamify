from flask import Flask, render_template, request, redirect, session, jsonify
from flask_session import Session
from datetime import datetime
import pytz
from sql import *  # Used for database connection and management
from SarvAuth import *  # Used for user authentication functions
from auth import auth_blueprint
import requests
import google.generativeai as genai
from dotenv import load_dotenv
import os
from geopy.geocoders import Nominatim

load_dotenv()
# Authentication Encryption Key (Replace with your actual encryption string)
API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = True
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

autoRun = True  # Change to True if you want to run the server automatically by running the app.py file
port = 5000  # Change to any port of your choice if you want to run the server automatically
authentication = True  # Change to False if you want to disable user authentication

if authentication:
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

# Function to chat with Gemini (similar to the provided code)
def chat_with_gemini(prompt):
    model = genai.GenerativeModel("gemini-2.0-flash-lite")  # Using Gemini model
    response = model.generate_content(prompt)
    return response.text.strip()

def get_place_image_url(place_id):
    # First, get the Place Details from the Google Places API
    place_details_url = f"https://maps.googleapis.com/maps/api/place/details/json?placeid={place_id}&key={API_KEY}"
    
    # Send a request to the Google Places API
    response = requests.get(place_details_url)
    
    # Check if the response is successful
    if response.status_code == 200:
        data = response.json()
        
        # Check if the image data is available in the response
        if "result" in data and "photos" in data["result"]:
            # Google Places API gives an array of photos, we'll just use the first one
            photo_reference = data["result"]["photos"][0]["photo_reference"]
            
            # Construct the URL for the photo using the photo_reference
            image_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key={API_KEY}"
            return image_url
        else:
            print("No photos found for this place.")
            return None
    else:
        print(f"Error: Unable to fetch details for Place ID {place_id}")
        return None

# Function to create a personalized trip plan using Gemini
def create_trip_plan(destination, keyword):
    if keyword == "":
        # Create the prompt based on user input
        prompt = f"Do not make the answer in markdown format. Not in .md format, do not add asterisks. just have regular sentences, Create a personalized trip plan to {destination} for 1 day. Include outdoor activities and food places. Include the name of the place, address, and a brief description of each activity. Make sure to include at least 2 outdoor activities and 2 food places. Do not include any other information. Do not add any other information. Do not add any other information. Do not add any other information."
    else:
        # Create the prompt based on user input
        prompt = f"Do not make the answer in markdown format. Not in .md format, do not add asterisks. just have regular sentences, Create a personalized trip plan to {destination} for 1 day catered the activites to {keyword}. Include outdoor activities and food places. Include the name of the place, address, and a brief description of each activity. Make sure to include at least 2 outdoor activities and 2 food places. Do not include any other information. Do not add any other information. Do not add any other information. Do not add any other information."

    # Use the chat_with_gemini function to generate the content (trip plan)
    trip_plan = chat_with_gemini(prompt)

    return trip_plan

# Function to get the location from the IP address
def get_ip_location():
    # Use ipinfo.io to get location information from the user's IP address
    response = requests.get('https://ipinfo.io/json')
    data = response.json()
    location = data['loc'].split(',')
    return float(location[0]), float(location[1])

# Function to fetch food places near a given latitude and longitude
def get_food_places_nearby(lat, lng, radius=1000):
    food_places_url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&type=restaurant&key={API_KEY}'
    response = requests.get(food_places_url)
    places = response.json()

    if places['status'] == 'OK':
        return places['results'][:5]
    else:
        return []
    
# Function to get coordinates from an address using Nominatim
def get_coordinates(address):
    geolocator = Nominatim(user_agent="roamify-app")
    location = geolocator.geocode(address)
    if location:
        return location.latitude, location.longitude
    return None

# Function to fetch outdoor activities (using related place types)
def get_outdoor_activities(lat, lng, radius=1000, keyword=""):
    print(f"Fetching outdoor activities for coordinates: {lat}, {lng} with radius: {radius} and keyword: {keyword}")
    # Define the types of outdoor activities to search for
    outdoor_types = ['park', 'stadium', 'tourist_attraction', 'gym', 'hiking']
    activities = []
    seen_activities = set()

    # Loop through each outdoor type and make an API request
    for place_type in outdoor_types:
        # Make a request to the Google Places API for outdoor activities
        url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&type={place_type}&key={API_KEY}'
        response = requests.get(url)
        places = response.json()

        if places['status'] == 'OK':
            for activity in places['results'][:2]:
                # Create a unique identifier for this activity (name + latitude + longitude)
                activity_id = (activity['name'], activity['geometry']['location']['lat'], activity['geometry']['location']['lng'])

                if activity_id not in seen_activities:
                    # Add the activity ID to the set of seen activities
                    seen_activities.add(activity_id)

                    # Add the activity details to the activities list
                    activity_dict = {
                        'name': activity['name'],
                        'vicinity': activity.get('vicinity', 'N/A'),
                        'latitude': activity['geometry']['location']['lat'],
                        'longitude': activity['geometry']['location']['lng'],
                        'place_id': activity['place_id'],  # Add the place_id here
                        "price_level": activity.get('price_level', 'N/A'),  # Ensure we get a default value if not available
                        "rating": activity.get('rating', 'N/A'),
                        "number_of_ratings": activity.get('user_ratings_total', 'N/A'),
                        "types": [t.capitalize() for t in activity.get('types', ['N/A'])][0]  # Capitalize each type
                    }

                    # Get food places nearby this activity
                    food_places = get_food_places_nearby(activity_dict['latitude'], activity_dict['longitude'], radius=1000)

                    # Create the trip plan for this activity
                    activity_dict['trip_plan'] = create_trip_plan(activity_dict['vicinity'], keyword)

                    # Add food places nearby to the activity dictionary
                    activity_dict['food_places_nearby'] = food_places

                    # Add image URL for this activity
                    activity_dict['image_url'] = get_place_image_url(activity_dict['place_id'])

                    # Append the activity with its nearby food places and image URL to the list of activities
                    activities.append(activity_dict)

    return activities

# This route is the base route for the website which renders the index.html file
@app.route("/", methods=["GET", "POST"])
def index():
    if not authentication:
        return render_template("index.html")
    else:
        if not session.get("name"):
            return render_template("index.html", authentication=True)
        else:
            # Get the user's location from IP
            lat, lng = get_ip_location()

            keyword = ""

            address = request.args.get("address")
            keyword = request.args.get("keywords")

            if address:
                # Get coordinates from the address
                try:
                    coordinates = get_coordinates(address)
                except:
                    coordinates = None

                if coordinates:
                    lat, lng = coordinates
                else:
                    return render_template("loggedin.html", error="Invalid address.")

            # Get nearby outdoor activities
            suggestions = get_outdoor_activities(lat, lng, 1000, keyword)

            # Pass the suggestions (including image_url) to the template
            return render_template("/auth/loggedin.html", suggestions=suggestions)

if autoRun:
    if __name__ == '__main__':
        app.run(debug=True, port=port)
