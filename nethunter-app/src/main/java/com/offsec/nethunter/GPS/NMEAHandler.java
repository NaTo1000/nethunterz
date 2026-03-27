package com.offsec.nethunter.GPS;

import android.location.GpsStatus;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Bundle;
import android.util.Log;

import java.util.Locale;

/**
 * NMEAHandler - Handles raw NMEA GPS data for injection into the Kali chroot environment.
 *
 * <p>This class implements {@link LocationListener} and {@link GpsStatus.NmeaListener}
 * to capture GPS location updates and raw NMEA sentences. The parsed NMEA data is
 * forwarded to a socket or file so that GPS-aware tools inside the chroot can consume it.</p>
 *
 * <p>Supported NMEA sentence types:</p>
 * <ul>
 *   <li>$GPGGA – Fix data (position, altitude, fix quality)</li>
 *   <li>$GPRMC – Recommended minimum data (position, speed, heading)</li>
 *   <li>$GPGSV – Satellites in view</li>
 *   <li>$GPGSA – Active satellites and DOP values</li>
 * </ul>
 */
public class NMEAHandler implements LocationListener, GpsStatus.NmeaListener {

    private static final String TAG = "NMEAHandler";

    /** Callback interface for delivering parsed NMEA sentences to the GPS service. */
    public interface NMEAListener {
        /**
         * Called when a new NMEA sentence has been received from the GPS hardware.
         *
         * @param sentence the raw NMEA sentence string (e.g., "$GPGGA,...")
         */
        void onNmeaSentence(String sentence);
    }

    private final NMEAListener listener;
    private Location lastKnownLocation;
    private boolean isActive = false;

    /**
     * Constructs an NMEAHandler with the given listener for sentence delivery.
     *
     * @param listener the {@link NMEAListener} to receive parsed NMEA sentences
     */
    public NMEAHandler(NMEAListener listener) {
        this.listener = listener;
    }

    // -------------------------------------------------------------------------
    // GpsStatus.NmeaListener
    // -------------------------------------------------------------------------

    @Override
    public void onNmeaReceived(long timestamp, String nmea) {
        if (nmea == null || nmea.isEmpty()) return;

        // Strip trailing whitespace / newlines
        String sentence = nmea.trim();
        if (!sentence.startsWith("$")) return;

        Log.v(TAG, "NMEA: " + sentence);
        if (listener != null) {
            listener.onNmeaSentence(sentence + "\r\n");
        }
    }

    // -------------------------------------------------------------------------
    // LocationListener
    // -------------------------------------------------------------------------

    @Override
    public void onLocationChanged(Location location) {
        if (location == null) return;
        lastKnownLocation = location;
        isActive = true;
        Log.d(TAG, String.format(Locale.US,
            "Location update: lat=%.6f lon=%.6f alt=%.1f",
            location.getLatitude(),
            location.getLongitude(),
            location.getAltitude()));

        // Synthesise a basic $GPGGA sentence when raw NMEA is not available
        if (listener != null) {
            listener.onNmeaSentence(buildGpgga(location));
            listener.onNmeaSentence(buildGprmc(location));
        }
    }

    @Override
    public void onStatusChanged(String provider, int status, Bundle extras) {
        Log.d(TAG, "GPS provider status changed: " + provider + " -> " + status);
    }

    @Override
    public void onProviderEnabled(String provider) {
        Log.d(TAG, "GPS provider enabled: " + provider);
        isActive = true;
    }

    @Override
    public void onProviderDisabled(String provider) {
        Log.d(TAG, "GPS provider disabled: " + provider);
        if (LocationManager.GPS_PROVIDER.equals(provider)) {
            isActive = false;
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Returns whether the GPS provider is currently active and delivering fixes.
     *
     * @return {@code true} if the GPS is active
     */
    public boolean isActive() {
        return isActive;
    }

    /**
     * Returns the most recent {@link Location} received, or {@code null} if none.
     *
     * @return last known location
     */
    public Location getLastKnownLocation() {
        return lastKnownLocation;
    }

    /**
     * Builds a minimal $GPGGA NMEA sentence from the supplied {@link Location}.
     *
     * @param loc the location to encode
     * @return NMEA $GPGGA sentence with CRLF terminator
     */
    private String buildGpgga(Location loc) {
        double lat = loc.getLatitude();
        double lon = loc.getLongitude();
        double alt = loc.getAltitude();

        String latDir = lat >= 0 ? "N" : "S";
        String lonDir = lon >= 0 ? "E" : "W";
        double absLat = Math.abs(lat);
        double absLon = Math.abs(lon);

        int latDeg = (int) absLat;
        double latMin = (absLat - latDeg) * 60.0;
        int lonDeg = (int) absLon;
        double lonMin = (absLon - lonDeg) * 60.0;

        String sentence = String.format(Locale.US,
            "$GPGGA,,%.2d%07.4f,%s,%.3d%07.4f,%s,1,08,1.0,%.1f,M,0.0,M,,",
            latDeg, latMin, latDir, lonDeg, lonMin, lonDir, alt);

        return sentence + "*" + computeChecksum(sentence) + "\r\n";
    }

    /**
     * Builds a minimal $GPRMC NMEA sentence from the supplied {@link Location}.
     *
     * @param loc the location to encode
     * @return NMEA $GPRMC sentence with CRLF terminator
     */
    private String buildGprmc(Location loc) {
        double lat = loc.getLatitude();
        double lon = loc.getLongitude();
        float speed = loc.getSpeed() * 1.94384f; // m/s -> knots
        float bearing = loc.getBearing();

        String latDir = lat >= 0 ? "N" : "S";
        String lonDir = lon >= 0 ? "E" : "W";
        double absLat = Math.abs(lat);
        double absLon = Math.abs(lon);

        int latDeg = (int) absLat;
        double latMin = (absLat - latDeg) * 60.0;
        int lonDeg = (int) absLon;
        double lonMin = (absLon - lonDeg) * 60.0;

        String sentence = String.format(Locale.US,
            "$GPRMC,,A,%.2d%07.4f,%s,%.3d%07.4f,%s,%.1f,%.1f,,,,A",
            latDeg, latMin, latDir, lonDeg, lonMin, lonDir, speed, bearing);

        return sentence + "*" + computeChecksum(sentence) + "\r\n";
    }

    /**
     * Computes the standard NMEA XOR checksum for the sentence body
     * (the characters between '$' and '*', exclusive).
     *
     * @param sentence the full sentence including leading '$'
     * @return two-character uppercase hex checksum
     */
    private String computeChecksum(String sentence) {
        int checksum = 0;
        for (int i = 1; i < sentence.length(); i++) {
            char c = sentence.charAt(i);
            if (c == '*') break;
            checksum ^= c;
        }
        return String.format(Locale.US, "%02X", checksum);
    }
}
