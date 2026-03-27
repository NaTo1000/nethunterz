#!/usr/bin/env python3
"""
flipper_control_model.py - TensorFlow/Keras model for Flipper board control prediction.
Predicts the optimal action to take given the current system state features.
"""

import json
import os
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

try:
    import tensorflow as tf
    from tensorflow import keras
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("TensorFlow not available. Model definition only.")


# Action classes matching the Android DecisionEngine
ACTION_CLASSES = [
    "NONE",
    "CONNECT_FLIPPER",
    "SEND_PING",
    "GET_VERSION",
    "CHECK_STORAGE",
]

# Feature names matching AIController.collectModelFeatures()
FEATURE_NAMES = [
    "flipper_connected",    # 0 or 1
    "connection_type",      # normalized 0-1
    "time_of_day",          # normalized 0-1 (time within 24h)
    "decision_ratio",       # decisions / (decisions + 1)
    "has_taken_action",     # 0 or 1
    "system_state",         # normalized enum 0-1
    "noise",                # small random noise
]

INPUT_DIM    = len(FEATURE_NAMES)
OUTPUT_DIM   = len(ACTION_CLASSES)
HIDDEN_UNITS = [64, 32, 16]


def build_model(input_dim: int = INPUT_DIM,
                output_dim: int = OUTPUT_DIM) -> "keras.Model":
    """
    Build a simple sequential neural network for action classification.
    Architecture: Dense(64) -> Dense(32) -> Dense(16) -> Dense(5, softmax)
    """
    if not TF_AVAILABLE:
        raise ImportError("TensorFlow is required to build the model")

    model = keras.Sequential([
        keras.layers.Input(shape=(input_dim,), name='state_features'),
        keras.layers.Dense(HIDDEN_UNITS[0], activation='relu', name='fc1'),
        keras.layers.BatchNormalization(name='bn1'),
        keras.layers.Dropout(0.2, name='dropout1'),

        keras.layers.Dense(HIDDEN_UNITS[1], activation='relu', name='fc2'),
        keras.layers.BatchNormalization(name='bn2'),
        keras.layers.Dropout(0.1, name='dropout2'),

        keras.layers.Dense(HIDDEN_UNITS[2], activation='relu', name='fc3'),

        keras.layers.Dense(output_dim, activation='softmax', name='action_probs'),
    ], name='flipper_control_model')

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    return model


def generate_synthetic_data(n_samples: int = 5000) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic training data based on known rules.
    This bootstraps the model before real usage data is available.
    """
    rng = np.random.default_rng(42)

    X = rng.random((n_samples, INPUT_DIM)).astype(np.float32)
    # Discretize binary features
    X[:, 0] = (rng.random(n_samples) > 0.5).astype(np.float32)  # connected
    X[:, 4] = (rng.random(n_samples) > 0.7).astype(np.float32)  # has_action

    # Generate labels based on rules:
    # - Not connected -> CONNECT_FLIPPER (class 1)
    # - Connected, no version yet -> GET_VERSION (class 3)
    # - Connected, recent action -> SEND_PING (class 2)
    # - Otherwise -> CHECK_STORAGE (class 4) or NONE (class 0)
    y_indices = np.zeros(n_samples, dtype=int)

    not_connected = X[:, 0] < 0.5
    connected     = X[:, 0] >= 0.5
    high_time     = X[:, 2] > 0.8

    y_indices[not_connected]            = 1  # CONNECT_FLIPPER
    y_indices[connected & high_time]    = 2  # SEND_PING
    y_indices[connected & ~high_time & (X[:, 3] < 0.3)] = 3  # GET_VERSION
    y_indices[connected & ~high_time & (X[:, 3] >= 0.3)] = 4  # CHECK_STORAGE
    # Add some noise
    noise_mask = rng.random(n_samples) < 0.05
    y_indices[noise_mask] = rng.integers(0, OUTPUT_DIM, noise_mask.sum())

    y = tf.keras.utils.to_categorical(y_indices, num_classes=OUTPUT_DIM)
    return X, y.astype(np.float32)


def save_model(model, output_dir: Path):
    """Save the model in both Keras and TFLite formats."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save Keras model
    keras_path = output_dir / "flipper_control_model.keras"
    model.save(keras_path)
    print(f"Keras model saved: {keras_path}")

    # Convert to TFLite
    tflite_path = output_dir / "flipper_control_model.tflite"
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_model = converter.convert()

    with open(tflite_path, 'wb') as f:
        f.write(tflite_model)
    print(f"TFLite model saved: {tflite_path} ({len(tflite_model):,} bytes)")

    # Save model metadata
    metadata = {
        "input_dim": INPUT_DIM,
        "output_dim": OUTPUT_DIM,
        "feature_names": FEATURE_NAMES,
        "action_classes": ACTION_CLASSES,
        "hidden_units": HIDDEN_UNITS,
    }
    with open(output_dir / "model_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

    return tflite_path


if __name__ == '__main__':
    if not TF_AVAILABLE:
        print("TensorFlow not installed. Install with: pip install tensorflow")
        exit(1)

    print(f"Building Flipper control model: {INPUT_DIM} inputs -> {OUTPUT_DIM} outputs")
    model = build_model()
    model.summary()

    print("\nGenerating synthetic training data...")
    X_train, y_train = generate_synthetic_data(5000)
    X_val,   y_val   = generate_synthetic_data(1000)

    print("Training model...")
    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=20,
        batch_size=64,
        verbose=1
    )

    output_dir = Path("ai/models/output")
    tflite_path = save_model(model, output_dir)
    print(f"\nModel ready for Android deployment: {tflite_path}")
