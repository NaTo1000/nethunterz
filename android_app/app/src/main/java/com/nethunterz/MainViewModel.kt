package com.nethunterz

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch

/**
 * MainViewModel – holds all UI state for [MainActivity].
 *
 * Bridges between the Android UI layer, the [BleManager],
 * and the [CloudClient].
 */
class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val _connectionState = MutableLiveData(BleConnectionState.DISCONNECTED)
    val connectionState: LiveData<BleConnectionState> = _connectionState

    private val _nrfStatus = MutableLiveData(NrfStatus())
    val nrfStatus: LiveData<NrfStatus> = _nrfStatus

    private val _cloudStatus = MutableLiveData(CloudStatus())
    val cloudStatus: LiveData<CloudStatus> = _cloudStatus

    private val _captureRunning = MutableLiveData(false)
    val captureRunning: LiveData<Boolean> = _captureRunning

    private val _recentPackets = MutableLiveData<List<PacketItem>>(emptyList())
    val recentPackets: LiveData<List<PacketItem>> = _recentPackets

    private val _frequencyUpgradeEvent = MutableLiveData<FrequencyUpgradeEvent?>()
    val frequencyUpgradeEvent: LiveData<FrequencyUpgradeEvent?> = _frequencyUpgradeEvent

    private val _errorEvent = MutableLiveData<String?>()
    val errorEvent: LiveData<String?> = _errorEvent

    private lateinit var bleManager: BleManager
    private val cloudClient = CloudClient()

    // -----------------------------------------------------------------------

    fun initBle(context: Context) {
        bleManager = BleManager(context) { event -> handleBleEvent(event) }
    }

    fun startBleScan() {
        viewModelScope.launch {
            _connectionState.value = BleConnectionState.SCANNING
            bleManager.startScan()
        }
    }

    fun toggleCapture() {
        val cmd = if (_captureRunning.value == true) "stop_capture" else "start_capture"
        viewModelScope.launch {
            val result = bleManager.sendCommand(mapOf("action" to cmd))
            if (result.isSuccess) {
                _captureRunning.value = !(_captureRunning.value ?: false)
            } else {
                _errorEvent.value = result.exceptionOrNull()?.message
            }
        }
    }

    fun requestFrequencyUpgrade(moduleId: Int, newChannel: Int) {
        viewModelScope.launch {
            val result = bleManager.sendCommand(
                mapOf(
                    "action" to "upgrade_frequency",
                    "module_id" to moduleId,
                    "channel" to newChannel
                )
            )
            if (result.isSuccess) {
                _frequencyUpgradeEvent.value = FrequencyUpgradeEvent(
                    moduleId = moduleId,
                    newChannel = newChannel,
                    newFreqMhz = 2400.0 + newChannel,
                )
            } else {
                _errorEvent.value = result.exceptionOrNull()?.message
            }
        }
    }

    fun refreshStatus() {
        viewModelScope.launch {
            val cloudResult = cloudClient.getStatus()
            cloudResult.onSuccess { status ->
                _cloudStatus.value = CloudStatus(connected = status.running)
            }
        }
    }

    // -----------------------------------------------------------------------
    // BLE event handling
    // -----------------------------------------------------------------------

    private fun handleBleEvent(event: BleEvent) {
        when (event) {
            is BleEvent.Connected -> _connectionState.value = BleConnectionState.CONNECTED
            is BleEvent.Disconnected -> _connectionState.value = BleConnectionState.DISCONNECTED
            is BleEvent.StatusUpdate -> _nrfStatus.value = event.status
            is BleEvent.PacketReceived -> {
                val current = _recentPackets.value?.toMutableList() ?: mutableListOf()
                current.add(event.packet)
                if (current.size > 200) current.removeAt(0)
                _recentPackets.value = current
            }
            is BleEvent.FrequencyUpgrade -> {
                _frequencyUpgradeEvent.value = FrequencyUpgradeEvent(
                    moduleId = event.moduleId,
                    newChannel = event.newChannel,
                    newFreqMhz = event.newFreqMhz,
                )
            }
            is BleEvent.Error -> _errorEvent.value = event.message
        }
    }
}

// ---------------------------------------------------------------------------
// Data / state classes
// ---------------------------------------------------------------------------

enum class BleConnectionState(val label: String) {
    DISCONNECTED("Disconnected"),
    SCANNING("Scanning…"),
    CONNECTING("Connecting…"),
    CONNECTED("Connected ✓"),
}

data class NrfStatus(
    val module0Channel: Int = 76,
    val module0FreqMhz: Double = 2476.0,
    val module1Channel: Int = 100,
    val module1FreqMhz: Double = 2500.0,
    val packetCount: Int = 0,
    val captureRunning: Boolean = false,
)

data class CloudStatus(
    val connected: Boolean = false,
    val packetsUploaded: Int = 0,
    val recommendationsReceived: Int = 0,
)

data class FrequencyUpgradeEvent(
    val moduleId: Int,
    val newChannel: Int,
    val newFreqMhz: Double,
)

data class PacketItem(
    val id: Long,
    val moduleId: Int,
    val channel: Int,
    val freqMhz: Double,
    val rssi: Int,
    val payload: String,
    val timestampMs: Long,
)

sealed class BleEvent {
    object Connected : BleEvent()
    object Disconnected : BleEvent()
    data class StatusUpdate(val status: NrfStatus) : BleEvent()
    data class PacketReceived(val packet: PacketItem) : BleEvent()
    data class FrequencyUpgrade(val moduleId: Int, val newChannel: Int, val newFreqMhz: Double) : BleEvent()
    data class Error(val message: String) : BleEvent()
}
