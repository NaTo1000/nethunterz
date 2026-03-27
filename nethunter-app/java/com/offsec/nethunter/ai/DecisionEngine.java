package com.offsec.nethunter.ai;

import android.content.Context;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Hybrid rule-based + ML decision engine for Flipper Zero autonomous control.
 * Rules are loaded from assets/rules.json and evaluated against system context.
 */
public class DecisionEngine {

    private static final String TAG = "DecisionEngine";

    public enum Action {
        NONE, CONNECT_FLIPPER, DISCONNECT, SEND_PING,
        GET_VERSION, CHECK_STORAGE, RUN_BADUSB, RESTART_SERVICE
    }

    public static class Decision {
        public final String  action;
        public final float   confidence;
        public final String  source; // "rule" or "ml"
        public final String  ruleId;
        public final Map<String, Object> params;

        public Decision(String action, float confidence, String source, String ruleId) {
            this.action     = action;
            this.confidence = confidence;
            this.source     = source;
            this.ruleId     = ruleId;
            this.params     = new HashMap<>();
        }

        @Override
        public String toString() {
            return "Decision{action=" + action + " conf=" + confidence
                + " src=" + source + " rule=" + ruleId + "}";
        }
    }

    private static class Rule {
        final String  id;
        final String  condition;
        final String  action;
        final float   priority;
        final Map<String, Object> params;
        boolean enabled;

        Rule(String id, String condition, String action, float priority, boolean enabled) {
            this.id        = id;
            this.condition = condition;
            this.action    = action;
            this.priority  = priority;
            this.enabled   = enabled;
            this.params    = new HashMap<>();
        }
    }

    private final Context context;
    private final List<Rule> rules = new ArrayList<>();
    private boolean rulesLoaded = false;
    private int evaluationCount = 0;

    private static final String RULES_ASSET = "rules.json";

    public DecisionEngine(Context context) {
        this.context = context;
    }

    /**
     * Load rules from assets/rules.json.
     */
    public boolean loadRules() {
        try {
            InputStream is;
            try {
                is = context.getAssets().open(RULES_ASSET);
            } catch (Exception e) {
                Log.d(TAG, "rules.json not found in assets, using built-in rules");
                loadBuiltInRules();
                rulesLoaded = true;
                return true;
            }

            byte[] bytes = new byte[is.available()];
            is.read(bytes);
            is.close();

            String json = new String(bytes, StandardCharsets.UTF_8);
            parseRules(json);
            rulesLoaded = true;
            Log.i(TAG, "Loaded " + rules.size() + " rules from assets");
            return true;

        } catch (Exception e) {
            Log.e(TAG, "Error loading rules", e);
            loadBuiltInRules();
            rulesLoaded = true;
            return true;
        }
    }

    private void parseRules(String json) throws Exception {
        JSONArray rulesArray = new JSONArray(json);
        for (int i = 0; i < rulesArray.length(); i++) {
            JSONObject obj = rulesArray.getJSONObject(i);
            Rule rule = new Rule(
                obj.getString("id"),
                obj.getString("condition"),
                obj.getString("action"),
                (float) obj.optDouble("priority", 0.5),
                obj.optBoolean("enabled", true)
            );

            // Parse optional params
            if (obj.has("params")) {
                JSONObject paramsObj = obj.getJSONObject("params");
                for (java.util.Iterator<String> keys = paramsObj.keys(); keys.hasNext(); ) {
                    String key = keys.next();
                    rule.params.put(key, paramsObj.get(key));
                }
            }
            rules.add(rule);
        }
    }

    private void loadBuiltInRules() {
        rules.clear();
        // Rule: Connect to Flipper if not connected
        rules.add(createRule("r001", "flipper_not_connected", "CONNECT_FLIPPER", 0.9f));
        // Rule: Ping if connected but no recent activity
        rules.add(createRule("r002", "flipper_idle", "SEND_PING", 0.6f));
        // Rule: Get version after connecting
        rules.add(createRule("r003", "version_unknown", "GET_VERSION", 0.7f));
        // Rule: Check storage periodically
        rules.add(createRule("r004", "periodic_check", "CHECK_STORAGE", 0.4f));
        // Rule: Disconnect on error
        rules.add(createRule("r005", "connection_error", "DISCONNECT", 0.95f));
    }

