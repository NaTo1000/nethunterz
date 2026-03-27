package com.offsec.nethunter;

import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertThrows;

/**
 * Unit tests for {@link com.offsec.nethunter.utils.RootUtils}.
 *
 * <p>These tests run on the JVM (not on a device) and therefore cannot
 * exercise the actual {@code su} binary. They validate the contract of the
 * public API – specifically argument validation – without relying on
 * Android framework or root access.</p>
 */
public class RootUtilsTest {

    // ------------------------------------------------------------------
    // executeCommand – argument validation
    // ------------------------------------------------------------------

    /**
     * Passing a {@code null} command should throw {@link IllegalArgumentException}.
     */
    @Test
    public void executeCommand_nullCommand_throwsIllegalArgumentException() {
        assertThrows(IllegalArgumentException.class,
            () -> com.offsec.nethunter.utils.RootUtils.executeCommand(null));
    }

    /**
     * Passing an empty string should throw {@link IllegalArgumentException}.
     */
    @Test
    public void executeCommand_emptyCommand_throwsIllegalArgumentException() {
        assertThrows(IllegalArgumentException.class,
            () -> com.offsec.nethunter.utils.RootUtils.executeCommand(""));
    }

    /**
     * Passing a whitespace-only string should throw {@link IllegalArgumentException}.
     */
    @Test
    public void executeCommand_whitespaceCommand_throwsIllegalArgumentException() {
        assertThrows(IllegalArgumentException.class,
            () -> com.offsec.nethunter.utils.RootUtils.executeCommand("   "));
    }

    // ------------------------------------------------------------------
    // executeCommandSuccess – argument validation
    // ------------------------------------------------------------------

    /**
     * Passing a {@code null} command to executeCommandSuccess should throw
     * {@link IllegalArgumentException}.
     */
    @Test
    public void executeCommandSuccess_nullCommand_throwsIllegalArgumentException() {
        assertThrows(IllegalArgumentException.class,
            () -> com.offsec.nethunter.utils.RootUtils.executeCommandSuccess(null));
    }

    /**
     * Passing an empty string to executeCommandSuccess should throw
     * {@link IllegalArgumentException}.
     */
    @Test
    public void executeCommandSuccess_emptyCommand_throwsIllegalArgumentException() {
        assertThrows(IllegalArgumentException.class,
            () -> com.offsec.nethunter.utils.RootUtils.executeCommandSuccess(""));
    }

    // ------------------------------------------------------------------
    // isRootAvailable – smoke test (non-root JVM environment)
    // ------------------------------------------------------------------

    /**
     * On a standard CI JVM (no root), {@link com.offsec.nethunter.utils.RootUtils#isRootAvailable()}
     * should return {@code false} without throwing an exception.
     */
    @Test
    public void isRootAvailable_returnsBoolean_noException() {
        boolean result = com.offsec.nethunter.utils.RootUtils.isRootAvailable();
        // Simply assert it doesn't throw – on CI this will be false
        assertFalse("Root should not be available in a standard CI/JVM environment", result);
    }

    // ------------------------------------------------------------------
    // executeCommand – return type contract
    // ------------------------------------------------------------------

    /**
     * Even when root is unavailable, {@link com.offsec.nethunter.utils.RootUtils#executeCommand(String)}
     * must return a non-null String (possibly empty).
     *
     * <p>This test will fail with an IOException in an environment where 'su' is
     * not installed; that failure is expected behaviour and is caught internally
     * by the method. The method should never propagate null.</p>
     */
    @Test
    public void executeCommand_noRoot_returnsNonNullString() {
        // In a JVM environment without su, the method should catch the IOException
        // and return an empty string rather than null.
        String result;
        try {
            result = com.offsec.nethunter.utils.RootUtils.executeCommand("echo test");
        } catch (Exception e) {
            // If an unexpected exception escapes, the test fails for a clear reason
            throw new AssertionError("executeCommand must not propagate exceptions", e);
        }
        assertNotNull("executeCommand must return a non-null String", result);
    }
}
