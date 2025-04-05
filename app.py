
from flask import Flask, render_template, request, redirect, session, jsonify
from flask_session import Session
from datetime import datetime
import pytz
from sql import * #Used for database connection and management
from SarvAuth import * #Used for user authentication functions
from auth import auth_blueprint
import requests
from dotenv import load_dotenv

load_dotenv()
# Authentication Encryption Key (Replace with your actual encryption string)
API_KEY = os.getenv("GOOGLE_API_KEY")

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = True
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

autoRun = True #Change to True if you want to run the server automatically by running the app.py file
port = 5000 #Change to any port of your choice if you want to run the server automatically
authentication = True #Change to False if you want to disable user authentication

if authentication:
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

# Replace with your API key and endpoint (you may need to update this based on Gemini API documentation)
GEMINI_API_URL = "https://gemini.googleapis.com/v1/create-trip-plan"
GEMINI_API_KEY = 'YOUR_GEMINI_API_KEY'

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
        return places['results']
    else:
        return []

# Function to fetch outdoor activities (using related place types)
def get_outdoor_activities(lat, lng, radius=1000):
    outdoor_types = ['park', 'stadium', 'tourist_attraction', 'gym', 'hiking']
    activities = []

    # Loop through each outdoor type and make an API request
    for place_type in outdoor_types:
        url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&type={place_type}&key={API_KEY}'
        response = requests.get(url)
        places = response.json()

        if places['status'] == 'OK':
            for activity in places['results']:
                activity_dict = {
                    'name': activity['name'],
                    'vicinity': activity.get('vicinity', 'N/A'),
                    'latitude': activity['geometry']['location']['lat'],
                    'longitude': activity['geometry']['location']['lng']
                }

                # Get food places nearby this activity
                food_places = get_food_places_nearby(activity_dict['latitude'], activity_dict['longitude'], radius=1000)
                
                # Add food places nearby to the activity dictionary
                activity_dict['food_places_nearby'] = food_places

                # Append the activity with its nearby food places to the list of activities
                activities.append(activity_dict)

    return activities



# Route to get suggestions based on the user's location (from IP)
@app.route('/get_suggestions', methods=["GET",'POST'])
def get_suggestions():
    # Get the user's location from IP
    lat, lng = get_ip_location()

    # Get nearby outdoor activities
    suggestions = get_outdoor_activities(lat, lng)
    return jsonify(suggestions)

#This route is the base route for the website which renders the index.html file
@app.route("/", methods=["GET", "POST"])
def index():
    if not authentication:
        return render_template("index.html")
    else:
        if not session.get("name"):
            return render_template("index.html", authentication=True)
        else:
            return render_template("/auth/loggedin.html")

if autoRun:
    if __name__ == '__main__':
        app.run(debug=True, port=port)
