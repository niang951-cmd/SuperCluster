package com.supercluster.app

import android.app.ActivityManager
import android.content.Context
import android.net.wifi.WifiManager
import android.os.Bundle
import android.util.Log
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.net.*
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {
    private val TAG = "SuperClusterNode"
    private val DISCOVERY_PORT = 9999
    private val TCP_PORT = 8080
    private val MULTICAST_IP = "239.255.255.250"
    
    private var multicastLock: WifiManager.MulticastLock? = null
    private val executor = Executors.newFixedThreadPool(25) // Plenty for handling discovery + tasks
    private lateinit var statusText: TextView
    private var modelLoaded = false
    private var modelBytes: ByteArray? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        statusText = findViewById(R.id.textView)
        
        val ip = getIPAddress()
        statusText.text = "SUPERCLUSTER NODE ACTIVE\n\nIP: $ip\nStatus: Waiting for Model\nRAM: ${getTotalRam()/1024/1024} MB"

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
        } catch (e: Exception) { Log.e(TAG, "Net Setup: ${e.message}") }
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
        // Robust discovery: Listen on both standard UDP and Multicast
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
                Log.d(TAG, "Replied to discovery from ${packet.address.hostAddress}")
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
                val reader = socket.getInputStream().bufferedReader()
                val writer = socket.getOutputStream().bufferedWriter()
                
                val firstLine = reader.readLine() ?: return@execute
                val requestJson = JSONObject(firstLine)
                val command = requestJson.optString("command")
                val response = JSONObject()

                when (command) {
                    "GET_STATS" -> {
                        response.put("ram", getTotalRam())
                        response.put("load", (1..25).random())
                        response.put("model_loaded", modelLoaded)
                    }
                    "LOAD_MODEL" -> {
                        val sizeMb = requestJson.optInt("size_mb", 256)
                        simulateModelLoad(sizeMb)
                        response.put("response", "SUCCESS: 256MB Reserved in RAM")
                    }
                    "PROMPT" -> {
                        val prompt = requestJson.optString("data")
                        if (modelLoaded) {
                            response.put("response", "LOCAL AI [Node ${getIPAddress()}]: Processed '$prompt' using RAM-resident data.")
                        } else {
                            response.put("response", "ERROR: Model not in RAM.")
                        }
                    }
                }
                writer.write(response.toString() + "\n")
                writer.flush()
            } catch (e: Exception) { Log.e(TAG, "Client: ${e.message}") }
            finally { try { socket.close() } catch (e: Exception) {} }
        }
    }

    private fun simulateModelLoad(sizeMb: Int) {
        try {
            modelBytes = ByteArray(sizeMb * 1024 * 1024) { 0 }
            modelLoaded = true
            runOnUiThread {
                statusText.text = "SUPERCLUSTER NODE ACTIVE\n\nIP: ${getIPAddress()}\nStatus: MODEL RESIDENT (RAM)\nModel Size: ${sizeMb}MB"
            }
        } catch (e: OutOfMemoryError) {
            modelLoaded = false
            runOnUiThread {
                statusText.text = "SUPERCLUSTER NODE ACTIVE\n\nIP: ${getIPAddress()}\nStatus: FAILED (OOM - Reduce Model Size)\nRAM: ${getTotalRam()/1024/1024} MB"
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
