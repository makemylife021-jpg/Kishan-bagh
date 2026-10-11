package com.kishanbagh.call

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioManager
import android.media.Ringtone
import android.media.RingtoneManager
import android.os.Build
import android.os.Bundle
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import android.view.View
import android.view.WindowManager
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.Chronometer
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.android.gms.nearby.Nearby
import com.google.android.gms.nearby.connection.AdvertisingOptions
import com.google.android.gms.nearby.connection.ConnectionInfo
import com.google.android.gms.nearby.connection.ConnectionLifecycleCallback
import com.google.android.gms.nearby.connection.ConnectionResolution
import com.google.android.gms.nearby.connection.ConnectionsClient
import com.google.android.gms.nearby.connection.DiscoveredEndpointInfo
import com.google.android.gms.nearby.connection.DiscoveryOptions
import com.google.android.gms.nearby.connection.EndpointDiscoveryCallback
import com.google.android.gms.nearby.connection.Payload
import com.google.android.gms.nearby.connection.PayloadCallback
import com.google.android.gms.nearby.connection.PayloadTransferUpdate
import com.google.android.gms.nearby.connection.Strategy

/**
 * Offline phone-to-phone calling.
 *
 * Every phone that taps "Go online" both advertises itself and looks for others using
 * Google Nearby Connections, which talks directly over Bluetooth, BLE and Wi-Fi Direct.
 * No SIM, Wi-Fi router or internet connection is used. Once two phones connect, each
 * one streams its microphone audio to the other.
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val SERVICE_ID = "com.kishanbagh.call"
        // One-to-one connection with the highest bandwidth: right for a voice call.
        private val STRATEGY = Strategy.P2P_POINT_TO_POINT
        private const val PREFS = "kishan_bagh_call"
    }

    private lateinit var connections: ConnectionsClient
    private lateinit var audioManager: AudioManager
    private val streamer = AudioStreamer()

    private lateinit var joinPanel: LinearLayout
    private lateinit var nameInput: EditText
    private lateinit var statusText: TextView
    private lateinit var peerList: ListView
    private lateinit var callPanel: LinearLayout
    private lateinit var callPeerName: TextView
    private lateinit var callState: TextView
    private lateinit var callTimer: Chronometer
    private lateinit var muteButton: Button
    private lateinit var speakerButton: Button

    private var myName = ""
    private var online = false
    private val nearby = linkedMapOf<String, String>() // endpointId -> name
    private val peerIds = mutableListOf<String>()
    private lateinit var peerAdapter: ArrayAdapter<String>

    private var callEndpointId: String? = null
    private var callName: String? = null
    private var inCall = false
    private var incomingDialog: AlertDialog? = null
    private var ringtone: Ringtone? = null

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
            if (result.values.all { it }) goOnline() else toast(getString(R.string.permissions_needed))
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        connections = Nearby.getConnectionsClient(this)
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager

        val root = findViewById<View>(R.id.root)
        val basePadding = root.paddingTop
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            v.setPadding(basePadding + bars.left, basePadding + bars.top, basePadding + bars.right, basePadding + bars.bottom)
            insets
        }

        joinPanel = findViewById(R.id.joinPanel)
        nameInput = findViewById(R.id.nameInput)
        statusText = findViewById(R.id.statusText)
        peerList = findViewById(R.id.peerList)
        callPanel = findViewById(R.id.callPanel)
        callPeerName = findViewById(R.id.callPeerName)
        callState = findViewById(R.id.callState)
        callTimer = findViewById(R.id.callTimer)
        muteButton = findViewById(R.id.muteButton)
        speakerButton = findViewById(R.id.speakerButton)

        peerAdapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, mutableListOf())
        peerList.adapter = peerAdapter
        peerList.setOnItemClickListener { _, _, position, _ -> placeCall(peerIds[position]) }

        nameInput.setText(getSharedPreferences(PREFS, MODE_PRIVATE).getString("name", ""))
        findViewById<Button>(R.id.goOnlineButton).setOnClickListener { onGoOnlineClicked() }
        findViewById<Button>(R.id.hangUpButton).setOnClickListener { hangUp() }
        muteButton.setOnClickListener {
            streamer.muted = !streamer.muted
            muteButton.setText(if (streamer.muted) R.string.unmute else R.string.mute)
        }
        speakerButton.setOnClickListener { setSpeaker(!isSpeakerOn()) }
    }

    override fun onDestroy() {
        stopRinging()
        streamer.stop()
        connections.stopAllEndpoints()
        connections.stopAdvertising()
        connections.stopDiscovery()
        audioManager.mode = AudioManager.MODE_NORMAL
        super.onDestroy()
    }

    // ---------- Going online ----------

    private fun requiredPermissions(): Array<String> {
        val perms = mutableListOf(Manifest.permission.RECORD_AUDIO)
        when {
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU -> perms += listOf(
                Manifest.permission.BLUETOOTH_ADVERTISE,
                Manifest.permission.BLUETOOTH_CONNECT,
                Manifest.permission.BLUETOOTH_SCAN,
                Manifest.permission.NEARBY_WIFI_DEVICES,
            )
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> perms += listOf(
                Manifest.permission.BLUETOOTH_ADVERTISE,
                Manifest.permission.BLUETOOTH_CONNECT,
                Manifest.permission.BLUETOOTH_SCAN,
                Manifest.permission.ACCESS_FINE_LOCATION,
            )
            else -> perms += Manifest.permission.ACCESS_FINE_LOCATION
        }
        return perms.toTypedArray()
    }

    private fun onGoOnlineClicked() {
        val name = nameInput.text.toString().trim()
        if (name.isEmpty()) {
            nameInput.error = getString(R.string.enter_name)
            return
        }
        myName = name
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("name", name).apply()
        val missing = requiredPermissions().filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) goOnline() else permissionLauncher.launch(missing.toTypedArray())
    }

    private fun goOnline() {
        online = true
        joinPanel.visibility = View.GONE
        startSearching()
    }

    private fun startSearching() {
        nearby.clear()
        refreshPeers()
        connections.startAdvertising(
            myName, SERVICE_ID, connectionCallback,
            AdvertisingOptions.Builder().setStrategy(STRATEGY).build()
        ).addOnFailureListener { onStartFailure(it) }
        connections.startDiscovery(
            SERVICE_ID, discoveryCallback,
            DiscoveryOptions.Builder().setStrategy(STRATEGY).build()
        ).addOnFailureListener { onStartFailure(it) }
    }

    private fun stopSearching() {
        connections.stopAdvertising()
        connections.stopDiscovery()
    }

    private fun onStartFailure(e: Exception) {
        // "Already advertising/discovering" is harmless; anything else is shown to the user.
        val message = e.message ?: return
        if (message.contains("8001") || message.contains("8002")) return
        toast(getString(R.string.start_failed, message))
    }

    private val discoveryCallback = object : EndpointDiscoveryCallback() {
        override fun onEndpointFound(endpointId: String, info: DiscoveredEndpointInfo) {
            if (info.serviceId != SERVICE_ID) return
            nearby[endpointId] = info.endpointName
            refreshPeers()
        }

        override fun onEndpointLost(endpointId: String) {
            nearby.remove(endpointId)
            refreshPeers()
        }
    }

    private fun refreshPeers() {
        peerIds.clear()
        peerIds += nearby.keys
        peerAdapter.clear()
        peerAdapter.addAll(nearby.values.map { "📞  $it" })
        statusText.text = when {
            !online -> ""
            nearby.isEmpty() -> getString(R.string.no_peers)
            else -> getString(R.string.searching, myName)
        }
    }

    // ---------- Call setup ----------

    private fun placeCall(endpointId: String) {
        if (inCall || callEndpointId != null) return
        callEndpointId = endpointId
        callName = nearby[endpointId]
        showCallPanel(getString(R.string.calling))
        connections.requestConnection(myName, endpointId, connectionCallback)
            .addOnFailureListener {
                toast(getString(R.string.call_failed))
                resetAfterCall()
            }
    }

    private val connectionCallback = object : ConnectionLifecycleCallback() {
        override fun onConnectionInitiated(endpointId: String, info: ConnectionInfo) {
            if (!info.isIncomingConnection) {
                // We placed this call: accept our side straight away.
                connections.acceptConnection(endpointId, payloadCallback)
                return
            }
            if (inCall || callEndpointId != null) {
                connections.rejectConnection(endpointId) // Busy.
                return
            }
            callEndpointId = endpointId
            callName = info.endpointName
            showIncomingCall(endpointId, info.endpointName)
        }

        override fun onConnectionResult(endpointId: String, resolution: ConnectionResolution) {
            if (endpointId != callEndpointId) return
            if (resolution.status.isSuccess) {
                startAudio(endpointId)
            } else {
                toast(getString(R.string.call_declined))
                resetAfterCall()
            }
        }

        override fun onDisconnected(endpointId: String) {
            if (endpointId != callEndpointId) return
            toast(getString(R.string.call_ended))
            resetAfterCall()
        }
    }

    private fun showIncomingCall(endpointId: String, name: String) {
        startRinging()
        incomingDialog = AlertDialog.Builder(this)
            .setTitle(R.string.incoming_title)
            .setMessage(getString(R.string.incoming_message, name))
            .setCancelable(false)
            .setPositiveButton(R.string.answer) { _, _ ->
                stopRinging()
                showCallPanel(getString(R.string.calling))
                connections.acceptConnection(endpointId, payloadCallback)
            }
            .setNegativeButton(R.string.decline) { _, _ ->
                stopRinging()
                connections.rejectConnection(endpointId)
                resetAfterCall()
            }
            .show()
    }

    // ---------- Audio ----------

    private fun startAudio(endpointId: String) {
        inCall = true
        stopSearching() // Frees the radio for the call itself.
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
        setSpeaker(false)

        val pipe = ParcelFileDescriptor.createPipe()
        connections.sendPayload(endpointId, Payload.fromStream(pipe[0]))
        streamer.startSending(ParcelFileDescriptor.AutoCloseOutputStream(pipe[1]))

        showCallPanel(getString(R.string.connected))
        callTimer.base = SystemClock.elapsedRealtime()
        callTimer.start()
    }

    private val payloadCallback = object : PayloadCallback() {
        override fun onPayloadReceived(endpointId: String, payload: Payload) {
            if (payload.type == Payload.Type.STREAM && endpointId == callEndpointId) {
                payload.asStream()?.asInputStream()?.let { streamer.startPlaying(it) }
            }
        }

        override fun onPayloadTransferUpdate(endpointId: String, update: PayloadTransferUpdate) = Unit
    }

    private fun hangUp() {
        callEndpointId?.let { connections.disconnectFromEndpoint(it) }
        toast(getString(R.string.call_ended))
        resetAfterCall()
    }

    private fun resetAfterCall() {
        val wasInCall = inCall
        inCall = false
        callEndpointId = null
        callName = null
        incomingDialog?.dismiss()
        incomingDialog = null
        stopRinging()
        streamer.stop()
        callTimer.stop()
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setSpeaker(false)
        audioManager.mode = AudioManager.MODE_NORMAL
        callPanel.visibility = View.GONE
        peerList.visibility = View.VISIBLE
        muteButton.setText(R.string.mute)
        if (online && wasInCall) startSearching() else refreshPeers()
    }

    private fun showCallPanel(state: String) {
        peerList.visibility = View.GONE
        callPanel.visibility = View.VISIBLE
        callPeerName.text = callName ?: ""
        callState.text = state
    }

    @Suppress("DEPRECATION")
    private fun isSpeakerOn() = audioManager.isSpeakerphoneOn

    @Suppress("DEPRECATION")
    private fun setSpeaker(on: Boolean) {
        audioManager.isSpeakerphoneOn = on
        speakerButton.setText(if (on) R.string.speaker_off else R.string.speaker_on)
    }

    private fun startRinging() {
        stopRinging()
        ringtone = RingtoneManager.getRingtone(this, RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE))
        ringtone?.play()
    }

    private fun stopRinging() {
        ringtone?.stop()
        ringtone = null
    }

    private fun toast(text: String) = Toast.makeText(this, text, Toast.LENGTH_LONG).show()
}
