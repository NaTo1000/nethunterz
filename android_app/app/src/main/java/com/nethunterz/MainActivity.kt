package com.nethunterz

import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModelProvider
import androidx.recyclerview.widget.LinearLayoutManager
import com.nethunterz.databinding.ActivityMainBinding

/**
 * MainActivity – Entry point for the NetHunterZ Android app.
 *
 * Displays:
 * - Live NRF module status (channel, frequency, RSSI)
 * - BLE connection state and paired device info
 * - Cloud orchestration status
 * - Recent captured packet feed
 * - Quick-action buttons: Scan, Start/Stop Capture, Frequency Upgrade
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var viewModel: MainViewModel
    private lateinit var packetAdapter: PacketAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)

        viewModel = ViewModelProvider(this)[MainViewModel::class.java]

        setupRecyclerView()
        setupClickListeners()
        observeViewModel()

        // Initialise BLE manager
        viewModel.initBle(this)
    }

    // -----------------------------------------------------------------------
    // UI setup
    // -----------------------------------------------------------------------

    private fun setupRecyclerView() {
        packetAdapter = PacketAdapter()
        binding.rvPackets.apply {
            layoutManager = LinearLayoutManager(this@MainActivity).apply {
                stackFromEnd = true
                reverseLayout = false
            }
            adapter = packetAdapter
        }
    }

    private fun setupClickListeners() {
        binding.btnScan.setOnClickListener {
            viewModel.startBleScan()
            showToast("Scanning for NetHunterZ devices…")
        }

        binding.btnStartCapture.setOnClickListener {
            viewModel.toggleCapture()
        }

        binding.btnFreqUpgrade.setOnClickListener {
            val newChannel = binding.etNewChannel.text.toString().toIntOrNull()
            if (newChannel == null || newChannel !in 0..125) {
                showToast("Enter a valid channel (0–125)")
                return@setOnClickListener
            }
            val moduleId = if (binding.rbModule0.isChecked) 0 else 1
            viewModel.requestFrequencyUpgrade(moduleId, newChannel)
        }

        binding.btnViewLogs.setOnClickListener {
            LogsActivity.start(this)
        }

        binding.btnFreqTracker.setOnClickListener {
            FrequencyTrackerActivity.start(this)
        }

        binding.swipeRefresh.setOnRefreshListener {
            viewModel.refreshStatus()
        }
    }

    private fun observeViewModel() {
        viewModel.connectionState.observe(this) { state ->
            binding.tvBleState.text = state.label
            binding.btnStartCapture.isEnabled = (state == BleConnectionState.CONNECTED)
            binding.btnFreqUpgrade.isEnabled = (state == BleConnectionState.CONNECTED)
        }

        viewModel.nrfStatus.observe(this) { status ->
            binding.tvModule0Channel.text =
                "Module 0: Ch${status.module0Channel} (${status.module0FreqMhz} MHz)"
            binding.tvModule1Channel.text =
                "Module 1: Ch${status.module1Channel} (${status.module1FreqMhz} MHz)"
            binding.tvPacketCount.text = "Packets: ${status.packetCount}"
        }

        viewModel.cloudStatus.observe(this) { cloud ->
            binding.tvCloudStatus.text =
                if (cloud.connected) "Cloud: Connected ✓" else "Cloud: Disconnected"
        }

        viewModel.captureRunning.observe(this) { running ->
            binding.btnStartCapture.text = if (running) "Stop Capture" else "Start Capture"
            binding.captureIndicator.visibility = if (running) View.VISIBLE else View.GONE
        }

        viewModel.recentPackets.observe(this) { packets ->
            packetAdapter.submitList(packets)
            if (packets.isNotEmpty()) {
                binding.rvPackets.smoothScrollToPosition(packets.size - 1)
            }
            binding.swipeRefresh.isRefreshing = false
        }

        viewModel.frequencyUpgradeEvent.observe(this) { event ->
            event?.let {
                showToast("Frequency upgraded → Ch${it.newChannel} (${it.newFreqMhz} MHz)")
            }
        }

        viewModel.errorEvent.observe(this) { err ->
            err?.let { showToast("Error: $it") }
        }
    }

    // -----------------------------------------------------------------------
    // Menu
    // -----------------------------------------------------------------------

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.main_menu, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.action_settings -> {
                showToast("Settings coming soon")
                true
            }
            R.id.action_about -> {
                showToast("NetHunterZ v1.0 – Pingequa Dual NRF + Flipper AIO")
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private fun showToast(msg: String) =
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
}
