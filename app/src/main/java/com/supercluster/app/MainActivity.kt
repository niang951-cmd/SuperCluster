package com.supercluster.app

import android.app.ActivityManager
import android.content.Context
import android.net.wifi.WifiManager
import android.os.Bundle
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
    private val executor = Executors.newCachedThreadPool()
    private lateinit var statusText: TextView
    private var modelLoaded = false
    private var modelBytes: ByteArray? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        statusText = findViewById(R.id.textView)
        updateUI("Node Initialized\nIP: ${getIPAddress()}")
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
        } catch (e: Exception) {}
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
        executor.execute { runDiscovery("Multicast", MulticastSocket(DISCOVERY_PORT).apply { joinGroup(InetAddress.getByName(MULTICAST_IP)) }) }
        executor.execute { runDiscovery("Broadcast", DatagramSocket(DISCOVERY_PORT).apply { broadcast = true }) }
    }

    private fun runDiscovery(type: String, socket: DatagramSocket) {
        try {
            val buffer = ByteArray(1024)
            while (true) {
                val packet = DatagramPacket(buffer, buffer.size)
                socket.receive(packet)
                if (String(packet.data, 0, packet.length).trim() == "SUPERCLUSTER_DISCOVERY") {
                    val resp = "SUPERCLUSTER_ACK".toByteArray()
                    socket.send(DatagramPacket(resp, resp.size, packet.address, packet.port))
                }
            }
        } catch (e: Exception) {}
    }

    private fun startTcpServer() {
        executor.execute {
            try {
                val server = ServerSocket(TCP_PORT)
                while (true) handleClient(server.accept())
            } catch (e: Exception) {}
        }
    }

    private fun handleClient(socket: Socket) {
        executor.execute {
            try {
                val reader = socket.getInputStream().bufferedReader()
                val writer = socket.getOutputStream().bufferedWriter()
                val request = JSONObject(reader.readLine() ?: return@execute)
                val response = JSONObject()

                when (request.optString("command")) {
                    "GET_STATS" -> {
                        response.put("ram", getTotalRam())
                        response.put("load", (5..40).random())
                        response.put("model_loaded", modelLoaded)
                    }
                    "LOAD_MODEL" -> {
                        val sizeMb = request.optInt("size_mb", 64)
                        modelBytes = ByteArray(sizeMb * 1024 * 1024) { (0..255).random().toByte() }
                        modelLoaded = true
                        updateUI("IP: ${getIPAddress()}\nMODE: AI CLUSTER\nMODEL: RESIDENT (${sizeMb}MB)")
                        response.put("response", "LOADED_OK")
                    }
                    "PROMPT" -> {
                        val prompt = request.optString("data").lowercase()
                        response.put("response", generateAIResponse(prompt))
                    }
                }
                writer.write(response.toString() + "\n")
                writer.flush()
            } catch (e: Exception) {} finally { socket.close() }
        }
    }

    private fun generateAIResponse(prompt: String): String {
        if (!modelLoaded) return "Error: Model not in RAM."
        
        // Simuler une "réflexion" utilisant les données en RAM
        Thread.sleep(800) 
        
        return when {
            prompt.contains("bonjour") || prompt.contains("hello") -> 
                "Greetings! This is Cluster Node ${getIPAddress()}. My local 64MB model is active and ready to assist you."
            prompt.contains("statut") || prompt.contains("status") ->
                "Node Health: Optimal. Memory: ${getTotalRam()/1024/1024}MB total, ${modelBytes?.size ?: 0} bytes dedicated to AI weights."
            prompt.contains("analyse") ->
                "Analyzing cluster synchronization... Data packets are being distributed across the ${getIPAddress()} interface with 0.4ms latency."
            else -> "I have processed your request: '$prompt'. The distributed inference engine on this node is currently operating at peak efficiency."
        }
    }

    private fun getTotalRam(): Long {
        val memInfo = ActivityManager.MemoryInfo()
        (getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(memInfo)
        return memInfo.totalMem
    }

    private fun updateUI(text: String) {
        runOnUiThread { statusText.text = "SUPERCLUSTER NODE\n\n$text" }
    }

    override fun onDestroy() {
        super.onDestroy()
        multicastLock?.let { if (it.isHeld) it.release() }
    }
}
