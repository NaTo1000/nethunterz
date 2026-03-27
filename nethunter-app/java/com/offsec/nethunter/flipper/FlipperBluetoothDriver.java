package com.offsec.nethunter.flipper;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothSocket;
import android.content.Context;
import android.util.Log;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Bluetooth Classic and BLE driver for Flipper Zero communication.
 * Flipper Zero uses Bluetooth Classic SPP for primary CLI communication.
 * BLE is used for companion app-style RPC.
 */
public class FlipperBluetoothDriver implements FlipperTransport {

    private static final String TAG = "FlipperBluetoothDriver";

    // SPP UUID for Bluetooth Classic serial communication
    private static final UUID SPP_UUID =
        UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    // Flipper Zero BLE Serial service UUID
    private static final UUID FLIPPER_BLE_SERVICE_UUID =
        UUID.fromString("3082D784-0D6B-4C31-8290-B53B54E7A256");
    private static final UUID FLIPPER_BLE_CHAR_RX_UUID =
        UUID.fromString("19ED82AE-ED21-4C9D-4145-228E62FE0000");
    private static final UUID FLIPPER_BLE_CHAR_TX_UUID =
        UUID.fromString("19ED82AE-ED21-4C9D-4145-228E62FE0001");

    private static final String FLIPPER_DEVICE_NAME_PREFIX = "Flipper ";
    private static final int    CONNECT_TIMEOUT_MS = 10000;
    private static final int    READ_TIMEOUT_MS    = 5000;
    private static final int    BUFFER_SIZE        = 4096;

    private final Context context;
    private final BluetoothAdapter bluetoothAdapter;
    private BluetoothSocket socket;
    private InputStream inputStream;
    private OutputStream outputStream;
    private BluetoothGatt bleGatt;
    private boolean useBle = false;

    private final AtomicBoolean connected = new AtomicBoolean(false);
    private final byte[] readBuffer = new byte[BUFFER_SIZE];

    public FlipperBluetoothDriver(Context context) {
        this.context = context;
        this.bluetoothAdapter = BluetoothAdapter.getDefaultAdapter();
    }

    /**
     * Connect to Flipper Zero via Bluetooth.
     * @param deviceAddress Optional MAC address; if null, will scan paired devices.
     */
    @Override
    public boolean connect() {
        return connect(null);
    }

    public boolean connect(String deviceAddress) {
        if (bluetoothAdapter == null || !bluetoothAdapter.isEnabled()) {
            Log.d(TAG, "Bluetooth not available or disabled");
            return false;
        }

        BluetoothDevice device = resolveDevice(deviceAddress);
        if (device == null) {
            Log.d(TAG, "Flipper Zero not found in paired devices");
            return false;
        }

        Log.i(TAG, "Connecting to Flipper via Bluetooth: " + device.getName()
            + " [" + device.getAddress() + "]");
        return connectClassic(device);
    }

    private BluetoothDevice resolveDevice(String address) {
        if (address != null && !address.isEmpty()) {
            return bluetoothAdapter.getRemoteDevice(address);
        }
        // Search paired devices for Flipper
        Set<BluetoothDevice> pairedDevices = bluetoothAdapter.getBondedDevices();
        for (BluetoothDevice dev : pairedDevices) {
            String name = dev.getName();
            if (name != null && name.startsWith(FLIPPER_DEVICE_NAME_PREFIX)) {
                Log.d(TAG, "Found paired Flipper: " + name);
                return dev;
            }
        }
        return null;
    }

    private boolean connectClassic(BluetoothDevice device) {
        try {
            // Cancel discovery to improve connection reliability
            if (bluetoothAdapter.isDiscovering()) {
                bluetoothAdapter.cancelDiscovery();
            }

            socket = device.createRfcommSocketToServiceRecord(SPP_UUID);
            socket.connect();

            inputStream  = socket.getInputStream();
            outputStream = socket.getOutputStream();
            connected.set(true);

            Log.i(TAG, "Bluetooth Classic SPP connected to " + device.getName());
            return true;

        } catch (IOException e) {
            Log.w(TAG, "SPP connect failed, trying fallback method: " + e.getMessage());
            return connectClassicFallback(device);
        }
    }

    private boolean connectClassicFallback(BluetoothDevice device) {
        try {
            // Fallback: use reflection to get the socket via channel 1
            socket = (BluetoothSocket) device.getClass()
                .getMethod("createRfcommSocket", new Class[]{int.class})
                .invoke(device, 1);
            socket.connect();

            inputStream  = socket.getInputStream();
            outputStream = socket.getOutputStream();
            connected.set(true);

            Log.i(TAG, "Bluetooth Classic fallback connected to " + device.getName());
            return true;
        } catch (Exception e) {
            Log.e(TAG, "Bluetooth fallback connect failed: " + e.getMessage());
            return false;
        }
    }

    @Override
    public void disconnect() {
        connected.set(false);
        try {
            if (inputStream != null)  inputStream.close();
            if (outputStream != null) outputStream.close();
            if (socket != null)       socket.close();
            if (bleGatt != null) {
                bleGatt.disconnect();
                bleGatt.close();
            }
        } catch (IOException e) {
            Log.w(TAG, "Error during Bluetooth disconnect: " + e.getMessage());
        } finally {
            socket      = null;
            inputStream = null;
            outputStream = null;
            bleGatt     = null;
        }
        Log.i(TAG, "Bluetooth disconnected");
    }

    @Override
    public void write(byte[] data) throws IOException {
        if (!connected.get() || outputStream == null) {
            throw new IOException("Bluetooth not connected");
        }
        outputStream.write(data);
        outputStream.flush();
    }

    @Override
    public byte[] read(int maxBytes) throws IOException {
        if (!connected.get() || inputStream == null) {
            throw new IOException("Bluetooth not connected");
        }
        int toRead = Math.min(maxBytes, BUFFER_SIZE);
        byte[] buffer = new byte[toRead];
        int bytesRead = inputStream.read(buffer, 0, toRead);
        if (bytesRead <= 0) return new byte[0];
        byte[] result = new byte[bytesRead];
        System.arraycopy(buffer, 0, result, 0, bytesRead);
        return result;
    }

    @Override
    public byte[] readUntil(byte terminator, int maxBytes) throws IOException {
        if (!connected.get() || inputStream == null) {
            throw new IOException("Bluetooth not connected");
        }
        byte[] accumulator = new byte[maxBytes];
        int pos = 0;
        long deadline = System.currentTimeMillis() + READ_TIMEOUT_MS;

        while (pos < maxBytes) {
            if (System.currentTimeMillis() > deadline) {
                throw new IOException("Bluetooth read timeout");
            }
            int available = inputStream.available();
            if (available > 0) {
                int b = inputStream.read();
                if (b < 0) break;
                accumulator[pos++] = (byte) b;
                if ((byte) b == terminator) break;
            } else {
                try { Thread.sleep(10); } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }

        byte[] result = new byte[pos];
        System.arraycopy(accumulator, 0, result, 0, pos);
        return result;
    }

    @Override
    public void flush() throws IOException {
        if (outputStream != null) outputStream.flush();
    }

    @Override
    public boolean isConnected() {
        return connected.get() && socket != null && socket.isConnected();
    }

    @Override
    public String getTransportType() {
        return "Bluetooth";
    }

    public boolean isBleMode() { return useBle; }
}
