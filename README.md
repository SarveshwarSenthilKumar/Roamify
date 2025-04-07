
# 🌲 Roamify

**Roamify** is a personalized web application that helps users discover outdoor activities nearby using AI. Leveraging intelligent recommendations, it generates customized plans based on user preferences, location, and weather.

This project is built on top of the [Flask Development Template](https://github.com/SarveshwarSenthilKumar/Flask-Development-Template) to ensure a clean, modular, and scalable foundation for rapid development.

---

## 🚀 Features

- 🔍 **AI-Powered Recommendations**  
  Get tailored suggestions for outdoor activities like hiking, biking, and events based on your location and preferences.

- 🗺️ **Location-Based Discovery**  
  Uses geolocation to suggest activities nearby.

- 🎯 **Personalized Itineraries**  
  Build a smart plan for your day out—weather-aware and goal-driven.

- 🧱 **Modular Flask Structure**  
  Organized app with Blueprints, Jinja templating, and environment-based config.

- 🌐 **Responsive UI**  
  Lightweight front-end using Bootstrap for mobile and desktop views.

---

## 🏗️ Tech Stack

- **Backend:** Flask (Python)  
- **Frontend:** HTML, Bootstrap, Jinja2  
- **AI/ML:** *(Google Gemini)*  
- **Geolocation:** *(Google Maps API)*  
- **Weather API:** *(Optional — OpenWeatherMap API or similar)*

---

## 📦 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/SarveshwarSenthilKumar/Roamify.git
   cd Roamify
   ```

2. **Set up a virtual environment (optional but recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the app:**
   ```bash
   flask run
   ```

   The app will be available at `http://127.0.0.1:5000`

---

## ⚙️ Configuration

Environment variables can be set in a `.env` file (based on the Flask Development Template). Key variables include:

```
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key
```

---

## 🧠 AI Integration (Planned)

We plan to incorporate AI models for:

- Natural language preference input
- Smart clustering of activities
- Predictive itinerary optimization

Integration options include:

- OpenAI API for language-based interactions
- Scikit-learn or TensorFlow for recommendation logic

---

## 📍 Future Improvements

- 🔗 Integrate Google Maps or OpenStreetMap for real-time activity locations  
- 🌦️ Use a weather API to make plans context-aware  
- 🧠 Fully implement AI recommendation engine  
- 📝 Save itineraries to user profiles (with login system)  
- 📱 Build a mobile-friendly PWA version  

---

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests. If you’d like to work on something major, please open an issue first to discuss what you’d like to change.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 💬 Acknowledgements

- Built at **Eureka Hacks 2025**  
- Special thanks to the mentors, judges, and everyone who tested our app!  
- Huge shoutout to [Pranav Bailoor](https://www.linkedin.com/in/pranavbailoor) for being an awesome teammate
