package com.offsec.nethunter.flipper;

import java.io.IOException;

/**
 * Common transport interface for Flipper Zero communication.
 * Implemented by USB, UART, and Bluetooth drivers.
 */
public interface FlipperTransport {

    /**
     * Establish a connection to the Flipper device.
     * @return true if connection was successful
     */
    boolean connect();

    /**
     * Disconnect and release resources.
     */
    void disconnect();

    /**
     * Write bytes to the Flipper device.
     * @param data bytes to send
     * @throws IOException on write failure
     */
    void write(byte[] data) throws IOException;

    /**
     * Read up to maxBytes from the device.
     * @param maxBytes maximum number of bytes to read
     * @return bytes read (may be empty but never null)
     * @throws IOException on read failure
     */
    byte[] read(int maxBytes) throws IOException;

    /**
     * Read bytes until a terminator byte is encountered.
     * @param terminator byte to stop reading at (inclusive)
     * @param maxBytes maximum number of bytes to read
     * @return bytes read including the terminator
     * @throws IOException on read failure or timeout
     */
    byte[] readUntil(byte terminator, int maxBytes) throws IOException;

    /**
     * Flush the output buffer.
     * @throws IOException on flush failure
     */
    void flush() throws IOException;

    /**
     * Check if the transport is currently connected.
     */
    boolean isConnected();

    /**
     * Get the transport type name for logging/UI.
     */
    String getTransportType();
}
