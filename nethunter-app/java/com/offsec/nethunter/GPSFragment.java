package com.offsec.nethunter;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.Fragment;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;

import com.offsec.nethunter.GPS.GPSService;
import com.offsec.nethunter.GPS.NMEAParser;
import com.offsec.nethunter.utils.Logger;

/**
 * Fragment that displays live GPS / NMEA data from {@link GPSService}.
 *
 * <p>Listens for {@link GPSService#ACTION_GPS_UPDATE} broadcasts and updates the UI
 * with the latest parsed {@link NMEAParser.NMEAData}.
 */
public class GPSFragment extends Fragment {

    private static final String TAG = "GPSFragment";

    private TextView mLatView;
    private TextView mLonView;
    private TextView mAltView;
    private TextView mSpeedView;
    private TextView mSatView;
    private TextView mFixView;
    private TextView mNmeaRaw;
    private Button   mStartBtn;
    private Button   mStopBtn;

    private final BroadcastReceiver mGpsReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (GPSService.ACTION_GPS_UPDATE.equals(intent.getAction())) {
                double lat      = intent.getDoubleExtra(GPSService.EXTRA_LATITUDE, 0);
                double lon      = intent.getDoubleExtra(GPSService.EXTRA_LONGITUDE, 0);
                double alt      = intent.getDoubleExtra(GPSService.EXTRA_ALTITUDE, 0);
                float  speed    = intent.getFloatExtra(GPSService.EXTRA_SPEED, 0);
                int    sats     = intent.getIntExtra(GPSService.EXTRA_SATELLITES, 0);
                String fixType  = intent.getStringExtra(GPSService.EXTRA_FIX_TYPE);
                String rawNmea  = intent.getStringExtra(GPSService.EXTRA_RAW_NMEA);
                updateUI(lat, lon, alt, speed, sats, fixType, rawNmea);
            }
        }
    };

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
            @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_gps, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        mLatView  = view.findViewById(R.id.tv_latitude);
        mLonView  = view.findViewById(R.id.tv_longitude);
        mAltView  = view.findViewById(R.id.tv_altitude);
        mSpeedView = view.findViewById(R.id.tv_speed);
        mSatView  = view.findViewById(R.id.tv_satellites);
        mFixView  = view.findViewById(R.id.tv_fix_type);
        mNmeaRaw  = view.findViewById(R.id.tv_nmea_raw);
        mStartBtn = view.findViewById(R.id.btn_start_gps);
        mStopBtn  = view.findViewById(R.id.btn_stop_gps);

        mStartBtn.setOnClickListener(v -> startGpsService());
        mStopBtn.setOnClickListener(v -> stopGpsService());
    }

    @Override
    public void onStart() {
        super.onStart();
        IntentFilter filter = new IntentFilter(GPSService.ACTION_GPS_UPDATE);
        LocalBroadcastManager.getInstance(requireContext()).registerReceiver(mGpsReceiver, filter);
    }

    @Override
    public void onStop() {
        LocalBroadcastManager.getInstance(requireContext()).unregisterReceiver(mGpsReceiver);
        super.onStop();
    }

    private void startGpsService() {
        Intent intent = new Intent(requireContext(), GPSService.class);
        intent.setAction(GPSService.ACTION_START);
        ContextCompat.startForegroundService(requireContext(), intent);
        Logger.i(TAG, "GPS service start requested");
    }

    private void stopGpsService() {
        Intent intent = new Intent(requireContext(), GPSService.class);
        intent.setAction(GPSService.ACTION_STOP);
        requireContext().startService(intent);
        Logger.i(TAG, "GPS service stop requested");
    }

    private void updateUI(double lat, double lon, double alt, float speed,
            int satellites, String fixType, String rawNmea) {
        if (mLatView == null) return;
        mLatView.setText(String.format("%.6f°", lat));
        mLonView.setText(String.format("%.6f°", lon));
        mAltView.setText(String.format("%.1f m", alt));
        mSpeedView.setText(String.format("%.1f km/h", speed));
        mSatView.setText(String.valueOf(satellites));
        mFixView.setText(fixType != null ? fixType : "No fix");
        if (rawNmea != null) {
            mNmeaRaw.setText(rawNmea);
        }
    }
}