    private Rule createRule(String id, String condition, String action, float priority) {
        return new Rule(id, condition, action, priority, true);
    }

    /**
     * Evaluate all rules against the current system context.
     * Returns the highest-priority matching decision.
     */
    public Decision evaluate(Map<String, Object> context) {
        evaluationCount++;
        Decision best = new Decision(Action.NONE.name(), 0.0f, "none", "");

        // Check ML predictions if available
        float[] mlPredictions = (float[]) context.get("ml_predictions");
        Float   mlConfidence  = (Float) context.get("ml_confidence");

        for (Rule rule : rules) {
            if (!rule.enabled) continue;
            float matchScore = evaluateCondition(rule.condition, context);
            if (matchScore > 0 && matchScore > best.confidence) {
                Decision d = new Decision(rule.action, matchScore, "rule", rule.id);
                d.params.putAll(rule.params);
                best = d;
            }
        }

        // If ML has higher confidence, override rule decision
        if (mlPredictions != null && mlConfidence != null
                && mlConfidence > best.confidence + 0.1f) {
            String mlAction = inferActionFromPredictions(mlPredictions);
            best = new Decision(mlAction, mlConfidence, "ml", "ml_model");
        }

        Log.d(TAG, "Evaluation #" + evaluationCount + " -> " + best);
        return best;
    }

    /**
     * Evaluate a condition string against the context.
     * Returns a score in [0, 1] (0 = no match, >0 = match strength).
     */
    private float evaluateCondition(String condition, Map<String, Object> ctx) {
        try {
            Boolean flipperConnected = getBool(ctx, "flipper_connected");
            String  connectionType   = getString(ctx, "connection_type", "NONE");
            Long    decisionCount    = getLong(ctx, "decision_count");

            switch (condition) {
                case "flipper_not_connected":
                    return flipperConnected != null && !flipperConnected ? 0.9f : 0.0f;

                case "flipper_idle":
                    if (flipperConnected != null && flipperConnected) {
                        long count = decisionCount != null ? decisionCount : 0;
                        // Ping every ~10 decisions when idle
                        return (count % 10 == 0) ? 0.6f : 0.0f;
                    }
                    return 0.0f;

                case "version_unknown":
                    boolean hasVersion = ctx.containsKey("firmware_version");
                    return (flipperConnected != null && flipperConnected && !hasVersion) ? 0.7f : 0.0f;

                case "periodic_check":
                    long cnt = decisionCount != null ? decisionCount : 0;
                    return (cnt % 30 == 0) ? 0.4f : 0.0f;

                case "connection_error":
                    return (flipperConnected != null && !flipperConnected
                        && decisionCount != null && decisionCount > 5) ? 0.2f : 0.0f;

                default:
                    return 0.0f;
            }
        } catch (Exception e) {
            Log.w(TAG, "Condition evaluation error for '" + condition + "': " + e.getMessage());
            return 0.0f;
        }
    }

    private String inferActionFromPredictions(float[] predictions) {
        String[] labels = MLModelManager.ACTION_LABELS;
        int maxIdx = 0;
        for (int i = 1; i < predictions.length && i < labels.length; i++) {
            if (predictions[i] > predictions[maxIdx]) maxIdx = i;
        }
        return maxIdx < labels.length ? labels[maxIdx] : Action.NONE.name();
    }

    // Context helpers
    private Boolean getBool(Map<String, Object> ctx, String key) {
        Object v = ctx.get(key);
        if (v instanceof Boolean) return (Boolean) v;
        return null;
    }

    private String getString(Map<String, Object> ctx, String key, String def) {
        Object v = ctx.get(key);
        return v != null ? v.toString() : def;
    }

    private Long getLong(Map<String, Object> ctx, String key) {
        Object v = ctx.get(key);
        if (v instanceof Long)    return (Long) v;
        if (v instanceof Integer) return ((Integer) v).longValue();
        return null;
    }

    public boolean isRulesLoaded()  { return rulesLoaded; }
    public int getRuleCount()        { return rules.size(); }
    public int getEvaluationCount() { return evaluationCount; }
}
