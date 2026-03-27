package com.offsec.nethunter.GPS;

import android.location.Location;
import android.util.Log;

import java.util.HashMap;
import java.util.Map;

/**
 * NMEA 0183 sentence parser.
 * Supports GGA (Global Positioning System Fix Data) and
 * RMC (Recommended Minimum Specific GPS/Transit Data) sentences.
 */
public class NMEAParser {

    private static final String TAG = "NMEAParser";

    public static final String SENTENCE_GGA = "$GPGGA";
    public static final String SENTENCE_RMC = "$GPRMC";
    public static final String SENTENCE_GSV = "$GPGSV";
    public static final String SENTENCE_GLL = "$GPGLL";
    public static final String SENTENCE_VTG = "$GPVTG";

    private double latitude = 0.0;
    private double longitude = 0.0;
    private double altitude = 0.0;
    private double speed = 0.0;
    private double bearing = 0.0;
    private String utcTime = "";
    private int fixQuality = 0;
    private int numSatellites = 0;
    private double hdop = 0.0;
    private boolean hasFix = false;

    private final Map<String, NMEAListener> listeners = new HashMap<>();

    public interface NMEAListener {
        void onGGAParsed(double lat, double lon, double alt, int fixQuality, int numSats);
        void onRMCParsed(double lat, double lon, double speed, double bearing, String utcTime);
        void onParseError(String sentence, String error);
    }

    public void addListener(String tag, NMEAListener listener) {
        listeners.put(tag, listener);
    }

    public void removeListener(String tag) {
        listeners.remove(tag);
    }

    /**
     * Parse a raw NMEA sentence string.
     * @param nmea The raw NMEA sentence (may include checksum).
     * @return true if the sentence was parsed successfully.
     */
    public boolean parse(String nmea) {
        if (nmea == null || nmea.isEmpty()) {
            return false;
        }
        nmea = nmea.trim();

        // Validate checksum if present
        if (nmea.contains("*")) {
            if (!validateChecksum(nmea)) {
                Log.w(TAG, "Checksum validation failed for: " + nmea);
                notifyParseError(nmea, "Checksum mismatch");
                return false;
            }
            // Strip checksum for parsing
            nmea = nmea.substring(0, nmea.lastIndexOf('*'));
        }

        String[] fields = nmea.split(",");
        if (fields.length == 0) {
            return false;
        }

        String sentenceType = fields[0].toUpperCase();
        try {
            switch (sentenceType) {
                case SENTENCE_GGA:
                case "$GNGGA":
                    return parseGGA(fields);
                case SENTENCE_RMC:
                case "$GNRMC":
                    return parseRMC(fields);
                case SENTENCE_GLL:
                case "$GNGLL":
                    return parseGLL(fields);
                case SENTENCE_VTG:
                    return parseVTG(fields);
                default:
                    return false;
            }
        } catch (Exception e) {
            Log.e(TAG, "Error parsing NMEA sentence: " + nmea, e);
            notifyParseError(nmea, e.getMessage());
            return false;
        }
    }

    /**
     * Parse GGA - Global Positioning System Fix Data
     * Format: $GPGGA,HHMMSS.ss,LLLL.LL,a,YYYYY.YY,a,x,CC,HDOP,ALTM,M,,,
     */
    private boolean parseGGA(String[] fields) {
        if (fields.length < 10) {
            notifyParseError(String.join(",", fields), "GGA: insufficient fields");
            return false;
        }

        utcTime = fields[1];
        fixQuality = parseInt(fields[6], 0);

        if (fixQuality == 0) {
            hasFix = false;
            return false;
        }

        double lat = parseLatLon(fields[2], fields[3]);
        double lon = parseLatLon(fields[4], fields[5]);
        if (Double.isNaN(lat) || Double.isNaN(lon)) {
            return false;
        }

        latitude = lat;
        longitude = lon;
        numSatellites = parseInt(fields[7], 0);
        hdop = parseDouble(fields[8], 0.0);
        altitude = parseDouble(fields[9], 0.0);
        hasFix = true;

        notifyGGA(latitude, longitude, altitude, fixQuality, numSatellites);
        return true;
    }

    /**
     * Parse RMC - Recommended Minimum Specific GPS/Transit Data
     * Format: $GPRMC,HHMMSS.ss,A,LLLL.LL,a,YYYYY.YY,a,x.x,x.x,DDMMYY,,,
     */
    private boolean parseRMC(String[] fields) {
        if (fields.length < 9) {
            notifyParseError(String.join(",", fields), "RMC: insufficient fields");
            return false;
        }

        String status = fields[2];
        if (!"A".equalsIgnoreCase(status)) {
            // Status V = void (no fix)
            hasFix = false;
            return false;
        }

        utcTime = fields[1];
        double lat = parseLatLon(fields[3], fields[4]);
        double lon = parseLatLon(fields[5], fields[6]);
        if (Double.isNaN(lat) || Double.isNaN(lon)) {
            return false;
        }

        latitude = lat;
        longitude = lon;
        // Speed in knots -> convert to m/s
        speed = parseDouble(fields[7], 0.0) * 0.514444;
        bearing = parseDouble(fields[8], 0.0);
        hasFix = true;

        notifyRMC(latitude, longitude, speed, bearing, utcTime);
        return true;
    }

