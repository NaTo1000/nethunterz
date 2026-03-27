package com.offsec.nethunter.ai;

import android.content.Context;
import android.util.Log;

import com.offsec.nethunter.flipper.FlipperManager;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * AI autonomous decision-making controller.
 * Monitors system state and issues commands to the Flipper Zero board
 * based on ML model inference and rule-based logic.
 */
public class AIController {

    private static final String TAG = "AIController";

    public enum AIMode { PASSIVE, ACTIVE, AUTONOMOUS }
    public enum SystemState { IDLE, SCANNING, ANALYZING, EXECUTING, LEARNING }

    private final Context context;
    private final FlipperManager flipperManager;
    private final MLModelManager modelManager;
    private final DecisionEngine decisionEngine;

    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(2);
    private ScheduledFuture<?> monitorTask;
    private final AtomicBoolean aiEnabled = new AtomicBoolean(false);

    private AIMode currentMode = AIMode.PASSIVE;
    private SystemState systemState = SystemState.IDLE;

    private final Map<String, Object> systemContext = new HashMap<>();
    private long decisionCount = 0;
    private long actionsTaken = 0;

    private static final int MONITOR_INTERVAL_MS = 2000;
    private static final float CONFIDENCE_THRESHOLD = 0.75f;

    public interface AIListener {
        void onDecisionMade(String decision, float confidence);
        void onActionExecuted(String action, boolean success);
        void onStateChanged(SystemState state);
        void onError(String error);
    }

    private AIListener listener;

    public AIController(Context context, FlipperManager flipperManager) {
        this.context       = context;
        this.flipperManager = flipperManager;
        this.modelManager  = new MLModelManager(context);
        this.decisionEngine = new DecisionEngine(context);
    }

    public void setListener(AIListener listener) {
        this.listener = listener;
    }

    /**
     * Initialize AI subsystem: load models and rules.
     */
    public boolean initialize() {
        try {
            Log.i(TAG, "Initializing AI controller");
            boolean modelsLoaded = modelManager.loadModels();
            boolean rulesLoaded  = decisionEngine.loadRules();

            if (!modelsLoaded) {
                Log.w(TAG, "ML models not available, falling back to rule-based mode only");
            }

            Log.i(TAG, "AI initialized: models=" + modelsLoaded + " rules=" + rulesLoaded);
            return rulesLoaded; // Minimum requirement is rule engine
        } catch (Exception e) {
            Log.e(TAG, "AI initialization failed", e);
            return false;
        }
    }

    /**
     * Start the autonomous monitoring loop.
     */
    public void startAutonomousMode() {
        if (aiEnabled.getAndSet(true)) {
            Log.w(TAG, "AI already running");
            return;
        }
        currentMode = AIMode.AUTONOMOUS;
        monitorTask = scheduler.scheduleWithFixedDelay(
            this::monitorAndDecide,
            0, MONITOR_INTERVAL_MS, TimeUnit.MILLISECONDS
        );
        Log.i(TAG, "Autonomous AI mode started");
    }

    /**
     * Stop autonomous monitoring.
     */
    public void stopAutonomousMode() {
        aiEnabled.set(false);
        currentMode = AIMode.PASSIVE;
        if (monitorTask != null) {
            monitorTask.cancel(false);
            monitorTask = null;
        }
        Log.i(TAG, "Autonomous AI mode stopped");
    }

    /**
     * Core monitoring and decision loop.
     */
    private void monitorAndDecide() {
        try {
            // Collect current system state
            updateSystemContext();
            setSystemState(SystemState.ANALYZING);

            // Get decision from the decision engine
            DecisionEngine.Decision decision = decisionEngine.evaluate(systemContext);
            decisionCount++;

            Log.d(TAG, "Decision: " + decision.action
                + " confidence=" + String.format("%.2f", decision.confidence)
                + " source=" + decision.source);

            if (listener != null) {
                listener.onDecisionMade(decision.action, decision.confidence);
            }

            // Execute action if confidence meets threshold
            if (decision.confidence >= CONFIDENCE_THRESHOLD
                    && !DecisionEngine.Action.NONE.name().equals(decision.action)) {
                setSystemState(SystemState.EXECUTING);
                boolean success = executeAction(decision);
                actionsTaken++;

                if (listener != null) {
                    listener.onActionExecuted(decision.action, success);
                }
                Log.i(TAG, "Action executed: " + decision.action + " success=" + success);
            }

            setSystemState(SystemState.IDLE);

        } catch (Exception e) {
            Log.e(TAG, "Error in AI monitor loop", e);
            setSystemState(SystemState.IDLE);
            if (listener != null) {
                listener.onError(e.getMessage());
            }
        }
    }

