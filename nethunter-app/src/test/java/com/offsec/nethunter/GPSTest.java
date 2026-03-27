package com.offsec.nethunter;

import com.offsec.nethunter.GPS.NMEAParser;

import org.junit.Before;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

/**
 * Unit tests for {@link NMEAParser}.
 *
 * <p>Covers NMEA sentence parsing, coordinate conversion, and checksum
 * validation without requiring an Android runtime.
 */
public class GPSTest {

    private NMEAParser mParser;

    @Before
    public void setUp() {
        mParser = new NMEAParser();
    }

    // -------------------------------------------------------------------------
    // nmeaToDecimal
    // -------------------------------------------------------------------------

    @Test
    public void nmeaToDecimal_northPositive() throws Exception {
        double result = NMEAParser.nmeaToDecimal("4807.038", "N");
        assertEquals(48.1173, result, 0.0001);
    }

    @Test
    public void nmeaToDecimal_southNegative() throws Exception {
        double result = NMEAParser.nmeaToDecimal("3352.903", "S");
        assertTrue("South should be negative", result < 0);
        assertEquals(-33.8817, result, 0.0001);
    }

    @Test
    public void nmeaToDecimal_eastPositive() throws Exception {
        double result = NMEAParser.nmeaToDecimal("01131.000", "E");
        assertEquals(11.5167, result, 0.0001);
    }

    @Test
    public void nmeaToDecimal_westNegative() throws Exception {
        double result = NMEAParser.nmeaToDecimal("01131.000", "W");
        assertTrue("West should be negative", result < 0);
    }

    @Test(expected = NumberFormatException.class)
    public void nmeaToDecimal_invalidValueThrows() throws Exception {
        NMEAParser.nmeaToDecimal("INVALID", "N");
    }

    // -------------------------------------------------------------------------
    // validateChecksum
    // -------------------------------------------------------------------------

    @Test
    public void validateChecksum_validGPGGA() {
        // Pre-computed valid checksum
        String sentence = "$GPGGA,092750.000,5321.6802,N,00630.3372,W,1,8,1.03,61.7,M,55.2,M,,*76";
        assertTrue(NMEAParser.validateChecksum(sentence));
    }

    @Test
    public void validateChecksum_corruptedSentence() {
        String sentence = "$GPGGA,092750.000,5321.6802,N,00630.3372,W,1,8,1.03,61.7,M,55.2,M,,*FF";
        assertFalse(NMEAParser.validateChecksum(sentence));
    }

    @Test
    public void validateChecksum_noChecksum_returnsTrue() {
        // Sentences without checksums should be accepted
        assertTrue(NMEAParser.validateChecksum("$GPGGA,nocheck"));
    }

    // -------------------------------------------------------------------------
    // parse – GPGGA
    // -------------------------------------------------------------------------

    @Test
    public void parse_GPGGA_extractsFields() {
        // Valid GPGGA sentence (checksum stripped for simplicity – no asterisk check)
        String sentence = "$GPGGA,092750.000,5321.6802,N,00630.3372,W,1,8,1.03,61.7,M,55.2,M,,";
        // Build with no checksum so it passes validation (no asterisk present)
        NMEAParser.NMEAData data = mParser.parse(sentence);
        assertNotNull("GPGGA should parse successfully", data);
        assertTrue("Latitude should be positive (N)", data.latitude > 0);
        assertTrue("Longitude should be negative (W)", data.longitude < 0);
        assertEquals(61.7, data.altitude, 0.1);
        assertEquals(8, data.satellitesUsed);
        assertEquals(1, data.fixQuality);
    }

    @Test
    public void parse_emptyString_returnsNull() {
        assertNull(mParser.parse(""));
    }

    @Test
    public void parse_whitespaceOnly_returnsNull() {
        assertNull(mParser.parse("   "));
    }

    @Test
    public void parse_unknownSentenceType_returnsNull() {
        assertNull(mParser.parse("$UNKNOWN,data,here"));
    }

    // -------------------------------------------------------------------------
    // parse – GPRMC
    // -------------------------------------------------------------------------

    @Test
    public void parse_GPRMC_extractsSpeedAndDate() {
        String sentence = "$GPRMC,092750.000,A,5321.6802,N,00630.3372,W,0.02,31.66,280511,,,";
        NMEAParser.NMEAData data = mParser.parse(sentence);
        assertNotNull("GPRMC should parse", data);
        assertEquals("280511", data.utcDate);
        // Speed 0.02 knots → ~0.037 km/h
        assertTrue("Speed should be near zero", data.speedKmh < 1.0f);
    }

    // -------------------------------------------------------------------------
    // parse – GPGSV
    // -------------------------------------------------------------------------

    @Test
    public void parse_GPGSV_extractsSatellitesInView() {
        String sentence = "$GPGSV,3,1,11,03,03,111,00,04,15,270,00,06,01,010,00,13,06,292,00";
        NMEAParser.NMEAData data = mParser.parse(sentence);
        assertNotNull("GPGSV should parse", data);
        assertEquals(11, data.satellitesInView);
    }

    // -------------------------------------------------------------------------
    // parse – GPGSA
    // -------------------------------------------------------------------------

    @Test
    public void parse_GPGSA_3dFix() {
        String sentence = "$GPGSA,A,3,04,05,,09,12,,,24,,,,,,2.5,1.3,2.1";
        NMEAParser.NMEAData data = mParser.parse(sentence);
        assertNotNull("GPGSA should parse", data);
        assertEquals("3D fix", data.fixType);
        assertEquals(2.5f, data.pdop, 0.01f);
    }

    @Test
    public void parse_GPGSA_noFix() {
        String sentence = "$GPGSA,A,1,,,,,,,,,,,,,99.9,99.9,99.9";
        NMEAParser.NMEAData data = mParser.parse(sentence);
        assertNotNull("GPGSA should parse", data);
        assertEquals("No fix", data.fixType);
    }

    // -------------------------------------------------------------------------
    // parse – GPVTG
    // -------------------------------------------------------------------------

    @Test
    public void parse_GPVTG_extractsHeadingAndSpeed() {
        String sentence = "$GPVTG,054.7,T,034.4,M,005.5,N,010.2,K";
        NMEAParser.NMEAData data = mParser.parse(sentence);
        assertNotNull("GPVTG should parse", data);
        assertEquals(54.7f, data.heading, 0.01f);
        assertEquals(10.2f, data.speedKmh, 0.01f);
    }

    // -------------------------------------------------------------------------
    // Callback
    // -------------------------------------------------------------------------

    @Test
    public void callback_invokedOnSuccessfulParse() {
        final boolean[] called = {false};
        mParser.addCallback(data -> called[0] = true);
        mParser.parse("$GPGSV,3,1,11,03,03,111,00,04,15,270,00,06,01,010,00,13,06,292,00");
        assertTrue("Callback should be invoked", called[0]);
    }

    @Test
    public void callback_notInvokedOnFailedParse() {
        final boolean[] called = {false};
        mParser.addCallback(data -> called[0] = true);
        mParser.parse("$UNKNOWN,bad,sentence");
        assertFalse("Callback should NOT be invoked for unknown sentence", called[0]);
    }

    // -------------------------------------------------------------------------
    // Snapshot
    // -------------------------------------------------------------------------

    @Test
    public void getSnapshot_returnsCopy() {
        mParser.parse("$GPGSV,3,1,11,03,03,111,00,04,15,270,00,06,01,010,00,13,06,292,00");
        NMEAParser.NMEAData snap = mParser.getSnapshot();
        assertNotNull(snap);
        assertEquals(11, snap.satellitesInView);
    }
}
