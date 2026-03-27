#!/usr/bin/env python3
"""
train_model.py - Training script for the Flipper control ML model.
Loads synthetic or real data, trains the model, and exports TFLite.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def load_training_data(data_path: Path):
    """Load training data from JSON lines file or generate synthetic data."""
    if data_path and data_path.exists():
        X_list, y_list = [], []
        with open(data_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                sample = json.loads(line)
                X_list.append(sample["features"])
                y_list.append(sample["label"])
        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.int32)
        logger.info(f"Loaded {len(X)} training samples from {data_path}")
        return X, y
    else:
        logger.info("No data file found, generating synthetic data...")
        from ai.models.flipper_control_model import generate_synthetic_data
        X, y_onehot = generate_synthetic_data(5000)
        y = np.argmax(y_onehot, axis=1)
        return X, y


def train(data_path: Path, output_dir: Path, epochs: int = 30, batch_size: int = 64):
    """Full training pipeline."""
    try:
        import tensorflow as tf
        from tensorflow import keras
    except ImportError:
        logger.error("TensorFlow is required. Install: pip install tensorflow")
        sys.exit(1)

    from ai.models.flipper_control_model import (
        build_model, save_model, generate_synthetic_data, OUTPUT_DIM
    )

    # Load data
    X, y_raw = load_training_data(data_path)
    y = keras.utils.to_categorical(y_raw, num_classes=OUTPUT_DIM)

    # Split train/validation
    n = len(X)
    split = int(n * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    logger.info(f"Training samples: {len(X_train)}, Validation: {len(X_val)}")

    # Build model
    model = build_model()
    model.summary()

    # Callbacks
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor='val_accuracy',
            patience=5,
            restore_best_weights=True,
            verbose=1
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=3,
            min_lr=1e-6,
            verbose=1
        ),
    ]

    # Train
    logger.info(f"Training for up to {epochs} epochs...")
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=1
    )

    # Evaluate
    val_loss, val_acc = model.evaluate(X_val, y_val, verbose=0)
    logger.info(f"Final validation accuracy: {val_acc:.4f}")
    logger.info(f"Final validation loss: {val_loss:.4f}")

    # Save
    tflite_path = save_model(model, output_dir)
    logger.info(f"Training complete. TFLite model: {tflite_path}")

    # Save training history
    history_path = output_dir / "training_history.json"
    with open(history_path, 'w') as f:
        json.dump({k: [float(v) for v in vals]
                   for k, vals in history.history.items()}, f, indent=2)
    logger.info(f"Training history saved: {history_path}")

    return val_acc


def main():
    parser = argparse.ArgumentParser(description='Train Flipper control model')
    parser.add_argument('--data',      type=Path, default=None,
                        help='Path to training data JSONL file')
    parser.add_argument('--output',    type=Path, default=Path('ai/models/output'),
                        help='Output directory for trained model')
    parser.add_argument('--epochs',    type=int, default=30, help='Max training epochs')
    parser.add_argument('--batch-size', type=int, default=64, help='Training batch size')
    args = parser.parse_args()

    accuracy = train(args.data, args.output, args.epochs, args.batch_size)
    logger.info(f"Model trained with {accuracy:.2%} validation accuracy")
    sys.exit(0 if accuracy > 0.70 else 1)


if __name__ == '__main__':
    main()
