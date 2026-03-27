package com.offsec.nethunter.flipper;

import android.content.Context;
import android.util.Log;

import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Central manager for Flipper Zero board communication.
 * Coordinates between USB, UART, and Bluetooth connection methods.
 */
public class FlipperManager {

    private static final String TAG = "FlipperManager";

    public enum ConnectionType { NONE, USB, UART, BLUETOOTH }
    public enum ConnectionState { DISCONNECTED, CONNECTING, CONNECTED, ERROR }

    private final Context context;
    private final AtomicBoolean connected = new AtomicBoolean(false);
    private final AtomicReference<ConnectionType> activeConnectionType =
        new AtomicReference<>(ConnectionType.NONE);
    private final AtomicReference<ConnectionState> state =
        new AtomicReference<>(ConnectionState.DISCONNECTED);

    private FlipperUSBDriver usbDriver;
    private FlipperUARTDriver uartDriver;
    private FlipperBluetoothDriver bluetoothDriver;
    private FlipperProtocol protocol;

    private final CopyOnWriteArrayList<ConnectionListener> listeners = new CopyOnWriteArrayList<>();

    public interface ConnectionListener {
        void onConnected(ConnectionType type);
        void onDisconnected(ConnectionType type);
        void onConnectionError(ConnectionType type, String error);
        void onDataReceived(byte[] data);
    }

    public FlipperManager(Context context) {
        this.context = context;
        usbDriver       = new FlipperUSBDriver(context);
        uartDriver      = new FlipperUARTDriver();
        bluetoothDriver = new FlipperBluetoothDriver(context);
        protocol        = new FlipperProtocol();
    }

    public void addConnectionListener(ConnectionListener listener) {
        listeners.add(listener);
    }

    public void removeConnectionListener(ConnectionListener listener) {
        listeners.remove(listener);
    }

    /**
     * Try to auto-connect using all available methods in priority order:
     * USB > UART > Bluetooth
     * @return true if connection was established
     */
    public boolean tryAutoConnect() {
        if (connected.get()) return true;

        Log.d(TAG, "Attempting auto-connect to Flipper Zero");
        state.set(ConnectionState.CONNECTING);

        // Try USB first (most reliable)
        if (tryConnect(ConnectionType.USB)) return true;

        // Try UART (direct serial)
        if (tryConnect(ConnectionType.UART)) return true;

        // Try Bluetooth last
        if (tryConnect(ConnectionType.BLUETOOTH)) return true;

        state.set(ConnectionState.DISCONNECTED);
        Log.d(TAG, "Auto-connect failed - no Flipper device found");
        return false;
    }

    private boolean tryConnect(ConnectionType type) {
        try {
            boolean result;
            switch (type) {
                case USB:
                    result = usbDriver.connect();
                    if (result) {
                        protocol.setTransport(usbDriver);
                    }
                    break;
                case UART:
                    result = uartDriver.connect();
                    if (result) {
                        protocol.setTransport(uartDriver);
                    }
                    break;
                case BLUETOOTH:
                    result = bluetoothDriver.connect(null);
                    if (result) {
                        protocol.setTransport(bluetoothDriver);
                    }
                    break;
                default:
                    return false;
            }

            if (result) {
                connected.set(true);
                activeConnectionType.set(type);
                state.set(ConnectionState.CONNECTED);
                notifyConnected(type);
                Log.i(TAG, "Connected to Flipper via " + type);
                return true;
            }
        } catch (Exception e) {
            Log.w(TAG, "Connection attempt failed for " + type + ": " + e.getMessage());
            notifyError(type, e.getMessage());
        }
        return false;
    }

    /**
     * Connect using a specific connection type.
     */
    public boolean connect(ConnectionType type) {
        if (connected.get()) {
            if (activeConnectionType.get() == type) return true;
            disconnect();
        }
        return tryConnect(type);
    }

    /**
     * Disconnect from the Flipper device.
     */
    public void disconnect() {
        if (!connected.get()) return;

        ConnectionType type = activeConnectionType.get();
        try {
            switch (type) {
                case USB:       usbDriver.disconnect(); break;
                case UART:      uartDriver.disconnect(); break;
                case BLUETOOTH: bluetoothDriver.disconnect(); break;
                default: break;
            }
        } catch (Exception e) {
            Log.w(TAG, "Error during disconnect: " + e.getMessage());
        }

        connected.set(false);
        activeConnectionType.set(ConnectionType.NONE);
        state.set(ConnectionState.DISCONNECTED);
        notifyDisconnected(type);
        Log.i(TAG, "Disconnected from Flipper");
    }

    /**
     * Send a raw command to the Flipper and return the response.
     */
    public byte[] sendCommand(byte[] command) throws Exception {
        if (!connected.get()) {
            throw new IllegalStateException("Not connected to Flipper device");
        }
        return protocol.sendCommand(command);
    }

    /**
     * Send a text CLI command to the Flipper and return string response.
     */
    public String sendCliCommand(String command) throws Exception {
        if (!connected.get()) {
            throw new IllegalStateException("Not connected to Flipper device");
        }
        return protocol.sendCliCommand(command);
    }

    /**
     * Get the Flipper firmware version.
     */
    public String getFirmwareVersion() {
        try {
            return protocol.getFirmwareVersion();
        } catch (Exception e) {
            Log.e(TAG, "Error getting firmware version", e);
            return "unknown";
        }
    }

    /**
     * Start firmware update process via the active connection.
     */
    public boolean startFirmwareUpdate(String firmwarePath) {
        try {
            FirmwareUpdater updater = new FirmwareUpdater(context);
            return updater.startUpdate(firmwarePath, protocol);
        } catch (Exception e) {
            Log.e(TAG, "Firmware update failed", e);
            return false;
        }
    }

    // Notification helpers
    private void notifyConnected(ConnectionType type) {
        for (ConnectionListener l : listeners) {
            try { l.onConnected(type); } catch (Exception e) { Log.w(TAG, "Listener error", e); }
        }
    }

    private void notifyDisconnected(ConnectionType type) {
        for (ConnectionListener l : listeners) {
            try { l.onDisconnected(type); } catch (Exception e) { Log.w(TAG, "Listener error", e); }
        }
    }

    private void notifyError(ConnectionType type, String error) {
        for (ConnectionListener l : listeners) {
            try { l.onConnectionError(type, error); } catch (Exception e) { Log.w(TAG, "Listener error", e); }
        }
    }

    // Getters
    public boolean isConnected()             { return connected.get(); }
    public ConnectionType getConnectionType() { return activeConnectionType.get(); }
    public ConnectionState getState()        { return state.get(); }
    public FlipperProtocol getProtocol()     { return protocol; }
}
