package com.nethunterz

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.ParcelUuid
import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import no.nordicsemi.android.ble.BleManager as NordicBleManager
import no.nordicsemi.android.ble.data.Data
import java.util.UUID

private const val TAG = "BleManager"

// GATT service / characteristic UUIDs (must match nrf_module/ble_bridge.py)
private val SERVICE_UUID = UUID.fromString("12345678-1234-5678-1234-56789abcdef0")
private val CHAR_STATUS = UUID.fromString("12345678-1234-5678-1234-56789abcdef1")
private val CHAR_COMMAND = UUID.fromString("12345678-1234-5678-1234-56789abcdef2")
private val CHAR_LOG_STREAM = UUID.fromString("12345678-1234-5678-1234-56789abcdef3")
private val CHAR_FREQ_UPGRADE = UUID.fromString("12345678-1234-5678-1234-56789abcdef4")
private val CHAR_AUTH = UUID.fromString("12345678-1234-5678-1234-56789abcdef5")

/**
 * BleManager – Manages BLE connectivity between the Android app and the
 * NetHunterZ NRF runtime (nrf_module/ble_bridge.py).
 *
 * Features:
 * - Scan for and auto-connect to "NetHunterZ-NRF" devices.
 * - Authenticate using HMAC-SHA256 challenge/response.
 * - Subscribe to status, log-stream, and frequency-upgrade notifications.
 * - Send control commands (start/stop capture, frequency upgrade, rewrite).
 */
class BleManager(
    private val context: Context,
    private val eventCallback: (BleEvent) -> Unit,
) {
    private val gson = Gson()
    private val btManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
    private val btAdapter: BluetoothAdapter? = btManager.adapter
    private var scanner: BluetoothLeScanner? = null
    private var nordBleManager: NetHunterZBleManager? = null

    // -----------------------------------------------------------------------
    // Scanning
    // -----------------------------------------------------------------------

    suspend fun startScan() = withContext(Dispatchers.IO) {
        val btAdapter = btAdapter ?: run {
            eventCallback(BleEvent.Error("Bluetooth not available"))
            return@withContext
        }
        scanner = btAdapter.bluetoothLeScanner
        val filters = listOf(
            ScanFilter.Builder()
                .setServiceUuid(ParcelUuid(SERVICE_UUID))
                .build()
        )
        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()
        scanner?.startScan(filters, settings, scanCallback)
        Log.d(TAG, "BLE scan started")
        delay(10_000)
        scanner?.stopScan(scanCallback)
        Log.d(TAG, "BLE scan stopped")
    }

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            Log.d(TAG, "Found device: ${result.device.address}")
            scanner?.stopScan(this)
            connect(result.device)
        }
        override fun onScanFailed(errorCode: Int) {
            Log.e(TAG, "Scan failed: $errorCode")
            eventCallback(BleEvent.Error("BLE scan failed: $errorCode"))
        }
    }

    // -----------------------------------------------------------------------
    // Connection
    // -----------------------------------------------------------------------

    private fun connect(device: android.bluetooth.BluetoothDevice) {
        nordBleManager = NetHunterZBleManager(context, eventCallback, gson).also { mgr ->
            mgr.connect(device)
                .useAutoConnect(true)
                .retry(3, 100)
                .enqueue()
        }
    }

    // -----------------------------------------------------------------------
    // Commands
    // -----------------------------------------------------------------------

    suspend fun sendCommand(command: Map<String, Any>): Result<Unit> {
        val mgr = nordBleManager ?: return Result.failure(IllegalStateException("Not connected"))
        return mgr.sendCommand(gson.toJson(command))
    }

    fun disconnect() {
        nordBleManager?.disconnect()?.enqueue()
    }
}


// ---------------------------------------------------------------------------
// Nordic BLE Manager implementation
// ---------------------------------------------------------------------------

