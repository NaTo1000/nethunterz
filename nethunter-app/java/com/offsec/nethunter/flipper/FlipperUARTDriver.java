package com.offsec.nethunter.flipper;

import android.util.Log;

import com.offsec.nethunter.utils.SystemUtils;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * UART serial communication driver for the Flipper Zero.
 * Uses /dev/ttyACM0 (or /dev/ttyUSB0 as fallback) at 115200 baud.
 * Requires root access to open the serial port.
 */
public class FlipperUARTDriver implements FlipperTransport {

    private static final String TAG = "FlipperUARTDriver";
    public static final int    BAUD_RATE   = 115200;
    public static final int    DATA_BITS   = 8;
    public static final int    STOP_BITS   = 1;
    public static final int    READ_TIMEOUT_MS  = 3000;
    public static final int    WRITE_TIMEOUT_MS = 2000;
    public static final int    BUFFER_SIZE = 4096;

    private FileInputStream  inputStream;
    private FileOutputStream outputStream;
    private String devicePath;
    private final AtomicBoolean connected = new AtomicBoolean(false);
    private Process sttyProcess;

    public FlipperUARTDriver() {
        this.devicePath = SystemUtils.FLIPPER_UART_DEV;
    }

    public FlipperUARTDriver(String devicePath) {
        this.devicePath = devicePath;
    }

    @Override
    public boolean connect() {
        // Resolve device path
        String resolvedPath = SystemUtils.getFlipperUartDevice();
        if (resolvedPath == null) {
            Log.d(TAG, "No UART device found at " + SystemUtils.FLIPPER_UART_DEV
                + " or " + SystemUtils.FLIPPER_UART_DEV_ALT);
            return false;
        }
        devicePath = resolvedPath;

        try {
            // Set permissions on the device node
            SystemUtils.CommandResult permResult =
                SystemUtils.runAsRoot("chmod 666 " + devicePath);
            if (!permResult.isSuccess()) {
                Log.w(TAG, "Could not set permissions on " + devicePath);
            }

            // Configure serial port with stty
            configureSerialPort();

            // Open the device
            File dev = new File(devicePath);
            if (!dev.exists()) {
                Log.w(TAG, "Device " + devicePath + " does not exist");
                return false;
            }

            inputStream  = new FileInputStream(dev);
            outputStream = new FileOutputStream(dev);
            connected.set(true);
            Log.i(TAG, "UART connected to " + devicePath + " at " + BAUD_RATE + " baud");
            return true;

        } catch (IOException e) {
            Log.e(TAG, "Failed to open UART device " + devicePath, e);
            cleanup();
            return false;
        }
    }

    /**
     * Configure the serial port using stty command.
     */
    private void configureSerialPort() {
        String sttyCmd = String.format(
            "stty -F %s %d cs8 -cstopb -parenb raw -echo -echoe -echok -echoctl -echoke",
            devicePath, BAUD_RATE
        );
        SystemUtils.CommandResult result = SystemUtils.runAsRoot(sttyCmd);
        if (result.isSuccess()) {
            Log.d(TAG, "Serial port configured: " + BAUD_RATE + " baud, 8N1");
        } else {
            Log.w(TAG, "stty configuration failed: " + result.stderr);
        }
    }

    @Override
    public void disconnect() {
        cleanup();
        Log.i(TAG, "UART disconnected");
    }

    private void cleanup() {
        connected.set(false);
        if (inputStream != null) {
            try { inputStream.close(); } catch (IOException e) { /* ignored */ }
            inputStream = null;
        }
        if (outputStream != null) {
            try { outputStream.close(); } catch (IOException e) { /* ignored */ }
            outputStream = null;
        }
    }

    @Override
    public void write(byte[] data) throws IOException {
        if (!connected.get() || outputStream == null) {
            throw new IOException("UART not connected");
        }
        outputStream.write(data);
        outputStream.flush();
    }

    @Override
    public byte[] read(int maxBytes) throws IOException {
        if (!connected.get() || inputStream == null) {
            throw new IOException("UART not connected");
        }
        byte[] buffer = new byte[Math.min(maxBytes, BUFFER_SIZE)];
        int bytesRead = inputStream.read(buffer);
        if (bytesRead <= 0) return new byte[0];
        byte[] result = new byte[bytesRead];
        System.arraycopy(buffer, 0, result, 0, bytesRead);
        return result;
    }

    @Override
    public byte[] readUntil(byte terminator, int maxBytes) throws IOException {
        if (!connected.get() || inputStream == null) {
            throw new IOException("UART not connected");
        }
        byte[] buffer = new byte[Math.min(maxBytes, BUFFER_SIZE)];
        int pos = 0;
        long deadline = System.currentTimeMillis() + READ_TIMEOUT_MS;

        while (pos < buffer.length) {
            if (System.currentTimeMillis() > deadline) {
                throw new IOException("Read timeout after " + READ_TIMEOUT_MS + "ms");
            }
            int available = inputStream.available();
            if (available > 0) {
                int b = inputStream.read();
                if (b < 0) break;
                buffer[pos++] = (byte) b;
                if ((byte) b == terminator) break;
            } else {
                try { Thread.sleep(5); } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }

        byte[] result = new byte[pos];
        System.arraycopy(buffer, 0, result, 0, pos);
        return result;
    }

    @Override
    public boolean isConnected() {
        return connected.get() && inputStream != null;
    }

    @Override
    public String getTransportType() {
        return "UART";
    }

    public String getDevicePath() {
        return devicePath;
    }

    public int getBaudRate() {
        return BAUD_RATE;
    }

    @Override
    public void flush() throws IOException {
        if (outputStream != null) {
            outputStream.flush();
        }
    }
}
