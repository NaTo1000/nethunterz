package com.offsec.nethunter.ai;

import android.content.Context;
import android.content.res.AssetManager;
import android.util.Log;

import org.tensorflow.lite.Interpreter;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * TensorFlow Lite model manager for on-device ML inference.
 * Loads and runs the Flipper control model from app assets.
 */
public class MLModelManager {

    private static final String TAG = "MLModelManager";

    private static final String MODEL_ASSET_PATH = "models/flipper_control_model.tflite";
    private static final int INPUT_FEATURES  = 7;
    private static final int OUTPUT_CLASSES  = 5;
    private static final int NUM_THREADS     = 2;

    private final Context context;
    private Interpreter interpreter;
    private final AtomicBoolean modelLoaded = new AtomicBoolean(false);

    // Output class labels corresponding to DecisionEngine.Action
    public static final String[] ACTION_LABELS = {
        "NONE",
        "CONNECT_FLIPPER",
        "SEND_PING",
        "GET_VERSION",
        "CHECK_STORAGE"
    };

    public MLModelManager(Context context) {
        this.context = context;
    }

    /**
     * Load TensorFlow Lite models from app assets.
     * @return true if at least one model was loaded successfully
     */
    public boolean loadModels() {
        try {
            ByteBuffer modelBuffer = loadModelFile(MODEL_ASSET_PATH);
            if (modelBuffer == null) {
                Log.w(TAG, "Model file not found in assets: " + MODEL_ASSET_PATH);
                return false;
            }

            Interpreter.Options options = new Interpreter.Options()
                .setNumThreads(NUM_THREADS)
                .setUseXNNPACK(true);

            interpreter = new Interpreter(modelBuffer, options);
            modelLoaded.set(true);

            // Validate model I/O dimensions
            validateModel();
            Log.i(TAG, "TFLite model loaded successfully: " + MODEL_ASSET_PATH);
            return true;

        } catch (Exception e) {
            Log.w(TAG, "Could not load TFLite model (inference will be disabled): " + e.getMessage());
            modelLoaded.set(false);
            return false;
        }
    }

    private void validateModel() {
        if (interpreter == null) return;
        int[] inputShape  = interpreter.getInputTensor(0).shape();
        int[] outputShape = interpreter.getOutputTensor(0).shape();
        Log.d(TAG, "Model input shape: " + java.util.Arrays.toString(inputShape));
        Log.d(TAG, "Model output shape: " + java.util.Arrays.toString(outputShape));
    }

    /**
     * Run model inference on the given feature vector.
     * @param features float array of length INPUT_FEATURES
     * @return output probabilities array of length OUTPUT_CLASSES, or null if model not loaded
     */
    public float[] runInference(float[] features) {
        if (!modelLoaded.get() || interpreter == null) {
            return null;
        }
        if (features == null || features.length != INPUT_FEATURES) {
            Log.w(TAG, "Invalid features array: expected " + INPUT_FEATURES
                + " but got " + (features != null ? features.length : "null"));
            return null;
        }

        try {
            // Prepare input tensor
            ByteBuffer inputBuffer = ByteBuffer.allocateDirect(INPUT_FEATURES * 4)
                .order(ByteOrder.nativeOrder());
            for (float f : features) {
                inputBuffer.putFloat(f);
            }
            inputBuffer.rewind();

            // Prepare output tensor
            float[][] output = new float[1][OUTPUT_CLASSES];

            interpreter.run(inputBuffer, output);
            return output[0];

        } catch (Exception e) {
            Log.e(TAG, "Inference error", e);
            return null;
        }
    }

    /**
     * Run inference and return the predicted action label with confidence.
     */
    public InferenceResult predict(float[] features) {
        float[] probabilities = runInference(features);
        if (probabilities == null) {
            return new InferenceResult("NONE", 0.0f, null);
        }

        // Find the class with highest probability
        int maxIndex = 0;
        float maxProb = probabilities[0];
        for (int i = 1; i < probabilities.length; i++) {
            if (probabilities[i] > maxProb) {
                maxProb = probabilities[i];
                maxIndex = i;
            }
        }

        String label = maxIndex < ACTION_LABELS.length ? ACTION_LABELS[maxIndex] : "UNKNOWN";
        return new InferenceResult(label, maxProb, probabilities);
    }

    private ByteBuffer loadModelFile(String assetPath) {
        try {
            AssetManager assetManager = context.getAssets();
            try (InputStream is = assetManager.open(assetPath)) {
                byte[] bytes = is.readAllBytes();
                ByteBuffer buffer = ByteBuffer.allocateDirect(bytes.length)
                    .order(ByteOrder.nativeOrder());
                buffer.put(bytes);
                buffer.rewind();
                return buffer;
            }
        } catch (IOException e) {
            Log.d(TAG, "Asset not found: " + assetPath);
            return null;
        }
    }

    /**
     * Close and release model resources.
     */
    public void close() {
        if (interpreter != null) {
            interpreter.close();
            interpreter = null;
        }
        modelLoaded.set(false);
        Log.d(TAG, "MLModelManager closed");
    }

    public boolean isModelLoaded() { return modelLoaded.get(); }
    public int getInputFeatureCount() { return INPUT_FEATURES; }
    public int getOutputClassCount()  { return OUTPUT_CLASSES; }

    // --- Result class ---

    public static class InferenceResult {
        public final String label;
        public final float confidence;
        public final float[] allProbabilities;

        public InferenceResult(String label, float confidence, float[] allProbabilities) {
            this.label            = label;
            this.confidence       = confidence;
            this.allProbabilities = allProbabilities;
        }
    }
}
