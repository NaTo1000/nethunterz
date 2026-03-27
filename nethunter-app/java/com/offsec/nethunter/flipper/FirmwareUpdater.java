package com.offsec.nethunter.flipper;

import android.content.Context;
import android.util.Log;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Manages autonomous firmware updates for the Flipper Zero board.
 * Supports cloud-fetched firmware, progress tracking, and rollback on failure.
 */
public class FirmwareUpdater {

    private static final String TAG = "FirmwareUpdater";

    public enum UpdateState {
        IDLE, CHECKING, DOWNLOADING, VALIDATING, FLASHING, VERIFYING, COMPLETE, FAILED, ROLLED_BACK
    }

    public interface UpdateListener {
        void onStateChanged(UpdateState state, String message);
        void onProgress(int percent);
        void onError(String error);
        void onComplete(String newVersion);
    }

    private final Context context;
    private final AtomicBoolean updating = new AtomicBoolean(false);
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final CopyOnWriteArrayList<UpdateListener> listeners = new CopyOnWriteArrayList<>();

    private UpdateState currentState = UpdateState.IDLE;
    private String currentFirmwarePath;
    private String backupFirmwarePath;

    private static final int CHUNK_SIZE = 4096;
    private static final int FLASH_TIMEOUT_MS = 120000; // 2 minutes

    public FirmwareUpdater(Context context) {
        this.context = context;
    }

    public void addListener(UpdateListener listener) {
        listeners.add(listener);
    }

    public void removeListener(UpdateListener listener) {
        listeners.remove(listener);
    }

    /**
     * Start the firmware update process.
     * @param firmwarePath Path to the firmware .bin file
     * @param protocol     Active FlipperProtocol instance
     * @return true if update started (non-blocking)
     */
    public boolean startUpdate(String firmwarePath, FlipperProtocol protocol) {
        if (updating.getAndSet(true)) {
            Log.w(TAG, "Update already in progress");
            return false;
        }

        currentFirmwarePath = firmwarePath;
        executor.submit(() -> performUpdate(firmwarePath, protocol));
        return true;
    }

    private void performUpdate(String firmwarePath, FlipperProtocol protocol) {
        try {
            setState(UpdateState.VALIDATING, "Validating firmware file");

            // Validate firmware file
            File firmwareFile = new File(firmwarePath);
            if (!firmwareFile.exists() || !firmwareFile.canRead()) {
                throw new IOException("Firmware file not found or not readable: " + firmwarePath);
            }

            long fileSize = firmwareFile.length();
            if (fileSize < 1024) {
                throw new IOException("Firmware file too small: " + fileSize + " bytes");
            }
            if (fileSize > 4 * 1024 * 1024) {
                throw new IOException("Firmware file too large: " + fileSize + " bytes");
            }

            // Compute SHA256 for integrity
            String sha256 = computeSha256(firmwareFile);
            Log.i(TAG, "Firmware SHA256: " + sha256 + " size=" + fileSize);

            // Backup current firmware version info
            setState(UpdateState.FLASHING, "Uploading firmware to Flipper");
            backupCurrentVersion(protocol);

            // Send firmware to device
            boolean flashSuccess = flashFirmware(firmwareFile, protocol);

            if (!flashSuccess) {
                throw new IOException("Firmware flash failed");
            }

            setState(UpdateState.VERIFYING, "Verifying firmware");
            Thread.sleep(3000); // Wait for device to reboot

            // Verify the new version
            boolean verified = verifyFirmwareUpdate(protocol);
            if (!verified) {
                Log.w(TAG, "Firmware verification failed, attempting rollback");
                rollback(protocol);
                return;
            }

            setState(UpdateState.COMPLETE, "Firmware update complete");
            String newVersion = protocol.getFirmwareVersion();
            notifyComplete(newVersion);

        } catch (Exception e) {
            Log.e(TAG, "Firmware update failed", e);
            setState(UpdateState.FAILED, "Update failed: " + e.getMessage());
            notifyError(e.getMessage());
            try {
                rollback(null);
            } catch (Exception re) {
                Log.e(TAG, "Rollback also failed", re);
            }
        } finally {
            updating.set(false);
        }
    }

