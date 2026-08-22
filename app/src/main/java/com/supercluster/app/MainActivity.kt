package com.supercluster.app

import android.content.Context
import android.net.wifi.WifiManager
import android.os.Bundle
import android.util.Log
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.net.*
import java.util.concurrent.Executors
import android.app.ActivityManager

class MainActivity : AppCompatActivity() {
    private val TAG = "SuperClusterNode"
    private val DISCOVERY_PORT = 9999
    private val TCP_PORT = 8080
    private val MULTICAST_IP = "239.255.255.250"
    
    private var multicastLock: WifiManager.MulticastLock? = null
    private val executor = Executors.newFixedThreadPool(10)
    private lateinit var statusText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        statusText = findViewById(R.id.textView)
        
        statusText.text = "Node Running Local AI\nIP: ${getIPAddress()}"

        try {
            val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            multicastLock = wifi.createMulticastLock("SuperClusterLock")
            multicastLock?.setReferenceCounted(true)
            multicastLock?.acquire()
        } catch (e: Exception) {
            Log.e(TAG, "Multicast Lock Error: ${e.message}")
        }

        startDiscoveryListener()
        startTcpServer()
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
        } catch (e: Exception) {
            e.printStackTrace()
        }
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
            while (true) {
                val buffer = ByteArray(1024)
                val packet = DatagramPacket(buffer, buffer.size)
                socket.receive(packet)
                handleDiscoveryPacket(socket, packet)
            }
        } catch (e: Exception) { Log.e(TAG, "Multicast Err: ${e.message}") }
    }

    private fun runBroadcastListener() {
        try {
            val socket = DatagramSocket(DISCOVERY_PORT)
            socket.broadcast = true
            while (true) {
                val buffer = ByteArray(1024)
                val packet = DatagramPacket(buffer, buffer.size)
                socket.receive(packet)
                handleDiscoveryPacket(socket, packet)
            }
        } catch (e: Exception) { Log.e(TAG, "Broadcast Err: ${e.message}") }
    }

    private fun handleDiscoveryPacket(socket: DatagramSocket, packet: DatagramPacket) {
        val message = String(packet.data, 0, packet.length).trim()
        if (message == "SUPERCLUSTER_DISCOVERY") {
            val response = "SUPERCLUSTER_ACK".toByteArray()
            socket.send(DatagramPacket(response, response.size, packet.address, packet.port))
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
            } catch (e: Exception) { Log.e(TAG, "TCP Err: ${e.message}") }
        }
    }

    private fun handleClient(socket: Socket) {
        executor.execute {
            try {
                val reader = socket.getInputStream().bufferedReader()
                val writer = socket.getOutputStream().bufferedWriter()
                val requestStr = reader.readLine() ?: return@execute
                
                val requestJson = JSONObject(requestStr)
                val command = requestJson.optString("command")
                val response = JSONObject()

                when (command) {
                    "GET_STATS" -> {
                        response.put("ram", getTotalRam())
                        response.put("load", (1..20).random())
                    }
                    "PROMPT" -> {
                        val prompt = requestJson.optString("data")
                        // Simulation d'une réponse IA locale
                        val aiResponse = "LOCAL NODE RESPONSE [${getIPAddress()}]:\n" +
                                "I have processed your prompt: '$prompt'.\n" +
                                "The local inference engine is active and distributed across the cluster.\n" +
                                "Using ${getTotalRam() / 1024 / 1024} MB of local memory."
                        response.put("response", aiResponse)
                    }
                }
                writer.write(response.toString() + "\n")
                writer.flush()
            } catch (e: Exception) { Log.e(TAG, "Handle Err: ${e.message}") }
            finally { try { socket.close() } catch (e: Exception) {} }
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
    }
}
