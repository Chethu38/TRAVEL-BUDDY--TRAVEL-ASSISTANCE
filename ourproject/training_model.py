import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
import joblib
import matplotlib.pyplot as plt
import os

# -------------------------------
# TRAINING: Crowd Prediction Model
# -------------------------------

# Path to your preprocessed dataset
file_path = r'D:\\MINIProject\\ourproj2\\prediction.csv'

# Load dataset
data = pd.read_csv(file_path)

# Clean column names (remove units like °C, %, etc.)
data.columns = data.columns.str.replace(r'\s\(.+\)', '', regex=True)

# Feature selection
X = data[['temperature', 'humidity', 'wind_speed']].values
y = data['crowd_level'].values

# Split dataset into train/test
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Normalize features
scaler = MinMaxScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

# Save scaler for future predictions
joblib.dump(scaler, r'd:\MINIProject\ourproj2\scaler.pkl')

# Define the ANN model
model = Sequential([
    Dense(128, activation='relu', input_shape=(X_train.shape[1],)),
    Dropout(0.2),
    Dense(64, activation='relu'),
    Dropout(0.2),
    Dense(32, activation='relu'),
    Dense(1, activation='linear')  # Regression output
])

# Compile model
model.compile(optimizer='adam', loss='mean_squared_error', metrics=['mse'])

# Train model
history = model.fit(
    X_train, y_train,
    validation_data=(X_test, y_test),
    epochs=50,
    batch_size=32,
    verbose=1
)

# Save the trained model
model.save(r'd:\MINIProject\ourproj2\crowd_prediction_model.h5')

# Evaluate model
loss, mse = model.evaluate(X_test, y_test, verbose=0)
print(f"\n✅ Model evaluation completed. Test MSE: {mse:.4f}")

# Plot training history
plt.plot(history.history['loss'], label='Training Loss')
plt.plot(history.history['val_loss'], label='Validation Loss')
plt.legend()
plt.title('Training History')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.show()