    /**
     * Parse GLL - Geographic Position, Latitude/Longitude
     */
    private boolean parseGLL(String[] fields) {
        if (fields.length < 6) return false;

        String status = fields[6];
        if (!"A".equalsIgnoreCase(status)) return false;

        double lat = parseLatLon(fields[1], fields[2]);
        double lon = parseLatLon(fields[3], fields[4]);
        if (!Double.isNaN(lat) && !Double.isNaN(lon)) {
            latitude = lat;
            longitude = lon;
            hasFix = true;
            return true;
        }
        return false;
    }

    /**
     * Parse VTG - Track Made Good and Ground Speed
     */
    private boolean parseVTG(String[] fields) {
        if (fields.length < 8) return false;
        bearing = parseDouble(fields[1], 0.0);
        // Speed in km/h -> convert to m/s
        speed = parseDouble(fields[7], 0.0) / 3.6;
        return true;
    }

    /**
     * Convert NMEA lat/lon (DDDMM.MMMMM) to decimal degrees.
     */
    private double parseLatLon(String value, String direction) {
        if (value == null || value.isEmpty()) return Double.NaN;
        try {
            double raw = Double.parseDouble(value);
            int degrees = (int) (raw / 100);
            double minutes = raw - (degrees * 100);
            double decimal = degrees + (minutes / 60.0);
            if ("S".equalsIgnoreCase(direction) || "W".equalsIgnoreCase(direction)) {
                decimal = -decimal;
            }
            return decimal;
        } catch (NumberFormatException e) {
            return Double.NaN;
        }
    }

    /**
     * Validate NMEA checksum. The checksum is the XOR of all bytes between $ and *.
     */
    public static boolean validateChecksum(String nmea) {
        int starIndex = nmea.lastIndexOf('*');
        if (starIndex < 0 || starIndex + 3 > nmea.length()) {
            return false;
        }
        String checksumStr = nmea.substring(starIndex + 1, starIndex + 3);
        int expected;
        try {
            expected = Integer.parseInt(checksumStr, 16);
        } catch (NumberFormatException e) {
            return false;
        }
        int calculated = 0;
        int start = nmea.startsWith("$") ? 1 : 0;
        for (int i = start; i < starIndex; i++) {
            calculated ^= nmea.charAt(i);
        }
        return calculated == expected;
    }

    private double parseDouble(String value, double defaultValue) {
        if (value == null || value.isEmpty()) return defaultValue;
        try {
            return Double.parseDouble(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    private int parseInt(String value, int defaultValue) {
        if (value == null || value.isEmpty()) return defaultValue;
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    private void notifyGGA(double lat, double lon, double alt, int fixQuality, int numSats) {
        for (NMEAListener listener : listeners.values()) {
            try {
                listener.onGGAParsed(lat, lon, alt, fixQuality, numSats);
            } catch (Exception e) {
                Log.e(TAG, "Listener error in onGGAParsed", e);
            }
        }
    }

    private void notifyRMC(double lat, double lon, double speed, double bearing, String utcTime) {
        for (NMEAListener listener : listeners.values()) {
            try {
                listener.onRMCParsed(lat, lon, speed, bearing, utcTime);
            } catch (Exception e) {
                Log.e(TAG, "Listener error in onRMCParsed", e);
            }
        }
    }

    private void notifyParseError(String sentence, String error) {
        for (NMEAListener listener : listeners.values()) {
            try {
                listener.onParseError(sentence, error);
            } catch (Exception e) {
                Log.e(TAG, "Listener error in onParseError", e);
            }
        }
    }

    /**
     * Convert parsed location data to an Android Location object.
     */
    public Location toLocation(String provider) {
        Location loc = new Location(provider);
        loc.setLatitude(latitude);
        loc.setLongitude(longitude);
        loc.setAltitude(altitude);
        loc.setSpeed((float) speed);
        loc.setBearing((float) bearing);
        return loc;
    }

    // Getters
    public double getLatitude()    { return latitude; }
    public double getLongitude()   { return longitude; }
    public double getAltitude()    { return altitude; }
    public double getSpeed()       { return speed; }
    public double getBearing()     { return bearing; }
    public String getUtcTime()     { return utcTime; }
    public int getFixQuality()     { return fixQuality; }
    public int getNumSatellites()  { return numSatellites; }
    public double getHdop()        { return hdop; }
    public boolean hasFix()        { return hasFix; }
}