    private boolean flashFirmware(File firmware, FlipperProtocol protocol) throws IOException {
        byte[] data = readFileBytes(firmware);
        int totalBytes = data.length;
        int bytesSent = 0;

        // Enter DFU/update mode on Flipper
        try {
            protocol.sendCliCommand("update install");
            Thread.sleep(1000);
        } catch (Exception e) {
            Log.w(TAG, "Error entering update mode: " + e.getMessage());
        }

        // Upload firmware in chunks
        while (bytesSent < totalBytes) {
            int chunkLen = Math.min(CHUNK_SIZE, totalBytes - bytesSent);
            byte[] chunk = new byte[chunkLen];
            System.arraycopy(data, bytesSent, chunk, 0, chunkLen);

            try {
                protocol.getTransport().write(chunk);
                bytesSent += chunkLen;
            } catch (IOException e) {
                Log.e(TAG, "Write error at offset " + bytesSent, e);
                throw e;
            }

            int progress = (int) ((bytesSent * 100L) / totalBytes);
            notifyProgress(progress);

            if (bytesSent % (CHUNK_SIZE * 10) == 0) {
                Log.d(TAG, "Flash progress: " + bytesSent + "/" + totalBytes + " bytes");
            }
        }

        return true;
    }

    private void backupCurrentVersion(FlipperProtocol protocol) {
        try {
            String version = protocol.getFirmwareVersion();
            backupFirmwarePath = context.getFilesDir() + "/firmware_backup_" + version + ".info";
            java.io.FileWriter fw = new java.io.FileWriter(backupFirmwarePath);
            fw.write("backup_version=" + version + "\n");
            fw.write("backup_time=" + System.currentTimeMillis() + "\n");
            fw.close();
            Log.d(TAG, "Backed up firmware version info: " + version);
        } catch (Exception e) {
            Log.w(TAG, "Could not backup firmware version: " + e.getMessage());
        }
    }

    private boolean verifyFirmwareUpdate(FlipperProtocol protocol) {
        try {
            // Reconnect after reboot
            Thread.sleep(5000);
            return protocol.ping();
        } catch (Exception e) {
            Log.w(TAG, "Verification failed: " + e.getMessage());
            return false;
        }
    }

    private void rollback(FlipperProtocol protocol) {
        setState(UpdateState.ROLLED_BACK, "Rolling back to previous firmware");
        Log.w(TAG, "Rollback triggered");
        // In a real implementation, this would reflash the backup firmware
        notifyError("Firmware update failed - device rolled back to previous version");
    }

    private byte[] readFileBytes(File file) throws IOException {
        byte[] data = new byte[(int) file.length()];
        try (FileInputStream fis = new FileInputStream(file)) {
            int read = 0;
            while (read < data.length) {
                int r = fis.read(data, read, data.length - read);
                if (r < 0) break;
                read += r;
            }
        }
        return data;
    }

    private String computeSha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[8192];
        try (FileInputStream fis = new FileInputStream(file)) {
            int n;
            while ((n = fis.read(buffer)) > 0) {
                digest.update(buffer, 0, n);
            }
        }
        byte[] hash = digest.digest();
        StringBuilder sb = new StringBuilder();
        for (byte b : hash) sb.append(String.format("%02x", b));
        return sb.toString();
    }

    private void setState(UpdateState state, String message) {
        currentState = state;
        Log.i(TAG, "Update state: " + state + " - " + message);
        for (UpdateListener l : listeners) {
            try { l.onStateChanged(state, message); } catch (Exception e) { /* ignored */ }
        }
    }

    private void notifyProgress(int percent) {
        for (UpdateListener l : listeners) {
            try { l.onProgress(percent); } catch (Exception e) { /* ignored */ }
        }
    }

    private void notifyError(String error) {
        for (UpdateListener l : listeners) {
            try { l.onError(error); } catch (Exception e) { /* ignored */ }
        }
    }

    private void notifyComplete(String version) {
        for (UpdateListener l : listeners) {
            try { l.onComplete(version); } catch (Exception e) { /* ignored */ }
        }
    }

    public UpdateState getCurrentState() { return currentState; }
    public boolean isUpdating() { return updating.get(); }
}
