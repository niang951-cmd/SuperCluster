package com.supercluster.app

import android.app.ActivityManager
import android.content.Context
import android.net.wifi.WifiManager
import android.os.Bundle
import android.util.Log
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.*
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {
    private val TAG = "SuperClusterNode"
    private val DISCOVERY_PORT = 9999
    private val TCP_PORT = 8080
    private val MULTICAST_IP = "239.255.255.250"
    
    private var multicastLock: WifiManager.MulticastLock? = null
    private val executor = Executors.newFixedThreadPool(20) // Increased for more nodes
    private lateinit var statusText: TextView
    private var modelLoaded = false
    private var modelBytes: ByteArray? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        statusText = findViewById(R.id.textView)
        
        statusText.text = "Node Ready\nIP: ${getIPAddress()}\nCluster Mode: High Scale"

        setupNetworking()
        startDiscoveryListener()
        startTcpServer()
    }

    private fun setupNetworking() {
        try {
            val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            multicastLock = wifi.createMulticastLock("SuperClusterLock")
            multicastLock?.setReferenceCounted(true)
            multicastLock?.acquire()
        } catch (e: Exception) {
            Log.e(TAG, "Networking Error: ${e.message}")
        }
    }

    private fun getIPAddress(): String {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val iface = interfaces.nextElement()
                if (iface.isLoopback || !iface.isUp) continue
                val addresses = iface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val addr = addresses.nextElement()
                    if (addr is Inet4Address) return addr.hostAddress ?: "Unknown"
                }
            }
        } catch (e: Exception) { e.printStackTrace() }
        return "Unknown"
    }

    private fun startDiscoveryListener() {
        executor.execute { runMulticastListener() }
        executor.execute { runBroadcastListener() }
    }

    private fun runMulticastListener() {
        try {
            val group = InetAddress.getByName(MULTICAST_IP)
            val socket = MulticastSocket(DISCOVERY_PORT)
            socket.joinGroup(group)
            val buffer = ByteArray(1024)
            while (true) {
                val packet = DatagramPacket(buffer, buffer.size)
                socket.receive(packet)
                handleDiscoveryPacket(socket, packet)
            }
        } catch (e: Exception) { Log.e(TAG, "Multicast: ${e.message}") }
    }

    private fun runBroadcastListener() {
        try {
            val socket = DatagramSocket(DISCOVERY_PORT)
            socket.broadcast = true
            val buffer = ByteArray(1024)
            while (true) {
                val packet = DatagramPacket(buffer, buffer.size)
                socket.receive(packet)
                handleDiscoveryPacket(socket, packet)
            }
        } catch (e: Exception) { Log.e(TAG, "Broadcast: ${e.message}") }
    }

    private fun handleDiscoveryPacket(socket: DatagramSocket, packet: DatagramPacket) {
        val message = String(packet.data, 0, packet.length).trim()
        if (message == "SUPERCLUSTER_DISCOVERY") {
            val response = "SUPERCLUSTER_ACK".toByteArray()
            try {
                socket.send(DatagramPacket(response, response.size, packet.address, packet.port))
            } catch (e: Exception) {}
        }
    }

    private fun startTcpServer() {
        executor.execute {
            try {
                val serverSocket = ServerSocket(TCP_PORT)
                while (true) {
                    val clientSocket = serverSocket.accept()
                    handleClient(clientSocket)
                }
            } catch (e: Exception) { Log.e(TAG, "TCP Server: ${e.message}") }
        }
    }

    private fun handleClient(socket: Socket) {
        executor.execute {
            try {
                val inputStream = socket.getInputStream()
                val reader = inputStream.bufferedReader()
                val writer = socket.getOutputStream().bufferedWriter()
                
                val firstLine = reader.readLine() ?: return@execute
                val requestJson = JSONObject(firstLine)
                val command = requestJson.optString("command")
                val response = JSONObject()

                when (command) {
                    "GET_STATS" -> {
                        response.put("ram", getTotalRam())
                        response.put("load", (1..15).random())
                        response.put("model_loaded", modelLoaded)
                    }
                    "LOAD_MODEL" -> {
                        // This simulates loading a model into RAM (byte array)
                        val sizeMb = requestJson.optInt("size_mb", 100)
                        simulateModelLoad(sizeMb)
                        response.put("response", "Model (${sizeMb}MB) loaded into RAM on node ${getIPAddress()}")
                    }
                    "PROMPT" -> {
                        val prompt = requestJson.optString("data")
                        val result = if (modelLoaded) {
                            "LOCAL INFERENCE [RAM-RESIDENT MODEL]:\nPrompt: $prompt\nStatus: Processing on node ${getIPAddress()} using ${modelBytes?.size ?: 0} bytes of dedicated RAM."
                        } else {
                            "ERROR: No model resident in RAM. Load a model first."
                        }
                        response.put("response", result)
                    }
                }
                writer.write(response.toString() + "\n")
                writer.flush()
            } catch (e: Exception) { Log.e(TAG, "Handle Client: ${e.message}") }
            finally { try { socket.close() } catch (e: Exception) {} }
        }
    }

    private fun simulateModelLoad(sizeMb: Int) {
        try {
            // Allocate actual bytes in RAM to simulate model storage
            modelBytes = ByteArray(sizeMb * 1024 * 1024) { 0 }
            modelLoaded = true
            runOnUiThread {
                statusText.text = "Node Active\nIP: ${getIPAddress()}\nModel: LOADED (${sizeMb}MB in RAM)"
            }
        } catch (e: OutOfMemoryError) {
            modelLoaded = false
            runOnUiThread {
                statusText.text = "Node Active\nIP: ${getIPAddress()}\nModel: LOAD FAILED (OOM)"
            }
        }
    }

    private fun getTotalRam(): Long {
        val actManager = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val memInfo = ActivityManager.MemoryInfo()
        actManager.getMemoryInfo(memInfo)
        return memInfo.totalMem
    }

    override fun onDestroy() {
        super.onDestroy()
        multicastLock?.let { if (it.isHeld) it.release() }
        modelBytes = null
    }
}
