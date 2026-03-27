package com.offsec.nethunter;

import com.offsec.nethunter.utils.Logger;
import com.offsec.nethunter.utils.NetHunterPaths;

import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.File;
import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.util.List;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

/**
 * Unit tests for {@link Logger}.
 *
 * <p>Uses reflection to inject a temporary log-file path so that tests do not
 * attempt to write to {@code /data/data/…} on the host JVM.
 */
public class LoggerTest {

    @Rule
    public TemporaryFolder tempFolder = new TemporaryFolder();

    private File mLogFile;

    @Before
    public void setUp() throws Exception {
        mLogFile = tempFolder.newFile("nethunter-test.log");
        injectLogFile(mLogFile);
    }

    @After
    public void tearDown() throws Exception {
        // Reset log file reference to null to avoid leaking state between tests
        injectLogFile(null);
    }

    // -------------------------------------------------------------------------
    // Log levels
    // -------------------------------------------------------------------------

    @Test
    public void logInfo_writesToFile() throws IOException {
        Logger.i("TestTag", "Info message from test");
        Logger.flush();

        List<String> lines = Files.readAllLines(mLogFile.toPath());
        assertTrue("Log file should contain info message",
                lines.stream().anyMatch(l -> l.contains("Info message from test")));
    }

    @Test
    public void logWarning_writesToFile() throws IOException {
        Logger.w("TestTag", "Warning message from test");
        Logger.flush();

        List<String> lines = Files.readAllLines(mLogFile.toPath());
        assertTrue("Log file should contain warning",
                lines.stream().anyMatch(l -> l.contains("Warning message from test")));
    }

    @Test
    public void logError_withThrowable_writesStackTrace() throws IOException {
        Exception ex = new RuntimeException("test exception");
        Logger.e("TestTag", "Error with exception", ex);
        Logger.flush();

        List<String> lines = Files.readAllLines(mLogFile.toPath());
        boolean hasMessage = lines.stream().anyMatch(l -> l.contains("Error with exception"));
        boolean hasStackTrace = lines.stream().anyMatch(l ->
                l.contains("RuntimeException") || l.contains("test exception"));
        assertTrue("Should contain error message", hasMessage);
        assertTrue("Should contain stack trace", hasStackTrace);
    }

    @Test
    public void logDebug_writesToFile() throws IOException {
        Logger.d("TestTag", "Debug entry");
        Logger.flush();

        List<String> lines = Files.readAllLines(mLogFile.toPath());
        assertTrue("Log file should contain debug entry",
                lines.stream().anyMatch(l -> l.contains("Debug entry")));
    }

    // -------------------------------------------------------------------------
    // Log format
    // -------------------------------------------------------------------------

    @Test
    public void logLine_containsLevelIndicator() throws IOException {
        Logger.i("TagX", "format check");
        Logger.flush();

        List<String> lines = Files.readAllLines(mLogFile.toPath());
        boolean hasLevel = lines.stream()
                .filter(l -> l.contains("format check"))
                .anyMatch(l -> l.contains("I/TagX"));
        assertTrue("Log line should contain level indicator I/TagX", hasLevel);
    }

    @Test
    public void logLine_containsTimestamp() throws IOException {
        Logger.i("TagY", "timestamp check");
        Logger.flush();

        List<String> lines = Files.readAllLines(mLogFile.toPath());
        // Timestamp format: yyyy-MM-dd HH:mm:ss.SSS
        boolean hasTimestamp = lines.stream()
                .filter(l -> l.contains("timestamp check"))
                .anyMatch(l -> l.matches("\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}\\.\\d{3}.*"));
        assertTrue("Log line should start with timestamp", hasTimestamp);
    }

    // -------------------------------------------------------------------------
    // File creation
    // -------------------------------------------------------------------------

    @Test
    public void logFile_createdOnFirstWrite() throws IOException {
        File newLog = new File(tempFolder.getRoot(), "newfile.log");
        assertFalse("File should not exist yet", newLog.exists());
        injectLogFile(newLog);
        Logger.i("Tag", "create file test");
        Logger.flush();
        assertTrue("Log file should be created after first write", newLog.exists());
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Uses reflection to inject a custom log-file path into the static Logger
     * state, bypassing the Android context requirement.
     */
    private static void injectLogFile(File file) throws Exception {
        Field f = Logger.class.getDeclaredField("sLogFile");
        f.setAccessible(true);
        f.set(null, file);
    }
}
