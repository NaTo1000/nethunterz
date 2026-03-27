package com.offsec.nethunter.flipper;

import android.content.Context;
import android.hardware.usb.UsbConstants;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbEndpoint;
import android.hardware.usb.UsbInterface;
import android.hardware.usb.UsbManager;
import android.util.Log;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * USB CDC/HID driver for the Flipper Zero board.
 * Uses Android's USB Host API for direct USB communication.
 *
 * Flipper Zero USB identifiers:
 *   VID: 0x0483 (STMicroelectronics)
 *   PID: 0x5740 (Virtual COM Port - CDC)
 */
public class FlipperUSBDriver implements FlipperTransport {

    private static final String TAG = "FlipperUSBDriver";

    public static final int FLIPPER_VID          = 0x0483;
    public static final int FLIPPER_PID_CDC      = 0x5740;
    public static final int FLIPPER_PID_DFU      = 0xDF11;
    public static final int USB_TIMEOUT_MS       = 3000;
    public static final int BULK_TRANSFER_SIZE   = 4096;

    private final Context context;
    private final UsbManager usbManager;
    private UsbDevice device;
    private UsbDeviceConnection connection;
    private UsbEndpoint endpointIn;
    private UsbEndpoint endpointOut;
    private UsbInterface usbInterface;

    private final AtomicBoolean connected = new AtomicBoolean(false);

    public FlipperUSBDriver(Context context) {
        this.context    = context;
        this.usbManager = (UsbManager) context.getSystemService(Context.USB_SERVICE);
    }

    @Override
    public boolean connect() {
        if (usbManager == null) {
            Log.e(TAG, "USB Manager not available");
            return false;
        }

        // Find Flipper Zero in connected USB devices
        HashMap<String, UsbDevice> deviceMap = usbManager.getDeviceList();
        UsbDevice flipper = findFlipperDevice(deviceMap);

        if (flipper == null) {
            Log.d(TAG, "No Flipper Zero USB device found");
            return false;
        }

        // Check if we have permission
        if (!usbManager.hasPermission(flipper)) {
            Log.d(TAG, "No USB permission for Flipper device");
            return false;
        }

        return connectToDevice(flipper);
    }

    /**
     * Connect to a specific UsbDevice (called from USB permission grant callback).
     */
    public boolean connectToDevice(UsbDevice usbDevice) {
        this.device = usbDevice;
        Log.i(TAG, "Connecting to Flipper USB device: " + usbDevice.getDeviceName()
            + " VID=0x" + Integer.toHexString(usbDevice.getVendorId())
            + " PID=0x" + Integer.toHexString(usbDevice.getProductId()));

        // Find CDC Data interface (interface class 0x0A)
        UsbInterface cdcInterface = findCdcDataInterface(usbDevice);
        if (cdcInterface == null) {
            // Fallback: use first interface with bulk endpoints
            cdcInterface = findBulkInterface(usbDevice);
        }
        if (cdcInterface == null) {
            Log.e(TAG, "No suitable USB interface found");
            return false;
        }
        usbInterface = cdcInterface;

        // Find IN and OUT bulk endpoints
        for (int i = 0; i < usbInterface.getEndpointCount(); i++) {
            UsbEndpoint ep = usbInterface.getEndpoint(i);
            if (ep.getType() == UsbConstants.USB_ENDPOINT_XFER_BULK) {
                if (ep.getDirection() == UsbConstants.USB_DIR_IN) {
                    endpointIn = ep;
                } else {
                    endpointOut = ep;
                }
            }
        }

        if (endpointIn == null || endpointOut == null) {
            Log.e(TAG, "Could not find bulk IN/OUT endpoints");
            return false;
        }

        // Open the connection
        connection = usbManager.openDevice(usbDevice);
        if (connection == null) {
            Log.e(TAG, "Failed to open USB connection");
            return false;
        }

        if (!connection.claimInterface(usbInterface, true)) {
            Log.e(TAG, "Failed to claim USB interface");
            connection.close();
            connection = null;
            return false;
        }

        connected.set(true);
        Log.i(TAG, "USB connection established - IN ep: 0x"
            + Integer.toHexString(endpointIn.getEndpointNumber())
            + " OUT ep: 0x" + Integer.toHexString(endpointOut.getEndpointNumber()));
        return true;
    }

