package com.offsec.nethunter;

import androidx.fragment.app.testing.FragmentScenario;
import androidx.test.espresso.Espresso;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.filters.MediumTest;
import androidx.test.rule.GrantPermissionRule;

import android.Manifest;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;

/**
 * Instrumented Espresso tests for {@link GPSFragment}.
 *
 * <p>Verifies that the GPS fragment renders key UI elements and that the
 * Start/Stop buttons are accessible.
 */
@MediumTest
@RunWith(AndroidJUnit4.class)
public class GPSFragmentTest {

    @Rule
    public GrantPermissionRule mLocationPermission = GrantPermissionRule.grant(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
    );

    // -------------------------------------------------------------------------
    // Launch
    // -------------------------------------------------------------------------

    @Test
    public void gpsFragment_launchesSuccessfully() {
        FragmentScenario<GPSFragment> scenario =
                FragmentScenario.launchInContainer(GPSFragment.class,
                        null, R.style.Theme_NetHunter);
        scenario.onFragment(fragment ->
                org.junit.Assert.assertNotNull(fragment.getView()));
    }

    // -------------------------------------------------------------------------
    // Views
    // -------------------------------------------------------------------------

    @Test
    public void startButton_isDisplayed() {
        FragmentScenario.launchInContainer(GPSFragment.class,
                null, R.style.Theme_NetHunter);
        onView(withId(R.id.btn_start_gps)).check(matches(isDisplayed()));
    }

    @Test
    public void stopButton_isDisplayed() {
        FragmentScenario.launchInContainer(GPSFragment.class,
                null, R.style.Theme_NetHunter);
        onView(withId(R.id.btn_stop_gps)).check(matches(isDisplayed()));
    }

    @Test
    public void latitudeView_isDisplayed() {
        FragmentScenario.launchInContainer(GPSFragment.class,
                null, R.style.Theme_NetHunter);
        onView(withId(R.id.tv_latitude)).check(matches(isDisplayed()));
    }

    @Test
    public void longitudeView_isDisplayed() {
        FragmentScenario.launchInContainer(GPSFragment.class,
                null, R.style.Theme_NetHunter);
        onView(withId(R.id.tv_longitude)).check(matches(isDisplayed()));
    }

    @Test
    public void fixTypeView_defaultsToNoFix() {
        FragmentScenario.launchInContainer(GPSFragment.class,
                null, R.style.Theme_NetHunter);
        onView(withId(R.id.tv_fix_type))
                .check(matches(withText("No Fix")));
    }

    @Test
    public void nmeaRawView_isDisplayed() {
        FragmentScenario.launchInContainer(GPSFragment.class,
                null, R.style.Theme_NetHunter);
        onView(withId(R.id.tv_nmea_raw)).check(matches(isDisplayed()));
    }
}
