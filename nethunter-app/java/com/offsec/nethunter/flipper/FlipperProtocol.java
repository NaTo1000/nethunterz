package com.offsec.nethunter.flipper;

import android.util.Log;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;

/**
 * RPC protocol implementation for Flipper Zero.
 *
 * The Flipper Zero uses a simple serial protocol:
 * - Commands are sent as newline-terminated strings in CLI mode
 * - Or as length-prefixed protobuf frames in RPC mode
 *
 * This implementation supports both CLI and RPC modes.
 */
public class FlipperProtocol {

    private static final String TAG = "FlipperProtocol";

    // RPC frame constants
    private static final byte   RPC_HEADER_MAGIC    = (byte) 0xAA;
    private static final int    RPC_MAX_PAYLOAD     = 65536;
    private static final int    MAX_RESPONSE_SIZE   = 4096;
    private static final long   RESPONSE_TIMEOUT_MS = 5000;

    // Protocol command types
    public static final int CMD_PING          = 0x01;
    public static final int CMD_GET_VERSION   = 0x02;
    public static final int CMD_STORAGE_READ  = 0x10;
    public static final int CMD_STORAGE_WRITE = 0x11;
    public static final int CMD_APP_START     = 0x20;
    public static final int CMD_APP_STOP      = 0x21;
    public static final int CMD_GPIO_SET      = 0x30;
    public static final int CMD_GPIO_GET      = 0x31;

    private FlipperTransport transport;
    private boolean rpcMode = false;
    private int sequenceNumber = 0;

    public FlipperProtocol() {}

    public void setTransport(FlipperTransport transport) {
        this.transport = transport;
    }

    /**
     * Send a CLI command (string) and receive the response.
     * @param command The command string (without trailing newline)
     * @return response string from Flipper
     */
    public String sendCliCommand(String command) throws IOException {
        if (transport == null || !transport.isConnected()) {
            throw new IOException("No active transport");
        }

        // Send command with CRLF
        byte[] cmdBytes = (command + "\r\n").getBytes(StandardCharsets.UTF_8);
        transport.write(cmdBytes);
        Log.d(TAG, "CLI command sent: " + command);

        // Read response until prompt (>: )
        StringBuilder response = new StringBuilder();
        long deadline = System.currentTimeMillis() + RESPONSE_TIMEOUT_MS;

        while (System.currentTimeMillis() < deadline) {
            byte[] chunk = transport.read(MAX_RESPONSE_SIZE);
            if (chunk.length > 0) {
                String part = new String(chunk, StandardCharsets.UTF_8);
                response.append(part);
                // Flipper CLI prompt is ">: "
                if (part.contains(">: ")) {
                    break;
                }
            } else {
                try { Thread.sleep(20); } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }

        String result = response.toString().trim();
        // Strip the echoed command and the prompt
        if (result.startsWith(command)) {
            result = result.substring(command.length()).trim();
        }
        if (result.endsWith(">:")) {
            result = result.substring(0, result.lastIndexOf(">:")).trim();
        }
        return result;
    }

    /**
     * Send an RPC command using the binary framed protocol.
     * Frame format: [MAGIC(1)] [SEQUENCE(4)] [CMD(2)] [LENGTH(4)] [PAYLOAD(N)]
     */
    public byte[] sendCommand(byte[] payload) throws IOException {
        if (transport == null || !transport.isConnected()) {
            throw new IOException("No active transport");
        }

        int seq = ++sequenceNumber;
        byte[] frame = buildFrame(CMD_PING, seq, payload);
        transport.write(frame);
        Log.d(TAG, "RPC command sent, seq=" + seq + " payload_len=" + payload.length);

        // Read response frame
        return readResponseFrame(seq);
    }

    private byte[] buildFrame(int cmdType, int seqNum, byte[] payload) {
        int payloadLen = payload != null ? payload.length : 0;
        ByteBuffer buf = ByteBuffer.allocate(1 + 4 + 2 + 4 + payloadLen)
            .order(ByteOrder.LITTLE_ENDIAN);
        buf.put(RPC_HEADER_MAGIC);
        buf.putInt(seqNum);
        buf.putShort((short) cmdType);
        buf.putInt(payloadLen);
        if (payload != null && payloadLen > 0) {
            buf.put(payload);
        }
        return buf.array();
    }

    private byte[] readResponseFrame(int expectedSeq) throws IOException {
        long deadline = System.currentTimeMillis() + RESPONSE_TIMEOUT_MS;
        ByteArrayOutputStream baos = new ByteArrayOutputStream();

        while (System.currentTimeMillis() < deadline) {
            byte[] chunk = transport.read(MAX_RESPONSE_SIZE);
            if (chunk.length > 0) {
                baos.write(chunk);
                byte[] data = baos.toByteArray();

                // Check if we have a complete frame
                if (data.length >= 11) { // minimum frame size
                    ByteBuffer buf = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
                    if (buf.get() == RPC_HEADER_MAGIC) {
                        int seq = buf.getInt();
                        buf.getShort(); // cmd type
                        int payloadLen = buf.getInt();
                        if (data.length >= 11 + payloadLen) {
                            byte[] payload = new byte[payloadLen];
                            buf.get(payload);
                            Log.d(TAG, "Response received seq=" + seq + " len=" + payloadLen);
                            return payload;
                        }
                    }
                }
            } else {
                try { Thread.sleep(20); } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        throw new IOException("Timeout waiting for RPC response (seq=" + expectedSeq + ")");
    }

    /**
     * Get the Flipper firmware version string.
     */
    public String getFirmwareVersion() throws IOException {
        String response = sendCliCommand("version");
        // Parse version from response
        for (String line : response.split("\n")) {
            if (line.contains("firmware_version") || line.contains("Version:")) {
                String[] parts = line.split("[:=]");
                if (parts.length >= 2) {
                    return parts[1].trim();
                }
            }
        }
        return response.isEmpty() ? "unknown" : response.split("\n")[0].trim();
    }

    /**
     * Ping the Flipper device to test connectivity.
     */
    public boolean ping() {
        try {
            String response = sendCliCommand("?");
            return response != null && !response.isEmpty();
        } catch (IOException e) {
            Log.w(TAG, "Ping failed: " + e.getMessage());
            return false;
        }
    }

    /**
     * Enter RPC mode (binary protocol).
     */
    public boolean enterRpcMode() throws IOException {
        String response = sendCliCommand("start_rpc_session");
        rpcMode = response.isEmpty() || response.contains("OK");
        return rpcMode;
    }

    /**
     * Exit RPC mode and return to CLI mode.
     */
    public void exitRpcMode() throws IOException {
        if (rpcMode) {
            // Send RPC stop session command
            byte[] stopCmd = buildFrame(0xFF, ++sequenceNumber, new byte[0]);
            transport.write(stopCmd);
            rpcMode = false;
        }
    }

    /**
     * Read a file from Flipper storage.
     */
    public byte[] readFile(String path) throws IOException {
        String response = sendCliCommand("storage read " + path);
        return response.getBytes(StandardCharsets.UTF_8);
    }

    /**
     * Write a file to Flipper storage.
     */
    public boolean writeFile(String path, byte[] data) throws IOException {
        // Send the write command
        sendCliCommand("storage write " + path);
        // Send size
        transport.write((data.length + "\n").getBytes(StandardCharsets.UTF_8));
        // Send data
        transport.write(data);
        transport.flush();
        // Read confirmation
        String response = sendCliCommand("");
        return response.contains("OK") || response.isEmpty();
    }

    public boolean isRpcMode() { return rpcMode; }
    public FlipperTransport getTransport() { return transport; }
}
