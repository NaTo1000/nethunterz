package com.offsec.nethunter.GPS;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.offsec.nethunter.utils.Logger;

import java.util.ArrayList;
import java.util.List;

/**
 * Parses NMEA 0183 sentences produced by GPS hardware or a GPS daemon.
 *
 * <p>Supported sentence types:
 * <ul>
 *   <li>$GPGGA – fix data including altitude and satellite count</li>
 *   <li>$GPGLL – geographic position</li>
 *   <li>$GPRMC – recommended minimum sentence</li>
 *   <li>$GPGSV – satellites in view</li>
 *   <li>$GPGSA – DOP and active satellites</li>
 *   <li>$GPVTG – track made good and ground speed</li>
 * </ul>
 *
 * <p>This class is thread-safe; parse methods are synchronised on the
 * {@link NMEAData} result object.
 */
public class NMEAParser {

    private static final String TAG = "NMEAParser";

    // -------------------------------------------------------------------------
    // Data model
    // -------------------------------------------------------------------------

    /** Snapshot of the most recently parsed NMEA values. */
    public static class NMEAData {
        /** Latitude in decimal degrees, north positive. */
        public double latitude;
        /** Longitude in decimal degrees, east positive. */
        public double longitude;
        /** Altitude above mean sea level in metres. */
        public double altitude;
        /** Speed over ground in km/h. */
        public float speedKmh;
        /** True track heading in degrees. */
        public float heading;
        /** Number of satellites currently used in the fix. */
        public int satellitesUsed;
        /** Number of satellites currently in view. */
        public int satellitesInView;
        /** GPS fix quality (0 = invalid, 1 = GPS, 2 = DGPS, …). */
        public int fixQuality;
        /** Fix type string: "No fix", "2D fix", or "3D fix". */
        public String fixType = "No fix";
        /** HDOP – horizontal dilution of precision. */
        public float hdop;
        /** VDOP – vertical dilution of precision. */
        public float vdop;
        /** PDOP – position dilution of precision. */
        public float pdop;
        /** UTC time string as reported in the sentence (HHMMSS.ss). */
        public String utcTime = "";
        /** UTC date string as reported in $GPRMC (DDMMYY). */
        public String utcDate = "";
        /** Last successfully parsed raw sentence. */
        public String lastSentence = "";

        @Override
        public String toString() {
            return String.format(
                    "NMEAData{lat=%.6f, lon=%.6f, alt=%.1fm, speed=%.1fkm/h, "
                    + "heading=%.1f°, satsUsed=%d, satsView=%d, fixQ=%d, fix=%s}",
                    latitude, longitude, altitude, speedKmh,
                    heading, satellitesUsed, satellitesInView, fixQuality, fixType);
        }
    }

    // -------------------------------------------------------------------------
    // Callback interface
    // -------------------------------------------------------------------------

    /** Callback fired after each successfully parsed NMEA sentence. */
    public interface ParseCallback {
        /**
         * Called on the thread that called {@link #parse(String)}.
         *
         * @param data the updated NMEA data snapshot
         */
        void onDataUpdated(@NonNull NMEAData data);
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private final NMEAData mData = new NMEAData();
    private final List<ParseCallback> mCallbacks = new ArrayList<>();

    // -------------------------------------------------------------------------
    // Listener management
    // -------------------------------------------------------------------------

    /**
     * Registers a callback to be notified after each parse.
     *
     * @param callback the callback to add; no-op if already registered
     */
    public synchronized void addCallback(@NonNull ParseCallback callback) {
        if (!mCallbacks.contains(callback)) {
            mCallbacks.add(callback);
        }
    }

    /**
     * Removes a previously registered callback.
     *
     * @param callback the callback to remove
     */
    public synchronized void removeCallback(@NonNull ParseCallback callback) {
        mCallbacks.remove(callback);
    }

    // -------------------------------------------------------------------------
    // Public parse entry point
    // -------------------------------------------------------------------------

