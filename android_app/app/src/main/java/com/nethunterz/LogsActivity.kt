package com.nethunterz

import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.nethunterz.databinding.ActivityLogsBinding

/**
 * LogsActivity – Displays runtime NRF capture logs and operational events.
 */
class LogsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLogsBinding

    companion object {
        fun start(context: Context) =
            context.startActivity(Intent(context, LogsActivity::class.java))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLogsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        title = getString(R.string.title_logs)

        binding.rvLogs.layoutManager = LinearLayoutManager(this).apply {
            stackFromEnd = true
        }
        // Log adapter is populated by the ViewModel in a real implementation
    }

    override fun onSupportNavigateUp(): Boolean {
        onBackPressedDispatcher.onBackPressed()
        return true
    }
}
