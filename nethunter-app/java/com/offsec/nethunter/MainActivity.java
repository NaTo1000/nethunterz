package com.offsec.nethunter;

import android.Manifest;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.IBinder;
import android.util.Log;
import android.view.MenuItem;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentManager;
import androidx.fragment.app.FragmentTransaction;

import com.google.android.material.bottomnavigation.BottomNavigationView;
import com.offsec.nethunter.service.NethunterService;

import java.util.ArrayList;
import java.util.List;

public class MainActivity extends AppCompatActivity implements ServiceConnection {

    private static final String TAG = "MainActivity";

    private BottomNavigationView bottomNavigationView;
    private NethunterService.LocalBinder serviceBinder;
    private boolean isServiceBound = false;

    private final ActivityResultLauncher<String[]> permissionLauncher =
        registerForActivityResult(new ActivityResultContracts.RequestMultiplePermissions(), result -> {
            boolean allGranted = true;
            for (Boolean granted : result.values()) {
                if (!granted) {
                    allGranted = false;
                    break;
                }
            }
            if (allGranted) {
                Log.d(TAG, "All permissions granted");
                startNethunterService();
            } else {
                Toast.makeText(this, R.string.permissions_required, Toast.LENGTH_LONG).show();
            }
        });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        setupBottomNavigation();
        checkAndRequestPermissions();

        if (savedInstanceState == null) {
            loadFragment(new FlipperFragment());
        }
    }

    private void setupBottomNavigation() {
        bottomNavigationView = findViewById(R.id.bottom_navigation);
        bottomNavigationView.setOnItemSelectedListener(item -> {
            Fragment fragment = null;
            int itemId = item.getItemId();
            if (itemId == R.id.nav_flipper) {
                fragment = new FlipperFragment();
            } else if (itemId == R.id.nav_ai_control) {
                fragment = new AiControlFragment();
            } else if (itemId == R.id.nav_firmware) {
                fragment = new FirmwareFragment();
            } else if (itemId == R.id.nav_terminal) {
                fragment = new TerminalFragment();
            }
            if (fragment != null) {
                loadFragment(fragment);
                return true;
            }
            return false;
        });
    }

    private void loadFragment(@NonNull Fragment fragment) {
        FragmentManager fm = getSupportFragmentManager();
        FragmentTransaction ft = fm.beginTransaction();
        ft.replace(R.id.fragment_container, fragment);
        ft.commit();
    }

    private void checkAndRequestPermissions() {
        List<String> permissions = new ArrayList<>();
        String[] requiredPermissions = {
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.READ_EXTERNAL_STORAGE,
            Manifest.permission.WRITE_EXTERNAL_STORAGE
        };

        for (String permission : requiredPermissions) {
            if (ContextCompat.checkSelfPermission(this, permission)
                    != PackageManager.PERMISSION_GRANTED) {
                permissions.add(permission);
            }
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT)
                    != PackageManager.PERMISSION_GRANTED) {
                permissions.add(Manifest.permission.BLUETOOTH_CONNECT);
            }
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_SCAN)
                    != PackageManager.PERMISSION_GRANTED) {
                permissions.add(Manifest.permission.BLUETOOTH_SCAN);
            }
        }

        if (!permissions.isEmpty()) {
            permissionLauncher.launch(permissions.toArray(new String[0]));
        } else {
            startNethunterService();
        }
    }

    private void startNethunterService() {
        Intent serviceIntent = new Intent(this, NethunterService.class);
        serviceIntent.setAction(NethunterService.ACTION_START_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent);
        } else {
            startService(serviceIntent);
        }
        bindService(serviceIntent, this, Context.BIND_AUTO_CREATE);
    }

    @Override
    public void onServiceConnected(ComponentName name, IBinder service) {
        serviceBinder = (NethunterService.LocalBinder) service;
        isServiceBound = true;
        Log.d(TAG, "NethunterService connected");
    }

    @Override
    public void onServiceDisconnected(ComponentName name) {
        serviceBinder = null;
        isServiceBound = false;
        Log.d(TAG, "NethunterService disconnected");
    }

    public NethunterService getService() {
        if (isServiceBound && serviceBinder != null) {
            return serviceBinder.getService();
        }
        return null;
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (isServiceBound) {
            unbindService(this);
            isServiceBound = false;
        }
    }

    @Override
    public boolean onOptionsItemSelected(@NonNull MenuItem item) {
        return super.onOptionsItemSelected(item);
    }
}