    /**
     * Parses a single NMEA sentence and updates the shared {@link NMEAData} state.
     *
     * <p>Returns {@code null} when the sentence is empty, has a bad checksum, or
     * is an unrecognised type.
     *
     * @param sentence a raw NMEA sentence, e.g. {@code "$GPGGA,…*hh"}
     * @return the updated {@link NMEAData}, or {@code null} on failure
     */
    @Nullable
    public synchronized NMEAData parse(@NonNull String sentence) {
        sentence = sentence.trim();
        if (sentence.isEmpty()) return null;
        if (!validateChecksum(sentence)) {
            Logger.w(TAG, "Checksum failure for: " + sentence);
            return null;
        }

        // Strip leading '$' and trailing checksum '*XX'
        String body = sentence.startsWith("$") ? sentence.substring(1) : sentence;
        int asterisk = body.lastIndexOf('*');
        if (asterisk >= 0) {
            body = body.substring(0, asterisk);
        }

        String[] fields = body.split(",", -1);
        if (fields.length == 0) return null;

        boolean updated;
        switch (fields[0]) {
            case "GPGGA": updated = parseGPGGA(fields); break;
            case "GPGLL": updated = parseGPGLL(fields); break;
            case "GPRMC": updated = parseGPRMC(fields); break;
            case "GPGSV": updated = parseGPGSV(fields); break;
            case "GPGSA": updated = parseGPGSA(fields); break;
            case "GPVTG": updated = parseGPVTG(fields); break;
            default:
                Logger.v(TAG, "Unrecognised sentence type: " + fields[0]);
                return null;
        }

        if (updated) {
            mData.lastSentence = sentence;
            notifyCallbacks();
            return mData;
        }
        return null;
    }

    /**
     * Returns a snapshot copy of the current NMEA data.
     *
     * @return a new {@link NMEAData} with the same field values
     */
    @NonNull
    public synchronized NMEAData getSnapshot() {
        NMEAData copy = new NMEAData();
        copy.latitude       = mData.latitude;
        copy.longitude      = mData.longitude;
        copy.altitude       = mData.altitude;
        copy.speedKmh       = mData.speedKmh;
        copy.heading        = mData.heading;
        copy.satellitesUsed = mData.satellitesUsed;
        copy.satellitesInView = mData.satellitesInView;
        copy.fixQuality     = mData.fixQuality;
        copy.fixType        = mData.fixType;
        copy.hdop           = mData.hdop;
        copy.vdop           = mData.vdop;
        copy.pdop           = mData.pdop;
        copy.utcTime        = mData.utcTime;
        copy.utcDate        = mData.utcDate;
        copy.lastSentence   = mData.lastSentence;
        return copy;
    }

    // -------------------------------------------------------------------------
    // Sentence parsers
    // -------------------------------------------------------------------------

    /**
     * Parses a $GPGGA sentence.
     *
     * <p>Format: $GPGGA,hhmmss.ss,llll.ll,a,yyyyy.yy,a,x,xx,x.x,x.x,M,x.x,M,x.x,xxxx*hh
     */
    private boolean parseGPGGA(String[] f) {
        if (f.length < 10) return false;
        try {
            if (!f[1].isEmpty()) mData.utcTime   = f[1];
            if (!f[2].isEmpty() && !f[3].isEmpty()) {
                mData.latitude  = nmeaToDecimal(f[2], f[3]);
            }
            if (!f[4].isEmpty() && !f[5].isEmpty()) {
                mData.longitude = nmeaToDecimal(f[4], f[5]);
            }
            if (!f[6].isEmpty()) mData.fixQuality    = Integer.parseInt(f[6]);
            if (!f[7].isEmpty()) mData.satellitesUsed = Integer.parseInt(f[7]);
            if (!f[8].isEmpty()) mData.hdop           = Float.parseFloat(f[8]);
            if (!f[9].isEmpty()) mData.altitude       = Double.parseDouble(f[9]);
            return true;
        } catch (NumberFormatException e) {
            Logger.w(TAG, "GPGGA parse error: " + e.getMessage());
            return false;
        }
    }

    /**
     * Parses a $GPGLL sentence.
     *
     * <p>Format: $GPGLL,llll.ll,a,yyyyy.yy,a,hhmmss.ss,A*hh
     */
    private boolean parseGPGLL(String[] f) {
        if (f.length < 5) return false;
        try {
            if (!f[1].isEmpty() && !f[2].isEmpty()) {
                mData.latitude  = nmeaToDecimal(f[1], f[2]);
            }
            if (!f[3].isEmpty() && !f[4].isEmpty()) {
                mData.longitude = nmeaToDecimal(f[3], f[4]);
            }
            if (f.length > 5 && !f[5].isEmpty()) mData.utcTime = f[5];
            return true;
        } catch (NumberFormatException e) {
            Logger.w(TAG, "GPGLL parse error: " + e.getMessage());
            return false;
        }
    }

    /**
     * Parses a $GPRMC sentence.
     *
     * <p>Format: $GPRMC,hhmmss.ss,A,llll.ll,a,yyyyy.yy,a,x.x,x.x,ddmmyy,x.x,a*hh
     */
    private boolean parseGPRMC(String[] f) {
        if (f.length < 10) return false;
        try {
            if (!f[1].isEmpty()) mData.utcTime = f[1];
            if (!f[3].isEmpty() && !f[4].isEmpty()) {
                mData.latitude  = nmeaToDecimal(f[3], f[4]);
            }
            if (!f[5].isEmpty() && !f[6].isEmpty()) {
                mData.longitude = nmeaToDecimal(f[5], f[6]);
            }
            // Speed in knots → km/h
            if (!f[7].isEmpty()) {
                mData.speedKmh = Float.parseFloat(f[7]) * 1.852f;
            }
            // True heading
            if (!f[8].isEmpty()) {
                mData.heading = Float.parseFloat(f[8]);
            }
            if (!f[9].isEmpty()) mData.utcDate = f[9];
            return true;
        } catch (NumberFormatException e) {
            Logger.w(TAG, "GPRMC parse error: " + e.getMessage());
            return false;
        }
    }

