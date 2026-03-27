package com.offsec.nethunter;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.preference.PreferenceFragmentCompat;

/**
 * Wrapper fragment that embeds the PreferenceFragment for settings.
 */
public class SettingsFragment extends Fragment {

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
            @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_settings, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        if (savedInstanceState == null) {
            getChildFragmentManager()
                    .beginTransaction()
                    .replace(R.id.settings_container, new NetHunterPreferenceFragment())
                    .commit();
        }
    }

    /** Inner PreferenceFragmentCompat that loads {@code res/xml/preferences.xml}. */
    public static class NetHunterPreferenceFragment extends PreferenceFragmentCompat {
        @Override
        public void onCreatePreferences(@Nullable Bundle savedInstanceState,
                @Nullable String rootKey) {
            // preferences.xml would be added separately; use empty screen for now
            setPreferencesFromResource(R.xml.preferences, rootKey);
        }
    }
}