    private UsbDevice findFlipperDevice(Map<String, UsbDevice> devices) {
        for (UsbDevice dev : devices.values()) {
            if (dev.getVendorId() == FLIPPER_VID
                    && (dev.getProductId() == FLIPPER_PID_CDC
                        || dev.getProductId() == FLIPPER_PID_DFU)) {
                Log.d(TAG, "Found Flipper Zero: " + dev.getDeviceName());
                return dev;
            }
        }
        return null;
    }

    private UsbInterface findCdcDataInterface(UsbDevice dev) {
        for (int i = 0; i < dev.getInterfaceCount(); i++) {
            UsbInterface iface = dev.getInterface(i);
            // CDC Data class = 0x0A
            if (iface.getInterfaceClass() == 0x0A) {
                return iface;
            }
        }
        return null;
    }

    private UsbInterface findBulkInterface(UsbDevice dev) {
        for (int i = 0; i < dev.getInterfaceCount(); i++) {
            UsbInterface iface = dev.getInterface(i);
            boolean hasIn = false, hasOut = false;
            for (int j = 0; j < iface.getEndpointCount(); j++) {
                UsbEndpoint ep = iface.getEndpoint(j);
                if (ep.getType() == UsbConstants.USB_ENDPOINT_XFER_BULK) {
                    if (ep.getDirection() == UsbConstants.USB_DIR_IN)  hasIn  = true;
                    if (ep.getDirection() == UsbConstants.USB_DIR_OUT) hasOut = true;
                }
            }
            if (hasIn && hasOut) return iface;
        }
        return null;
    }

    @Override
    public void write(byte[] data) throws IOException {
        if (!connected.get() || connection == null || endpointOut == null) {
            throw new IOException("USB not connected");
        }
        int sent = connection.bulkTransfer(endpointOut, data, data.length, USB_TIMEOUT_MS);
        if (sent < 0) {
            throw new IOException("USB bulk write failed (error " + sent + ")");
        }
        Log.v(TAG, "USB write: " + sent + " bytes");
    }

    @Override
    public byte[] read(int maxBytes) throws IOException {
        if (!connected.get() || connection == null || endpointIn == null) {
            throw new IOException("USB not connected");
        }
        byte[] buffer = new byte[Math.min(maxBytes, BULK_TRANSFER_SIZE)];
        int received = connection.bulkTransfer(endpointIn, buffer, buffer.length, USB_TIMEOUT_MS);
        if (received < 0) {
            return new byte[0];
        }
        byte[] result = new byte[received];
        System.arraycopy(buffer, 0, result, 0, received);
        Log.v(TAG, "USB read: " + received + " bytes");
        return result;
    }

    @Override
    public byte[] readUntil(byte terminator, int maxBytes) throws IOException {
        byte[] accumulator = new byte[maxBytes];
        int pos = 0;
        long deadline = System.currentTimeMillis() + 5000;

        while (pos < maxBytes) {
            if (System.currentTimeMillis() > deadline) {
                throw new IOException("Read timeout");
            }
            byte[] chunk = read(maxBytes - pos);
            if (chunk.length == 0) {
                try { Thread.sleep(10); } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
                continue;
            }
            for (byte b : chunk) {
                accumulator[pos++] = b;
                if (b == terminator) {
                    byte[] result = new byte[pos];
                    System.arraycopy(accumulator, 0, result, 0, pos);
                    return result;
                }
            }
        }

        byte[] result = new byte[pos];
        System.arraycopy(accumulator, 0, result, 0, pos);
        return result;
    }

    @Override
    public void disconnect() {
        connected.set(false);
        if (connection != null) {
            if (usbInterface != null) {
                connection.releaseInterface(usbInterface);
            }
            connection.close();
            connection = null;
        }
        device = null;
        endpointIn = null;
        endpointOut = null;
        usbInterface = null;
        Log.i(TAG, "USB disconnected");
    }

    @Override
    public boolean isConnected() {
        return connected.get() && connection != null;
    }

    @Override
    public String getTransportType() {
        return "USB";
    }

    @Override
    public void flush() throws IOException {
        // USB bulk transfers are synchronous; no explicit flush needed
    }

    public UsbDevice getDevice()      { return device; }
    public boolean isInDfuMode() {
        return device != null && device.getProductId() == FLIPPER_PID_DFU;
    }
}