    /**
     * Parses a $GPGSV sentence (satellites in view).
     *
     * <p>Format: $GPGSV,x,x,xx,...*hh
     */
    private boolean parseGPGSV(String[] f) {
        if (f.length < 4) return false;
        try {
            if (!f[3].isEmpty()) {
                mData.satellitesInView = Integer.parseInt(f[3]);
            }
            return true;
        } catch (NumberFormatException e) {
            Logger.w(TAG, "GPGSV parse error: " + e.getMessage());
            return false;
        }
    }

    /**
     * Parses a $GPGSA sentence (DOP and active satellites).
     *
     * <p>Format: $GPGSA,A,x,xx,xx,…,x.x,x.x,x.x*hh
     */
    private boolean parseGPGSA(String[] f) {
        if (f.length < 18) return false;
        try {
            // Fix type: 1=no fix, 2=2D, 3=3D
            if (!f[2].isEmpty()) {
                int fixMode = Integer.parseInt(f[2]);
                switch (fixMode) {
                    case 2:  mData.fixType = "2D fix"; break;
                    case 3:  mData.fixType = "3D fix"; break;
                    default: mData.fixType = "No fix"; break;
                }
            }
            if (!f[15].isEmpty()) mData.pdop = Float.parseFloat(f[15]);
            if (!f[16].isEmpty()) mData.hdop = Float.parseFloat(f[16]);
            if (!f[17].isEmpty()) mData.vdop = Float.parseFloat(f[17]);
            return true;
        } catch (NumberFormatException e) {
            Logger.w(TAG, "GPGSA parse error: " + e.getMessage());
            return false;
        }
    }

    /**
     * Parses a $GPVTG sentence (track and ground speed).
     *
     * <p>Format: $GPVTG,x.x,T,x.x,M,x.x,N,x.x,K*hh
     */
    private boolean parseGPVTG(String[] f) {
        if (f.length < 9) return false;
        try {
            if (!f[1].isEmpty()) mData.heading  = Float.parseFloat(f[1]);
            // Speed in km/h is field 7
            if (!f[7].isEmpty()) mData.speedKmh = Float.parseFloat(f[7]);
            return true;
        } catch (NumberFormatException e) {
            Logger.w(TAG, "GPVTG parse error: " + e.getMessage());
            return false;
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Converts an NMEA coordinate string (DDDMM.mmmmm) to decimal degrees.
     *
     * @param value     the raw NMEA value, e.g. "4807.038"
     * @param direction "N", "S", "E", or "W"
     * @return decimal-degree value (negative for S/W)
     * @throws NumberFormatException if {@code value} cannot be parsed
     */
    static double nmeaToDecimal(@NonNull String value, @NonNull String direction)
            throws NumberFormatException {
        if (value.isEmpty()) return 0.0;
        double raw = Double.parseDouble(value);
        int degrees = (int) (raw / 100);
        double minutes = raw - degrees * 100.0;
        double decimal = degrees + minutes / 60.0;
        if ("S".equalsIgnoreCase(direction) || "W".equalsIgnoreCase(direction)) {
            decimal = -decimal;
        }
        return decimal;
    }

    /**
     * Validates an NMEA sentence's XOR checksum.
     *
     * @param sentence the full sentence including leading '$' and trailing '*XX'
     * @return {@code true} if the checksum is valid or absent
     */
    static boolean validateChecksum(@NonNull String sentence) {
        int start    = sentence.indexOf('$');
        int asterisk = sentence.lastIndexOf('*');
        if (start < 0 || asterisk < 0 || asterisk + 3 > sentence.length()) {
            return true; // no checksum present – accept
        }
        byte computed = 0;
        for (int i = start + 1; i < asterisk; i++) {
            computed ^= (byte) sentence.charAt(i);
        }
        try {
            int expected = Integer.parseInt(sentence.substring(asterisk + 1, asterisk + 3), 16);
            return (computed & 0xFF) == expected;
        } catch (NumberFormatException e) {
            return false;
        }
    }

    private void notifyCallbacks() {
        for (ParseCallback cb : mCallbacks) {
            try {
                cb.onDataUpdated(mData);
            } catch (Exception e) {
                Logger.e(TAG, "Callback threw an exception", e);
            }
        }
    }
}