    /**
     * Collect current system context for decision making.
     */
    private void updateSystemContext() {
        systemContext.put("flipper_connected", flipperManager.isConnected());
        systemContext.put("connection_type",
            flipperManager.getConnectionType().name());
        systemContext.put("timestamp", System.currentTimeMillis());
        systemContext.put("decision_count", decisionCount);
        systemContext.put("actions_taken", actionsTaken);

        // Add ML model features if available
        if (modelManager.isModelLoaded()) {
            float[] features = collectModelFeatures();
            float[] predictions = modelManager.runInference(features);
            if (predictions != null) {
                systemContext.put("ml_predictions", predictions);
                systemContext.put("ml_confidence", findMaxConfidence(predictions));
            }
        }
    }

    private float[] collectModelFeatures() {
        return new float[]{
            flipperManager.isConnected() ? 1.0f : 0.0f,
            flipperManager.getConnectionType().ordinal() / 3.0f,
            (float) (System.currentTimeMillis() % 86400000) / 86400000.0f,
            (float) decisionCount / Math.max(1, decisionCount + 1),
            actionsTaken > 0 ? 1.0f : 0.0f,
            systemState.ordinal() / 4.0f,
            (float) Math.random() * 0.1f // small random noise
        };
    }

    private float findMaxConfidence(float[] predictions) {
        float max = 0f;
        for (float p : predictions) max = Math.max(max, p);
        return max;
    }

    /**
     * Execute the decided action on the Flipper.
     */
    private boolean executeAction(DecisionEngine.Decision decision) {
        if (!flipperManager.isConnected()) {
            if (DecisionEngine.Action.CONNECT_FLIPPER.name().equals(decision.action)) {
                return flipperManager.tryAutoConnect();
            }
            Log.d(TAG, "Cannot execute action - Flipper not connected");
            return false;
        }

        try {
            switch (decision.action) {
                case "SEND_PING":
                    return flipperManager.getProtocol().ping();
                case "GET_VERSION":
                    String version = flipperManager.getFirmwareVersion();
                    systemContext.put("firmware_version", version);
                    return version != null && !version.isEmpty();
                case "CHECK_STORAGE":
                    flipperManager.sendCliCommand("storage info /");
                    return true;
                case "RUN_BADUSB":
                    if (Boolean.TRUE.equals(decision.params.get("authorized"))) {
                        flipperManager.sendCliCommand("badusb run " + decision.params.get("script"));
                        return true;
                    }
                    Log.w(TAG, "BadUSB action not authorized");
                    return false;
                case "DISCONNECT":
                    flipperManager.disconnect();
                    return true;
                default:
                    Log.d(TAG, "Unknown action: " + decision.action);
                    return false;
            }
        } catch (Exception e) {
            Log.e(TAG, "Action execution failed: " + decision.action, e);
            return false;
        }
    }

    private void setSystemState(SystemState state) {
        if (this.systemState != state) {
            this.systemState = state;
            if (listener != null) {
                listener.onStateChanged(state);
            }
        }
    }

    /**
     * Manually trigger a single AI decision cycle.
     */
    public DecisionEngine.Decision makeDecision() {
        updateSystemContext();
        return decisionEngine.evaluate(systemContext);
    }

    public void shutdown() {
        stopAutonomousMode();
        scheduler.shutdownNow();
        modelManager.close();
    }

    // Getters
    public AIMode getMode()            { return currentMode; }
    public SystemState getState()      { return systemState; }
    public boolean isEnabled()         { return aiEnabled.get(); }
    public long getDecisionCount()     { return decisionCount; }
    public long getActionsTaken()      { return actionsTaken; }
    public MLModelManager getModelManager() { return modelManager; }
}
