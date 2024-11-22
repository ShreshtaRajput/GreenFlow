from flask import Flask, request, render_template, redirect, url_for, jsonify
import joblib
import numpy as np
import requests
from sqlalchemy import Integer, create_engine, Column, Float, String, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import threading
import pickle

Base = declarative_base()

class IrrigationData(Base):
    __tablename__ = 'irrigation_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    humidity = Column(Float)
    temperature = Column(Float)
    last_checked_moisture = Column(Float)
    rainfall_prediction = Column(String(3))
    rag_status = Column(String(5))
    irrigation_needed = Column(String(3))

# Create a new SQLite database (or connect to an existing one)
engine = create_engine('sqlite:///irrigation.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_irrigation_prediction(last_checked_moisture, humidity, temperature, rainfall_prediction):
    # Prepare the payload for the prediction request
    payload = {
        "moisture": last_checked_moisture,
        "humidity": humidity,
        "temperature": temperature,
        "rainfall_prediction": rainfall_prediction
    }
    response = requests.post('https://03b2-2409-40d0-11-b574-e41d-f72d-1ed4-80b7.ngrok-free.app/predict', json=payload)
    if response.status_code == 200:
        return response.json().get("prediction")  # Assuming your API returns this field
    return "No"  # Default to "No" if there’s an issue

app = Flask(__name__)
app.config['OPENWEATHER_API_KEY'] = 'e03222f5d17fbf6deab758d60af38551'
NGROK_PREDICTION_URL = "https://0d24-152-58-92-103.ngrok-free.app/predict"

def get_weather_data(city_name="New Delhi"):
    api_key = app.config['OPENWEATHER_API_KEY']
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}&units=metric"
    
    response = requests.get(url)
    if response.status_code == 200:
        # global data
        data = response.json()
        # global temperature
        temperature = data['main']['temp']
        # global humidity
        humidity = data['main']['humidity']
        # global rain_forecast
        rain_forecast = "Yes" if 'rain' in data else "No"
        return {
            "temperature": temperature,
            "humidity": humidity,
            "rain_forecast": rain_forecast
        }
    else:
        print("Error fetching weather data:", response.status_code)
        return None

moisture_threshold = 40  
last_checked_moisture = 100
message = ""
current_mode = "Basic"

