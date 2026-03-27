package com.offsec.nethunter;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.MenuItem;
import android.view.View;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.ActionBarDrawerToggle;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.drawerlayout.widget.DrawerLayout;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentManager;
import androidx.fragment.app.FragmentTransaction;

import com.google.android.material.bottomnavigation.BottomNavigationView;
import com.google.android.material.navigation.NavigationView;
import com.offsec.nethunter.service.NetHunterService;
import com.offsec.nethunter.utils.Logger;
import com.offsec.nethunter.utils.SystemUtils;

import java.util.ArrayList;
import java.util.List;

/**
 * Main entry-point activity for NetHunter.
 *
 * <p>Hosts a {@link DrawerLayout} with a side {@link NavigationView} and a
 * {@link BottomNavigationView}. Navigation between GPS, Services, Terminal, and Settings
 * fragments is handled here. Root-access and runtime permission checks are performed at
 * startup.
 */
public class MainActivity extends AppCompatActivity
        implements NavigationView.OnNavigationItemSelectedListener {

    private static final String TAG = "MainActivity";

    private static final int REQUEST_PERMISSIONS = 100;
    private static final String[] REQUIRED_PERMISSIONS;

    static {
        List<String> perms = new ArrayList<>();
        perms.add(Manifest.permission.ACCESS_FINE_LOCATION);
        perms.add(Manifest.permission.ACCESS_COARSE_LOCATION);
        perms.add(Manifest.permission.READ_EXTERNAL_STORAGE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            perms.add(Manifest.permission.POST_NOTIFICATIONS);
        }
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P) {
            perms.add(Manifest.permission.WRITE_EXTERNAL_STORAGE);
        }
        REQUIRED_PERMISSIONS = perms.toArray(new String[0]);
    }

    private DrawerLayout mDrawerLayout;
    private ActionBarDrawerToggle mDrawerToggle;
    private BottomNavigationView mBottomNav;
    private NavigationView mNavView;

    // -------------------------------------------------------------------------
    // Lifecycle
    // -------------------------------------------------------------------------

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        bindViews();
        setupToolbar();
        setupDrawer();
        setupBottomNavigation();
        setupNavigationView();

        if (savedInstanceState == null) {
            showFragment(new GPSFragment(), "gps");
            mBottomNav.setSelectedItemId(R.id.nav_gps);
        }

        checkRootAndWarn();
        requestMissingPermissions();
    }

    @Override
    protected void onPostCreate(Bundle savedInstanceState) {
        super.onPostCreate(savedInstanceState);
        mDrawerToggle.syncState();
    }

    @Override
    public void onBackPressed() {
        if (mDrawerLayout.isDrawerOpen(mNavView)) {
            mDrawerLayout.closeDrawer(mNavView);
        } else {
            super.onBackPressed();
        }
    }

    // -------------------------------------------------------------------------
    // View binding
    // -------------------------------------------------------------------------

    private void bindViews() {
        mDrawerLayout = findViewById(R.id.drawer_layout);
        mBottomNav    = findViewById(R.id.bottom_navigation);
        mNavView      = findViewById(R.id.nav_view);
    }

    // -------------------------------------------------------------------------
    // Toolbar / Drawer
    // -------------------------------------------------------------------------

    private void setupToolbar() {
        androidx.appcompat.widget.Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
    }

    private void setupDrawer() {
        mDrawerToggle = new ActionBarDrawerToggle(
                this, mDrawerLayout,
                R.string.navigation_drawer_open,
                R.string.navigation_drawer_close);
        mDrawerLayout.addDrawerListener(mDrawerToggle);
        if (getSupportActionBar() != null) {
            getSupportActionBar().setDisplayHomeAsUpEnabled(true);
            getSupportActionBar().setHomeButtonEnabled(true);
        }
    }

    private void setupNavigationView() {
        mNavView.setNavigationItemSelectedListener(this);
    }

    // -------------------------------------------------------------------------
    // Bottom Navigation
    // -------------------------------------------------------------------------

    private void setupBottomNavigation() {
        mBottomNav.setOnItemSelectedListener(item -> {
            int id = item.getItemId();
            if (id == R.id.nav_gps) {
                showFragment(new GPSFragment(), "gps");
                return true;
            } else if (id == R.id.nav_services) {
                showFragment(new ServicesFragment(), "services");
                return true;
            } else if (id == R.id.nav_terminal) {
                showFragment(new TerminalFragment(), "terminal");
                return true;
            } else if (id == R.id.nav_settings) {
                showFragment(new SettingsFragment(), "settings");
                return true;
            }
            return false;
        });
    }

    // -------------------------------------------------------------------------
    // NavigationView.OnNavigationItemSelectedListener
    // -------------------------------------------------------------------------

    @Override
    public boolean onNavigationItemSelected(@NonNull MenuItem item) {
        int id = item.getItemId();
        if (id == R.id.menu_start_service) {
            startNetHunterService();
        } else if (id == R.id.menu_stop_service) {
            stopNetHunterService();
        } else if (id == R.id.menu_about) {
            showAboutDialog();
        }
        mDrawerLayout.closeDrawer(mNavView);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(@NonNull MenuItem item) {
        if (mDrawerToggle.onOptionsItemSelected(item)) {
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    // -------------------------------------------------------------------------
    // Fragment management
    // -------------------------------------------------------------------------

    /**
     * Replaces the main content frame with the given fragment, adding to the back stack unless
     * the fragment is the initial destination.
     *
     * @param fragment the fragment to display
     * @param tag      a unique tag for back-stack management
     */
    private void showFragment(@NonNull Fragment fragment, @NonNull String tag) {
        FragmentManager fm = getSupportFragmentManager();
        Fragment existing = fm.findFragmentByTag(tag);
        if (existing != null && existing.isVisible()) {
            return;
        }
        FragmentTransaction ft = fm.beginTransaction();
        ft.setCustomAnimations(android.R.anim.fade_in, android.R.anim.fade_out);
        ft.replace(R.id.fragment_container, fragment, tag);
        ft.commit();
        Logger.d(TAG, "Showing fragment: " + tag);
    }

    // -------------------------------------------------------------------------
    // Service control
    // -------------------------------------------------------------------------

    private void startNetHunterService() {
        Intent intent = new Intent(this, NetHunterService.class);
        intent.setAction(NetHunterService.ACTION_START);
        ContextCompat.startForegroundService(this, intent);
        Toast.makeText(this, R.string.service_starting, Toast.LENGTH_SHORT).show();
        Logger.i(TAG, "NetHunterService start requested");
    }

    private void stopNetHunterService() {
        Intent intent = new Intent(this, NetHunterService.class);
        intent.setAction(NetHunterService.ACTION_STOP);
        startService(intent);
        Toast.makeText(this, R.string.service_stopping, Toast.LENGTH_SHORT).show();
        Logger.i(TAG, "NetHunterService stop requested");
    }

    // -------------------------------------------------------------------------
    // Root warning
    // -------------------------------------------------------------------------

    private void checkRootAndWarn() {
        if (!SystemUtils.isRootAvailable()) {
            new AlertDialog.Builder(this)
                    .setTitle(R.string.warning_no_root_title)
                    .setMessage(R.string.warning_no_root_message)
                    .setPositiveButton(android.R.string.ok, null)
                    .setIcon(android.R.drawable.ic_dialog_alert)
                    .show();
            Logger.w(TAG, "Displayed no-root warning dialog");
        }
    }

    // -------------------------------------------------------------------------
    // Permissions
    // -------------------------------------------------------------------------

    private void requestMissingPermissions() {
        List<String> missing = new ArrayList<>();
        for (String perm : REQUIRED_PERMISSIONS) {
            if (ContextCompat.checkSelfPermission(this, perm)
                    != PackageManager.PERMISSION_GRANTED) {
                missing.add(perm);
            }
        }
        if (!missing.isEmpty()) {
            ActivityCompat.requestPermissions(this,
                    missing.toArray(new String[0]), REQUEST_PERMISSIONS);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode,
            @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_PERMISSIONS) {
            boolean allGranted = true;
            for (int result : grantResults) {
                if (result != PackageManager.PERMISSION_GRANTED) {
                    allGranted = false;
                    break;
                }
            }
            if (!allGranted) {
                Logger.w(TAG, "Some permissions were denied by the user");
                Toast.makeText(this, R.string.permissions_denied_warning,
                        Toast.LENGTH_LONG).show();
            } else {
                Logger.i(TAG, "All requested permissions granted");
            }
        }
    }

    // -------------------------------------------------------------------------
    // About dialog
    // -------------------------------------------------------------------------

    private void showAboutDialog() {
        String info = "NetHunter\n"
                + "Version: " + BuildConfig.VERSION_NAME + "\n\n"
                + "Android security and penetration testing platform.\n"
                + "Based on the Kali Linux NetHunter project.";

        new AlertDialog.Builder(this)
                .setTitle(R.string.about_title)
                .setMessage(info)
                .setPositiveButton(android.R.string.ok, null)
                .show();
    }
}
