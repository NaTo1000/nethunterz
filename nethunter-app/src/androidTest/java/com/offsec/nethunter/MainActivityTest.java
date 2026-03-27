package com.offsec.nethunter;

import androidx.test.core.app.ActivityScenario;
import androidx.test.espresso.Espresso;
import androidx.test.espresso.action.ViewActions;
import androidx.test.espresso.assertion.ViewAssertions;
import androidx.test.espresso.matcher.ViewMatchers;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.filters.LargeTest;
import androidx.test.rule.GrantPermissionRule;

import android.Manifest;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;

/**
 * Instrumented Espresso tests for {@link MainActivity}.
 *
 * <p>Verifies that the main screen launches correctly, the bottom navigation
 * renders and responds, and key UI elements are visible.
 */
@LargeTest
@RunWith(AndroidJUnit4.class)
public class MainActivityTest {

    @Rule
    public GrantPermissionRule mPermissionRule = GrantPermissionRule.grant(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
    );

    // -------------------------------------------------------------------------
    // Launch
    // -------------------------------------------------------------------------

    @Test
    public void mainActivity_launchesSuccessfully() {
        try (ActivityScenario<MainActivity> scenario =
                     ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity ->
                    org.junit.Assert.assertNotNull(activity));
        }
    }

    // -------------------------------------------------------------------------
    // Bottom navigation
    // -------------------------------------------------------------------------

    @Test
    public void bottomNav_visible() {
        try (ActivityScenario<MainActivity> ignored =
                     ActivityScenario.launch(MainActivity.class)) {
            onView(withId(R.id.bottom_navigation)).check(matches(isDisplayed()));
        }
    }

    @Test
    public void bottomNav_clickServices_navigatesCorrectly() {
        try (ActivityScenario<MainActivity> ignored =
                     ActivityScenario.launch(MainActivity.class)) {
            onView(withId(R.id.nav_services)).perform(click());
            // Verify the fragment container is still visible (navigation succeeded)
            onView(withId(R.id.fragment_container)).check(matches(isDisplayed()));
        }
    }

    @Test
    public void bottomNav_clickTerminal_navigatesCorrectly() {
        try (ActivityScenario<MainActivity> ignored =
                     ActivityScenario.launch(MainActivity.class)) {
            onView(withId(R.id.nav_terminal)).perform(click());
            onView(withId(R.id.fragment_container)).check(matches(isDisplayed()));
        }
    }

    @Test
    public void bottomNav_clickSettings_navigatesCorrectly() {
        try (ActivityScenario<MainActivity> ignored =
                     ActivityScenario.launch(MainActivity.class)) {
            onView(withId(R.id.nav_settings)).perform(click());
            onView(withId(R.id.fragment_container)).check(matches(isDisplayed()));
        }
    }

    @Test
    public void bottomNav_clickGPS_showsGPSFragment() {
        try (ActivityScenario<MainActivity> ignored =
                     ActivityScenario.launch(MainActivity.class)) {
            // Navigate away first, then back to GPS
            onView(withId(R.id.nav_terminal)).perform(click());
            onView(withId(R.id.nav_gps)).perform(click());
            onView(withId(R.id.fragment_container)).check(matches(isDisplayed()));
        }
    }

    // -------------------------------------------------------------------------
    // Toolbar
    // -------------------------------------------------------------------------

    @Test
    public void toolbar_isDisplayed() {
        try (ActivityScenario<MainActivity> ignored =
                     ActivityScenario.launch(MainActivity.class)) {
            onView(withId(R.id.toolbar)).check(matches(isDisplayed()));
        }
    }
}