private class NetHunterZBleManager(
    context: Context,
    private val eventCallback: (BleEvent) -> Unit,
    private val gson: Gson,
) : NordicBleManager(context) {

    private var statusChar: android.bluetooth.BluetoothGattCharacteristic? = null
    private var commandChar: android.bluetooth.BluetoothGattCharacteristic? = null
    private var logStreamChar: android.bluetooth.BluetoothGattCharacteristic? = null
    private var freqUpgradeChar: android.bluetooth.BluetoothGattCharacteristic? = null
    private var authChar: android.bluetooth.BluetoothGattCharacteristic? = null

    override fun getGattCallback() = gattCallback

    private val gattCallback = object : BleManagerGattCallback() {
        override fun isRequiredServiceSupported(gatt: android.bluetooth.BluetoothGatt): Boolean {
            val service = gatt.getService(SERVICE_UUID) ?: return false
            statusChar = service.getCharacteristic(CHAR_STATUS)
            commandChar = service.getCharacteristic(CHAR_COMMAND)
            logStreamChar = service.getCharacteristic(CHAR_LOG_STREAM)
            freqUpgradeChar = service.getCharacteristic(CHAR_FREQ_UPGRADE)
            authChar = service.getCharacteristic(CHAR_AUTH)
            return statusChar != null && commandChar != null
        }

        override fun initialize() {
            // Enable notifications on status characteristic
            statusChar?.let {
                enableNotifications(it)
                    .with { _, data -> handleStatusNotification(data) }
                    .enqueue()
            }
            // Enable notifications on log stream
            logStreamChar?.let {
                enableNotifications(it)
                    .with { _, data -> handleLogStream(data) }
                    .enqueue()
            }
            // Enable notifications on frequency upgrade
            freqUpgradeChar?.let {
                enableNotifications(it)
                    .with { _, data -> handleFreqUpgrade(data) }
                    .enqueue()
            }
        }

        override fun onServicesInvalidated() {
            statusChar = null
            commandChar = null
            logStreamChar = null
            freqUpgradeChar = null
            authChar = null
            eventCallback(BleEvent.Disconnected)
        }
    }

    override fun onDeviceConnected(device: android.bluetooth.BluetoothDevice) {
        super.onDeviceConnected(device)
        eventCallback(BleEvent.Connected)
    }

    override fun onDeviceDisconnected(device: android.bluetooth.BluetoothDevice, reason: Int) {
        eventCallback(BleEvent.Disconnected)
    }

    // -----------------------------------------------------------------------
    // Notification handlers
    // -----------------------------------------------------------------------

    private fun handleStatusNotification(data: Data) {
        try {
            val json = gson.fromJson(data.getStringValue(0) ?: return, JsonObject::class.java)
            val nrf = json.getAsJsonObject("nrf") ?: return
            val modules = nrf.getAsJsonArray("modules") ?: return
            val m0 = modules[0].asJsonObject
            val m1 = modules[1].asJsonObject
            val status = NrfStatus(
                module0Channel = m0["channel"].asInt,
                module0FreqMhz = m0["frequency_mhz"].asDouble,
                module1Channel = m1["channel"].asInt,
                module1FreqMhz = m1["frequency_mhz"].asDouble,
                packetCount = nrf["packet_count"].asInt,
                captureRunning = nrf["running"].asBoolean,
            )
            eventCallback(BleEvent.StatusUpdate(status))
        } catch (e: Exception) {
            Log.w(TAG, "Status parse error: $e")
        }
    }

    private fun handleLogStream(data: Data) {
        try {
            val text = data.getStringValue(0) ?: return
            val json = gson.fromJson(text, JsonObject::class.java)
            val pkt = PacketItem(
                id = System.currentTimeMillis(),
                moduleId = json["module_id"].asInt,
                channel = json["channel"].asInt,
                freqMhz = json["frequency_mhz"].asDouble,
                rssi = json["rssi"].asInt,
                payload = json["payload"].asString,
                timestampMs = (json["timestamp"].asDouble * 1000).toLong(),
            )
            eventCallback(BleEvent.PacketReceived(pkt))
        } catch (e: Exception) {
            Log.w(TAG, "Log stream parse error: $e")
        }
    }

    private fun handleFreqUpgrade(data: Data) {
        try {
            val text = data.getStringValue(0) ?: return
            val json = gson.fromJson(text, JsonObject::class.java)
            eventCallback(
                BleEvent.FrequencyUpgrade(
                    moduleId = json["module_id"].asInt,
                    newChannel = json["channel"].asInt,
                    newFreqMhz = json["frequency_mhz"].asDouble,
                )
            )
        } catch (e: Exception) {
            Log.w(TAG, "Freq upgrade parse error: $e")
        }
    }

    // -----------------------------------------------------------------------
    // Commands
    // -----------------------------------------------------------------------

    suspend fun sendCommand(jsonStr: String): Result<Unit> = withContext(Dispatchers.IO) {
        val char = commandChar
            ?: return@withContext Result.failure(IllegalStateException("Command characteristic unavailable"))
        try {
            writeCharacteristic(char, jsonStr.toByteArray(), android.bluetooth.BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
                .await()
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "sendCommand failed: $e")
            Result.failure(e)
        }
    }
}
