import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import LabelEncoder
import os

# === NEW: Find the directory this file is in ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# === NEW: Create full path to your data file ===
data_file_path = os.path.join(BASE_DIR, 'travel_data.csv')

# --- 1. Model Training Function ---
def train_model(file_path):
    """
    Loads data, converts text to numbers, and trains a Decision Tree model.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Data file not found: {file_path}")
        
    data = pd.read_csv(file_path)
    X = data.drop('Trip_Plan', axis=1)
    y = data['Trip_Plan']

    encoders = {}
    for column in X.columns:
        if X[column].dtype == 'object':
            le = LabelEncoder()
            X[column] = le.fit_transform(X[column])
            encoders[column] = le

    target_encoder = LabelEncoder()
    y_encoded = target_encoder.fit_transform(y)

    model = DecisionTreeClassifier(random_state=42)
    model.fit(X, y_encoded)

    print("🤖 Trip Suggestion Model trained successfully on travel_data.csv!")
    return model, encoders, target_encoder, list(X.columns)

# --- 2. Train Model ONCE on Server Start ---
try:
    MODEL, ENCODERS, TARGET_ENCODER, FEATURE_NAMES = train_model(data_file_path)
except Exception as e:
    print(f"!!!!!!!!!! FAILED TO TRAIN TRIP MODEL: {e} !!!!!!!!!!")
    MODEL, ENCODERS, TARGET_ENCODER, FEATURE_NAMES = None, None, None, None

# --- 3. Prediction Function (to be called by the server) ---
def get_trip_recommendation(user_inputs):
    """
    Takes user input dictionary and predicts the top 3 most likely trip plans.
    """
    if not MODEL:
        return "Error: Trip model is not loaded. Check server logs."
    try:
        input_df = pd.DataFrame([user_inputs])

        for col, enc in ENCODERS.items():
            if col in input_df.columns:
                val = input_df[col].iloc[0]
                if val not in enc.classes_:
                    print(f"⚠️ Unknown value '{val}' in {col}. Using default value '{enc.classes_[0]}'")
                    val = enc.classes_[O]
                input_df[col] = enc.transform([val])
        
        input_df = input_df[FEATURE_NAMES]
        proba = MODEL.predict_proba(input_df)[0]
        top_indices = np.argsort(proba)[::-1][:3]
        top_classes = TARGET_ENCODER.inverse_transform(top_indices)
        top_probs = proba[top_indices]

        suggestion_html = "Based on your choices, here are the top 3 destinations:<br><ul>"
        for i, (place, prob) in enumerate(zip(top_classes, top_probs), 1):
            suggestion_html += f"<li><b>{i}. {place}</b></li>"
        suggestion_html += "</ul>"
        
        return suggestion_html
    except Exception as e:
        print(f"Error during trip prediction: {e}")
        return f"An error occurred during prediction: {e}"