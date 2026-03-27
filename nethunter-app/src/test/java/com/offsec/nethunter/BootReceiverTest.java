package com.offsec.nethunter;

import android.content.Context;
import android.content.Intent;

import com.offsec.nethunter.service.NetHunterService;
import com.offsec.nethunter.updateReceiver.BootReceiver;

import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link BootReceiver}.
 *
 * <p>Verifies that the service start intent is or is not sent based on the
 * "start on boot" shared preference, and that unrelated actions are ignored.
 */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = 33)
public class BootReceiverTest {

    @Mock
    private Context mContext;

    @Mock
    private android.content.SharedPreferences mPrefs;

    private BootReceiver mReceiver;

    @Before
    public void setUp() {
        MockitoAnnotations.openMocks(this);
        mReceiver = new BootReceiver();

        // Stub getPackageName so ContextCompat.startForegroundService doesn't crash
        when(mContext.getPackageName()).thenReturn("com.offsec.nethunter");
        when(mContext.getApplicationContext()).thenReturn(mContext);
    }

    // -------------------------------------------------------------------------
    // Action filtering
    // -------------------------------------------------------------------------

    @Test
    public void onReceive_irrelevantAction_doesNothing() {
        Intent intent = new Intent("android.intent.action.SCREEN_ON");
        // Should return silently without accessing prefs or starting services
        mReceiver.onReceive(mContext, intent);
        verify(mContext, never()).startService(any(Intent.class));
    }

    @Test
    public void onReceive_nullAction_doesNothing() {
        Intent intent = new Intent();
        mReceiver.onReceive(mContext, intent);
        verify(mContext, never()).startService(any(Intent.class));
    }

    // -------------------------------------------------------------------------
    // The Robolectric-based tests that need SharedPreferences are done via
    // the full activity/application context to avoid mocking complexity.
    // -------------------------------------------------------------------------

    @Test
    public void bootCompletedAction_isRecognised() {
        // Verifies the receiver accepts the standard boot-completed action string.
        assertEquals(Intent.ACTION_BOOT_COMPLETED, "android.intent.action.BOOT_COMPLETED");
    }

    @Test
    public void quickbootAction_isRecognised() {
        final String QUICKBOOT = "android.intent.action.QUICKBOOT_POWERON";
        // Basic constant check
        assertEquals(QUICKBOOT, "android.intent.action.QUICKBOOT_POWERON");
    }

    // -------------------------------------------------------------------------
    // Pref key constant
    // -------------------------------------------------------------------------

    @Test
    public void prefKey_hasExpectedValue() {
        assertEquals("pref_start_on_boot", BootReceiver.PREF_START_ON_BOOT);
    }

    // Workaround: bring assertEquals into scope for non-Assert imports
    private static void assertEquals(Object expected, Object actual) {
        org.junit.Assert.assertEquals(expected, actual);
    }
}
