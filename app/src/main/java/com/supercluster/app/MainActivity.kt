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
    private val executor = Executors.newCachedThreadPool() // Dynamic thread pool
    private lateinit var statusText: TextView
    private var modelLoaded = false
    private var modelBytes: ByteArray? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        statusText = findViewById(R.id.textView)
        
        updateStatus("Ready\nIP: ${getIPAddress()}\nRAM: ${getTotalRam()/1024/1024} MB")

        setupNetworking()
        startDiscoveryListener()
        startTcpServer()
    }

    private fun updateStatus(text: String) {
        runOnUiThread { statusText.text = "SUPERCLUSTER NODE\n\n$text" }
    }

    private fun setupNetworking() {
        try {
            val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            multicastLock = wifi.createMulticastLock("SuperClusterLock")
            multicastLock?.setReferenceCounted(true)
            multicastLock?.acquire()
        } catch (e: Exception) { Log.e(TAG, "Net Error: ${e.message}") }
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
        } catch (e: Exception) {}
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
        } catch (e: Exception) {}
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
        } catch (e: Exception) {}
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
            } catch (e: Exception) {}
        }
    }

    private fun handleClient(socket: Socket) {
        executor.execute {
            try {
                socket.soTimeout = 10000
                val reader = socket.getInputStream().bufferedReader()
                val writer = socket.getOutputStream().bufferedWriter()
                
                val firstLine = reader.readLine() ?: return@execute
                val requestJson = JSONObject(firstLine)
                val command = requestJson.optString("command")
                val response = JSONObject()

                when (command) {
                    "GET_STATS" -> {
                        response.put("ram", getTotalRam())
                        response.put("load", (1..20).random())
                        response.put("model_loaded", modelLoaded)
                    }
                    "LOAD_MODEL" -> {
                        // Use a much smaller model for better cluster scalability (64MB)
                        val sizeMb = requestJson.optInt("size_mb", 64)
                        simulateModelLoad(sizeMb)
                        response.put("response", "LOADED_OK")
                    }
                    "PROMPT" -> {
                        val prompt = requestJson.optString("data")
                        if (modelLoaded) {
                            response.put("response", "Processed on node ${getIPAddress()} using Tiny-Model (64MB RAM)")
                        } else {
                            response.put("response", "ERROR_NO_MODEL")
                        }
                    }
                }
                writer.write(response.toString() + "\n")
                writer.flush()
            } catch (e: Exception) {}
            finally { try { socket.close() } catch (e: Exception) {} }
        }
    }

    private fun simulateModelLoad(sizeMb: Int) {
        try {
            modelBytes = ByteArray(sizeMb * 1024 * 1024) { 0 }
            modelLoaded = true
            updateStatus("IP: ${getIPAddress()}\nSTATUS: MODEL IN RAM\nSIZE: ${sizeMb} MB")
        } catch (e: OutOfMemoryError) {
            modelLoaded = false
            updateStatus("IP: ${getIPAddress()}\nSTATUS: MEMORY FULL\nRAM: ${getTotalRam()/1024/1024} MB")
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
