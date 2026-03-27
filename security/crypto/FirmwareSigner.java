package com.offsec.nethunter.security.crypto;

import android.util.Log;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.InvalidKeyException;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.PublicKey;
import java.security.Signature;
import java.security.SignatureException;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.security.spec.InvalidKeySpecException;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;

/**
 * Firmware signature verification for the NetHunter update system.
 * Supports RSA-2048 and Ed25519 signatures for firmware integrity checks.
 */
public class FirmwareSigner {

    private static final String TAG = "FirmwareSigner";

    public enum Algorithm { RSA_SHA256, ECDSA_SHA256, ED25519 }

    private PublicKey publicKey;
    private final Algorithm algorithm;

    public FirmwareSigner(Algorithm algorithm) {
        this.algorithm = algorithm;
    }

    /**
     * Load the verification public key from PEM-encoded bytes.
     * @param pemPublicKey PEM-encoded public key (PKCS#8 format)
     */
    public boolean loadPublicKey(byte[] pemPublicKey) {
        try {
            String pem = new String(pemPublicKey)
                .replace("-----BEGIN PUBLIC KEY-----", "")
                .replace("-----END PUBLIC KEY-----", "")
                .replaceAll("\\s", "");

            byte[] decoded = Base64.getDecoder().decode(pem);
            X509EncodedKeySpec keySpec = new X509EncodedKeySpec(decoded);

            String keyAlg;
            switch (algorithm) {
                case RSA_SHA256:   keyAlg = "RSA";   break;
                case ECDSA_SHA256: keyAlg = "EC";    break;
                case ED25519:      keyAlg = "Ed25519"; break;
                default:           keyAlg = "RSA";
            }

            KeyFactory keyFactory = KeyFactory.getInstance(keyAlg);
            publicKey = keyFactory.generatePublic(keySpec);
            Log.d(TAG, "Public key loaded: algorithm=" + keyAlg);
            return true;

        } catch (NoSuchAlgorithmException | InvalidKeySpecException e) {
            Log.e(TAG, "Failed to load public key", e);
            return false;
        }
    }

    /**
     * Verify the signature of a firmware file.
     *
     * @param firmwareFile  The firmware binary file
     * @param signatureFile The detached signature file (.sig)
     * @return true if the signature is valid
     */
    public boolean verifySignature(File firmwareFile, File signatureFile) {
        if (publicKey == null) {
            Log.e(TAG, "Public key not loaded");
            return false;
        }

        if (!firmwareFile.exists() || !signatureFile.exists()) {
            Log.e(TAG, "Firmware or signature file not found");
            return false;
        }

        try {
            byte[] signatureBytes = readFile(signatureFile);
            String jcaAlgorithm  = getJCAAlgorithm();
            Signature sig = Signature.getInstance(jcaAlgorithm);
            sig.initVerify(publicKey);

            // Feed the firmware data into the signature context
            try (FileInputStream fis = new FileInputStream(firmwareFile)) {
                byte[] buffer = new byte[8192];
                int n;
                while ((n = fis.read(buffer)) > 0) {
                    sig.update(buffer, 0, n);
                }
            }

            boolean valid = sig.verify(signatureBytes);
            if (valid) {
                Log.i(TAG, "Firmware signature VALID: " + firmwareFile.getName());
            } else {
                Log.w(TAG, "Firmware signature INVALID: " + firmwareFile.getName());
            }
            return valid;

        } catch (NoSuchAlgorithmException | InvalidKeyException | SignatureException | IOException e) {
            Log.e(TAG, "Signature verification error", e);
            return false;
        }
    }

    /**
     * Verify firmware SHA-256 checksum against expected value.
     */
    public boolean verifyChecksum(File firmwareFile, String expectedSha256) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[8192];

            try (FileInputStream fis = new FileInputStream(firmwareFile)) {
                int n;
                while ((n = fis.read(buffer)) > 0) {
                    digest.update(buffer, 0, n);
                }
            }

            byte[] hash = digest.digest();
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) sb.append(String.format("%02x", b));
            String actualSha256 = sb.toString();

            boolean match = actualSha256.equalsIgnoreCase(expectedSha256);
            if (match) {
                Log.i(TAG, "Checksum VALID: " + firmwareFile.getName());
            } else {
                Log.w(TAG, "Checksum MISMATCH: expected=" + expectedSha256
                    + " actual=" + actualSha256);
            }
            return match;

        } catch (NoSuchAlgorithmException | IOException e) {
            Log.e(TAG, "Checksum verification error", e);
            return false;
        }
    }

    /**
     * Full firmware validation: checksum + signature.
     */
    public boolean validateFirmware(File firmwareFile, File signatureFile,
                                     String expectedSha256) {
        // Step 1: Verify checksum
        if (expectedSha256 != null && !expectedSha256.isEmpty()) {
            if (!verifyChecksum(firmwareFile, expectedSha256)) {
                Log.e(TAG, "Firmware checksum validation failed");
                return false;
            }
        }

        // Step 2: Verify signature (if key is loaded)
        if (publicKey != null && signatureFile != null) {
            if (!verifySignature(firmwareFile, signatureFile)) {
                Log.e(TAG, "Firmware signature validation failed");
                return false;
            }
        }

        Log.i(TAG, "Firmware validation PASSED: " + firmwareFile.getName());
        return true;
    }

    private String getJCAAlgorithm() {
        switch (algorithm) {
            case RSA_SHA256:   return "SHA256withRSA";
            case ECDSA_SHA256: return "SHA256withECDSA";
            case ED25519:      return "Ed25519";
            default:           return "SHA256withRSA";
        }
    }

    private byte[] readFile(File file) throws IOException {
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

    public boolean isKeyLoaded() { return publicKey != null; }
    public Algorithm getAlgorithm() { return algorithm; }
}
