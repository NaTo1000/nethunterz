package com.offsec.nethunter;

import android.os.Bundle;
import android.text.method.ScrollingMovementMethod;
import android.view.KeyEvent;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import com.offsec.nethunter.utils.Logger;
import com.offsec.nethunter.utils.ShellExecutor;

/**
 * Simple terminal fragment that allows the user to run shell commands and view output.
 */
public class TerminalFragment extends Fragment {

    private static final String TAG = "TerminalFragment";

    private TextView   mOutputView;
    private EditText   mInputView;
    private ScrollView mScrollView;
    private ShellExecutor mShell;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
            @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_terminal, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        mOutputView = view.findViewById(R.id.tv_terminal_output);
        mInputView  = view.findViewById(R.id.et_command_input);
        mScrollView = view.findViewById(R.id.scroll_terminal);
        mOutputView.setMovementMethod(new ScrollingMovementMethod());

        mShell = ShellExecutor.getInstance();

        ImageButton sendBtn = view.findViewById(R.id.btn_send_command);
        sendBtn.setOnClickListener(v -> executeCommand());

        mInputView.setOnEditorActionListener((tv, actionId, event) -> {
            if (event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                    && event.getAction() == KeyEvent.ACTION_DOWN) {
                executeCommand();
                return true;
            }
            return false;
        });

        appendOutput("NetHunter Terminal Ready\n$ ");
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        mShell = null;
    }

    private void executeCommand() {
        String cmd = mInputView.getText().toString().trim();
        if (cmd.isEmpty()) return;
        mInputView.setText("");
        appendOutput("$ " + cmd + "\n");

        mShell.executeAsync(cmd, new ShellExecutor.Callback() {
            @Override
            public void onOutput(String line) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> appendOutput(line + "\n"));
                }
            }
            @Override
            public void onComplete(int exitCode) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() ->
                            appendOutput("[exit " + exitCode + "]\n$ "));
                }
            }
            @Override
            public void onError(String error) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> appendOutput("[error] " + error + "\n$ "));
                }
            }
        });
        Logger.d(TAG, "Executed command: " + cmd);
    }

    private void appendOutput(String text) {
        mOutputView.append(text);
        mScrollView.post(() -> mScrollView.fullScroll(View.FOCUS_DOWN));
    }
}
