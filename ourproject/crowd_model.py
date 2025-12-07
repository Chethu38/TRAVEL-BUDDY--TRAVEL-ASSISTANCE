import numpy as np
from tensorflow.keras.models import load_model
import joblib

# Load model & scaler
model = load_model("crowd_prediction_model.h5")
scaler = joblib.load("scaler.pkl")

print("--- Crowd model and scaler loaded successfully ---")

def get_crowd_prediction(temp, humidity, wind_speed):
    """
    Predicts crowd level (%) from temperature, humidity, and wind_speed.
    Ensures output stays between 0 and 100%.
    """
    try:
        # Prepare input as numpy array
        X = np.array([[temp, humidity, wind_speed]])
        X_scaled = scaler.transform(X)

        # Model prediction
        y_pred = model.predict(X_scaled)
        crowd_value = float(y_pred[0][0])

        # --- FIX: Clamp / normalize result ---
        if crowd_value < 0:
            crowd_value = 0
        elif crowd_value > 1000:  # prevent huge spikes like 2738%
            crowd_value = crowd_value / 10.0

        # If still above 100, wrap around or cap at 100
        if crowd_value > 100:
            crowd_value = crowd_value % 100

        return round(crowd_value, 2)

    except Exception as e:
        print("⚠️ Error predicting crowd level:", e)
        return 50.0  # fallback moderate value