model = joblib.load('irrigation_model.pkl')
@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    try:
        # Retrieve and parse input data
        moisture = float(data.get('moisture'))
        temperature = float(data.get('temperature'))
        humidity = float(data.get('humidity'))
        rain_forecast = data.get('rain_forecast')
        
        # Validate rain_forecast input
        if rain_forecast not in ["Yes", "No"]:
            return jsonify({"error": "Invalid value for rain_forecast; use 'Yes' or 'No'."}), 400
        
        # Prepare features for prediction
        features = np.array([[moisture, temperature, humidity, rain_forecast]])

        # Predict using the model
        prediction = model.predict(features)

        # Format and return the result
        result = "YES" if prediction[0] == 1 else "NO"
        return jsonify({"prediction": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/water', methods=['GET'])
def water():
    global last_checked_moisture, moisture_threshold, current_mode, message

    if last_checked_moisture is not None:
        if current_mode == "Basic":
            if last_checked_moisture < moisture_threshold:
                message = "Moisture is below the threshold. Watering will be initiated."
                return jsonify({"cmd": "water"}), 200
            else:
                message = f"Moisture is {last_checked_moisture}%, which is more than the threshold ({moisture_threshold}%). No watering needed."
                return jsonify({"cmd": "no_water"}), 200
        elif current_mode == "ML Prediction":
            weather_data = get_weather_data("New Delhi")            
            if weather_data:
                prediction_data = {
                    "moisture": last_checked_moisture,
                    "temperature": weather_data["temperature"],
                    "humidity": weather_data["humidity"],
                    "rainfall_prediction": weather_data["rain_forecast"]
                }
                prediction_response = requests.post(NGROK_PREDICTION_URL, json=prediction_data)
                
                if prediction_response.status_code == 200:
                    prediction_result = prediction_response.json().get("prediction")
                    if prediction_result == "YES":
                        message = "ML Model suggests watering based on conditions."
                        return jsonify({"cmd": "water"}), 200
                    else:
                        message = "ML Model suggests no watering needed based on conditions."
                        return jsonify({"cmd": "no_water"}), 200
                else:
                    message = "Error getting prediction."
                    return jsonify({"cmd": "no_water"}), 500
            else:
                message = "Error fetching weather data."
                return jsonify({"cmd": "no_data"}), 500

    message = "Moisture data not available."
    return jsonify({"cmd": "no_data"}), 200

@app.route('/')
def home():
    return render_template('home.html')

abc_response = ""
def abc():
    # global abc_response
    # Replace with your actual API key and external user ID
    weather_data_abc = get_weather_data("new delhi")
    api_key = 'KPckVRvU7yFf8K9ETN29gs5OxH9j2uGv'
    external_user_id = '<replace_external_user_id>'

    # Step 1: Create Chat Session
    create_session_url = 'https://api.on-demand.io/chat/v1/sessions'
    create_session_headers = {
        'apikey': api_key
    }
    create_session_body = {
        "pluginIds": ["plugin-1729888199",],
        "externalUserId": external_user_id
    }

    # Make the request to create a chat session
    create_session_response = requests.post(create_session_url, headers=create_session_headers, json=create_session_body)
    create_session_data = create_session_response.json()
    # print(create_session_data)
    # Extract the session ID from the response
    session_id = create_session_data['data']['id']

    # Step 2: Submit Query
    submit_query_url = f'https://api.on-demand.io/chat/v1/sessions/{session_id}/query'
    submit_query_headers = {
        'apikey': api_key
    }

    submit_query_body = {
        "endpointId": "predefined-openai-gpt4o",
        "query": f'The moisture level is {last_checked_moisture}, humidity is {weather_data_abc["humidity"]}, temparature is {weather_data_abc["temperature"]} and rainfall is {weather_data_abc["rain_forecast"]}, give prediction response',
        "pluginIds": ["plugin-1729888199",],
        "responseMode": "sync"
    }

    # Make the request to submit the query
    submit_query_response = requests.post(submit_query_url, headers=submit_query_headers, json=submit_query_body)
    submit_query_data = submit_query_response.json()

    # Print the response from the query submission
    # print(submit_query_data)
    abc_response = submit_query_data['data']['answer']
    print(submit_query_data['data']['answer'])
    return abc_response


@app.route('/dashboard', methods=['GET'])
def dashboard():
    global moisture_threshold, last_checked_moisture, message
    abc_response = abc()  # Call abc() function
    return render_template('dashboard.html',
                            abc_response=abc_response, 
                           moisture_threshold=moisture_threshold, 
                           last_checked_moisture=last_checked_moisture,
                           message=message, mode=current_mode)

@app.route('/settings', methods=['GET'])
def settings():
    global moisture_threshold, current_mode
    return render_template('settings2.html', 
                           moisture_threshold=moisture_threshold,
                           current_mode=current_mode)

@app.route('/get_moisture', methods=['POST'])
def get_moisture():
    global last_checked_moisture, message
    if request.is_json:
        data = request.get_json()
        last_checked_moisture = data.get('moisture')
        print(f"Moisture level received: {last_checked_moisture}")

        # Fetch current weather data
        weather_data = get_weather_data("New Delhi")  # Replace with your desired city if needed
        
        if weather_data:
            humidity = weather_data["humidity"]
            temperature = weather_data["temperature"]
            rainfall_prediction = weather_data["rain_forecast"] == "Yes"  # Convert to boolean

            # Insert data into the database
            
            return jsonify({"status": "Moisture data received"}), 200
        else:
            return jsonify({"error": "Could not fetch weather data."}), 500
    else:
        print("Dashboard requested moisture data update")
        return redirect(url_for('dashboard'))

@app.route('/update_threshold', methods=['POST'])
def update_threshold():
    global moisture_threshold
    global current_mode

    new_threshold = request.form.get('threshold', type=int)
    if new_threshold is not None:
        if 0 <= new_threshold <= 100:
            moisture_threshold = new_threshold

    
    selected_mode = request.form.get('mode')
    if selected_mode in ["Basic", "ML Prediction"]:
        current_mode = selected_mode
        print(f"Updated mode: {current_mode}")
    return redirect(url_for('dashboard'))

@app.route('/update_mode', methods=['POST'])
def update_mode():
    global current_mode
    selected_mode = request.form.get('mode')
    if selected_mode in ["Basic", "ML Prediction"]:
        current_mode = selected_mode
        print(f"Updated mode: {current_mode}")
    return redirect(url_for('dashboard'))




if __name__ == '__main__':
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False))
    flask_thread.daemon = True
    flask_thread.start()

    # Call the API function in the main thread or another separate thread if needed
    abc()
    try:
        while True:
            pass  # Keep the main thread alive
    except KeyboardInterrupt:
        print("Shutting down...")

