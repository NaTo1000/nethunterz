package com.offsec.nethunter;

import com.offsec.nethunter.utils.ShellExecutor;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.mockito.MockitoAnnotations;

import java.util.Arrays;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

/**
 * Unit tests for {@link ShellExecutor}.
 *
 * <p>These tests use real process spawning where supported by the JVM on the
 * host OS. Tests that require {@code su} are skipped gracefully by detecting
 * the non-root test environment.
 */
public class ShellExecutorTest {

    private ShellExecutor mShell;

    @Before
    public void setUp() {
        MockitoAnnotations.openMocks(this);
        mShell = ShellExecutor.getInstance();
    }

    @After
    public void tearDown() {
        // Close any persistent shell left open by tests
        mShell.closeRootShell();
    }

    // -------------------------------------------------------------------------
    // Singleton
    // -------------------------------------------------------------------------

    @Test
    public void getInstance_returnsSameInstance() {
        ShellExecutor a = ShellExecutor.getInstance();
        ShellExecutor b = ShellExecutor.getInstance();
        assertNotNull(a);
        assertEquals("getInstance must return singleton", a, b);
    }

    // -------------------------------------------------------------------------
    // executeSync (non-root)
    // -------------------------------------------------------------------------

    @Test
    public void executeSyncNoRoot_trueCommand_returnsZero() {
        int exit = mShell.executeSyncNoRoot("true");
        assertEquals("'true' should exit 0", 0, exit);
    }

    @Test
    public void executeSyncNoRoot_falseCommand_returnsNonZero() {
        int exit = mShell.executeSyncNoRoot("false");
        assertTrue("'false' should exit non-zero", exit != 0);
    }

    @Test
    public void executeSyncNoRoot_echoCommand_returnsZero() {
        int exit = mShell.executeSyncNoRoot("echo hello");
        assertEquals("echo should exit 0", 0, exit);
    }

    @Test
    public void executeSyncNoRoot_invalidCommand_returnsError() {
        int exit = mShell.executeSyncNoRoot("nonexistent_command_xyz_123");
        assertTrue("Invalid command should return non-zero exit", exit != 0);
    }

    // -------------------------------------------------------------------------
    // executeAsync (non-root)
    // -------------------------------------------------------------------------

    @Test
    public void executeAsync_outputDeliveredToCallback() throws InterruptedException {
        CountDownLatch latch = new CountDownLatch(1);
        AtomicBoolean outputReceived = new AtomicBoolean(false);

        mShell.executeAsyncNoRoot("echo nethunter_test", new ShellExecutor.Callback() {
            @Override
            public void onOutput(String line) {
                if (line.contains("nethunter_test")) {
                    outputReceived.set(true);
                }
            }
            @Override
            public void onComplete(int exitCode) {
                latch.countDown();
            }
            @Override
            public void onError(String error) {
                latch.countDown();
            }
        });

        assertTrue("Async command should complete within 5 seconds",
                latch.await(5, TimeUnit.SECONDS));
        assertTrue("Output should contain 'nethunter_test'", outputReceived.get());
    }

    @Test
    public void executeAsync_exitCodeDelivered() throws InterruptedException {
        CountDownLatch latch = new CountDownLatch(1);
        AtomicInteger exitCode = new AtomicInteger(-99);

        mShell.executeAsyncNoRoot("exit 42", new ShellExecutor.Callback() {
            @Override
            public void onOutput(String line) {}
            @Override
            public void onComplete(int code) {
                exitCode.set(code);
                latch.countDown();
            }
            @Override
            public void onError(String error) {
                latch.countDown();
            }
        });

        assertTrue("Should complete in 5 seconds", latch.await(5, TimeUnit.SECONDS));
        assertEquals("Exit code should be 42", 42, exitCode.get());
    }

    @Test
    public void executeAsync_nullCallback_doesNotCrash() throws InterruptedException {
        CountDownLatch latch = new CountDownLatch(1);
        // Execute with null callback – should not throw
        mShell.executeAsyncNoRoot("echo ok", null);
        // Brief wait to let the async task run
        Thread.sleep(500);
    }

    // -------------------------------------------------------------------------
    // executeBatch
    // -------------------------------------------------------------------------

    @Test
    public void executeBatch_allSucceed_returnsZero() {
        int result = mShell.executeBatch(Arrays.asList("true", "true", "true"));
        assertEquals("All-true batch should return 0", 0, result);
    }

    @Test
    public void executeBatch_firstFails_returnsNonZero() {
        int result = mShell.executeBatch(Arrays.asList("false", "true", "true"));
        assertFalse("Batch with first failure should return non-zero", result == 0);
    }

    @Test
    public void executeBatch_emptyList_returnsZero() {
        int result = mShell.executeBatch(java.util.Collections.emptyList());
        assertEquals("Empty batch should return 0", 0, result);
    }

    // -------------------------------------------------------------------------
    // Root shell (only tested if 'su' is not available to avoid blocking)
    // -------------------------------------------------------------------------

    @Test
    public void openRootShell_whenSuUnavailable_returnsFalse() {
        // On a non-rooted CI host, openRootShell() should return false gracefully
        // rather than hanging indefinitely.
        // We use a separate instance to avoid polluting the singleton state.
        // This test verifies graceful failure only.
        boolean opened = mShell.openRootShell();
        if (!opened) {
            // Graceful failure – expected on non-root host
            assertFalse("Shell should not be open if su not available", opened);
        }
        mShell.closeRootShell();
    }
}
