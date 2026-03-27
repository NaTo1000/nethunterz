package com.offsec.nethunter.utils;

import android.content.Context;
import android.content.res.AssetManager;

import androidx.annotation.NonNull;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Utility class for file-system operations required during NetHunter setup
 * and runtime.
 *
 * <p>Provides:
 * <ul>
 *   <li>Asset extraction from the APK to internal storage.</li>
 *   <li>ZIP archive decompression with directory creation.</li>
 *   <li>Recursive file/directory operations (copy, delete, chmod).</li>
 *   <li>SHA-256 checksum calculation.</li>
 * </ul>
 */
public class FileManager {

    private static final String TAG = "FileManager";
    private static final int    BUFFER_SIZE = 8192;

    private final Context mContext;

    /**
     * Creates a new {@code FileManager} bound to the given context.
     *
     * @param context the application context; used to access {@link AssetManager}
     */
    public FileManager(@NonNull Context context) {
        mContext = context.getApplicationContext();
    }

    // -------------------------------------------------------------------------
    // Asset extraction
    // -------------------------------------------------------------------------

    /**
     * Extracts all assets from the APK to the application's internal file
     * storage ({@link NetHunterPaths#APP_DATA_DIR}).
     *
     * @param overwrite if {@code true}, existing files are replaced; if
     *                  {@code false}, existing files are skipped
     * @throws IOException if any asset cannot be read or written
     */
    public void extractAssets(boolean overwrite) throws IOException {
        AssetManager am = mContext.getAssets();
        extractAssetDir(am, "", new File(NetHunterPaths.APP_DATA_DIR), overwrite);
        Logger.i(TAG, "Asset extraction complete (overwrite=" + overwrite + ")");
    }

    /**
     * Recursively extracts assets from {@code assetPath} into {@code destDir}.
     *
     * @param am        the asset manager
     * @param assetPath the path inside the asset tree (empty string for root)
     * @param destDir   the destination directory on the file system
     * @param overwrite whether to overwrite existing files
     * @throws IOException on read/write errors
     */
    private void extractAssetDir(@NonNull AssetManager am,
            @NonNull String assetPath, @NonNull File destDir,
            boolean overwrite) throws IOException {
        String[] list = am.list(assetPath);
        if (list == null) return;

        if (!destDir.exists() && !destDir.mkdirs()) {
            throw new IOException("Could not create directory: " + destDir);
        }

        for (String name : list) {
            String srcPath = assetPath.isEmpty() ? name : assetPath + "/" + name;
            File   destFile = new File(destDir, name);

            String[] subList = am.list(srcPath);
            if (subList != null && subList.length > 0) {
                // It's a directory – recurse
                extractAssetDir(am, srcPath, destFile, overwrite);
            } else {
                // It's a file
                if (destFile.exists() && !overwrite) {
                    Logger.d(TAG, "Skipping existing asset: " + destFile);
                    continue;
                }
                try (InputStream in = am.open(srcPath);
                     FileOutputStream out = new FileOutputStream(destFile)) {
                    copy(in, out);
                    Logger.d(TAG, "Extracted: " + srcPath + " → " + destFile);
                }
            }
        }
    }

    // -------------------------------------------------------------------------
    // ZIP extraction
    // -------------------------------------------------------------------------

    /**
     * Extracts a ZIP archive to the given destination directory.
     *
     * <p>Directory entries and empty directories inside the ZIP are created.
     * Path traversal entries (containing {@code ..}) are silently skipped.
     *
     * @param zipFile the ZIP archive to extract
     * @param destDir the directory to extract into
     * @throws IOException on read/write errors
     */
    public void extractZip(@NonNull File zipFile, @NonNull File destDir) throws IOException {
        if (!destDir.exists() && !destDir.mkdirs()) {
            throw new IOException("Cannot create destination: " + destDir);
        }
        try (ZipInputStream zis = new ZipInputStream(new FileInputStream(zipFile))) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                String name = entry.getName();
                // Guard against path traversal
                if (name.contains("..")) {
                    Logger.w(TAG, "Skipping suspicious ZIP entry: " + name);
                    zis.closeEntry();
                    continue;
                }
                File outFile = new File(destDir, name);
                if (entry.isDirectory()) {
                    if (!outFile.exists() && !outFile.mkdirs()) {
                        Logger.w(TAG, "Could not create ZIP directory: " + outFile);
                    }
                } else {
                    File parent = outFile.getParentFile();
                    if (parent != null && !parent.exists()) parent.mkdirs();
                    try (FileOutputStream fos = new FileOutputStream(outFile)) {
                        copy(zis, fos);
                    }
                    Logger.d(TAG, "Unzipped: " + name);
                }
                zis.closeEntry();
            }
        }
        Logger.i(TAG, "ZIP extraction complete: " + zipFile.getName());
    }

    // -------------------------------------------------------------------------
    // Recursive copy
    // -------------------------------------------------------------------------

    /**
     * Copies {@code src} to {@code dest} recursively. If {@code src} is a file,
     * {@code dest} is overwritten. If {@code src} is a directory, its entire
     * subtree is copied under {@code dest}.
     *
     * @param src  the source file or directory
     * @param dest the destination file or directory
     * @throws IOException on read/write errors
     */
    public void copyRecursive(@NonNull File src, @NonNull File dest) throws IOException {
        if (src.isDirectory()) {
            if (!dest.exists() && !dest.mkdirs()) {
                throw new IOException("Cannot create dest dir: " + dest);
            }
            String[] children = src.list();
            if (children != null) {
                for (String child : children) {
                    copyRecursive(new File(src, child), new File(dest, child));
                }
            }
        } else {
            File parent = dest.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            try (FileInputStream in = new FileInputStream(src);
                 FileOutputStream out = new FileOutputStream(dest)) {
                copy(in, out);
            }
        }
    }

    // -------------------------------------------------------------------------
    // Delete
    // -------------------------------------------------------------------------

    /**
     * Deletes a file or directory tree recursively.
     *
     * @param target the file or directory to delete
     * @return {@code true} if the target no longer exists after the call
     */
    public boolean deleteRecursive(@NonNull File target) {
        if (target.isDirectory()) {
            File[] children = target.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteRecursive(child);
                }
            }
        }
        boolean deleted = target.delete();
        if (!deleted && target.exists()) {
            Logger.w(TAG, "Could not delete: " + target);
        }
        return deleted || !target.exists();
    }

    // -------------------------------------------------------------------------
    // Chmod
    // -------------------------------------------------------------------------

    /**
     * Sets the POSIX executable bit on a file via {@code chmod +x}.
     *
     * @param file the file to make executable
     * @return {@code true} if the operation succeeded
     */
    public boolean makeExecutable(@NonNull File file) {
        return file.setExecutable(true, false);
    }

    /**
     * Recursively sets the executable bit on all regular files under
     * {@code dir}.
     *
     * @param dir the directory whose files should be made executable
     */
    public void makeAllExecutable(@NonNull File dir) {
        if (!dir.exists()) return;
        if (dir.isFile()) {
            makeExecutable(dir);
            return;
        }
        File[] children = dir.listFiles();
        if (children != null) {
            for (File child : children) {
                makeAllExecutable(child);
            }
        }
    }

    // -------------------------------------------------------------------------
    // Checksum
    // -------------------------------------------------------------------------

    /**
     * Calculates the SHA-256 checksum of a file.
     *
     * @param file the file to hash
     * @return the hex-encoded SHA-256 digest string
     * @throws IOException              if the file cannot be read
     * @throws NoSuchAlgorithmException if SHA-256 is unavailable (should never happen)
     */
    @NonNull
    public String sha256(@NonNull File file) throws IOException, NoSuchAlgorithmException {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (DigestInputStream dis = new DigestInputStream(
                new FileInputStream(file), digest)) {
            byte[] buf = new byte[BUFFER_SIZE];
            while (dis.read(buf) != -1) { /* digest as we read */ }
        }
        byte[] hash = digest.digest();
        StringBuilder hex = new StringBuilder(hash.length * 2);
        for (byte b : hash) {
            hex.append(String.format("%02x", b));
        }
        return hex.toString();
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Copies all bytes from {@code in} to {@code out} using an internal buffer.
     *
     * @param in  the source stream
     * @param out the destination stream
     * @throws IOException on I/O error
     */
    private void copy(@NonNull InputStream in, @NonNull OutputStream out) throws IOException {
        byte[] buf = new byte[BUFFER_SIZE];
        int n;
        while ((n = in.read(buf)) != -1) {
            out.write(buf, 0, n);
        }
    }
}
