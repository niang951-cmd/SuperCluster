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
    private val executor = Executors.newFixedThreadPool(4)
    private lateinit var statusText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        statusText = findViewById(R.id.textView)
        
        statusText.text = "Node Active\nIP: ${getIPAddress()}"

        // Multicast lock is required to receive multicast packets on many devices
        try {
            val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            multicastLock = wifi.createMulticastLock("SuperClusterLock")
            multicastLock?.setReferenceCounted(true)
            multicastLock?.acquire()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to acquire multicast lock: ${e.message}")
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
        // Run both Multicast and Broadcast listeners for robustness
        executor.execute { runMulticastListener() }
        executor.execute { runBroadcastListener() }
    }

    private fun runMulticastListener() {
        try {
            val group = InetAddress.getByName(MULTICAST_IP)
            val socket = MulticastSocket(DISCOVERY_PORT)
            socket.joinGroup(group)
            
            val buffer = ByteArray(1024)
            Log.d(TAG, "Multicast Listener started on $MULTICAST_IP:$DISCOVERY_PORT")

            while (true) {
                val packet = DatagramPacket(buffer, buffer.size)
                socket.receive(packet)
                handleDiscoveryPacket(socket, packet)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Multicast error: ${e.message}")
        }
    }

    private fun runBroadcastListener() {
        try {
            val socket = DatagramSocket(DISCOVERY_PORT)
            socket.broadcast = true
            val buffer = ByteArray(1024)
            Log.d(TAG, "Broadcast Listener started on port $DISCOVERY_PORT")

            while (true) {
                val packet = DatagramPacket(buffer, buffer.size)
                socket.receive(packet)
                handleDiscoveryPacket(socket, packet)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Broadcast error: ${e.message}")
        }
    }

    private fun handleDiscoveryPacket(socket: DatagramSocket, packet: DatagramPacket) {
        val message = String(packet.data, 0, packet.length).trim()
        Log.d(TAG, "Received Discovery: $message from ${packet.address.hostAddress}")

        if (message == "SUPERCLUSTER_DISCOVERY") {
            val response = "SUPERCLUSTER_ACK".toByteArray()
            val replyPacket = DatagramPacket(response, response.size, packet.address, packet.port)
            socket.send(replyPacket)
            Log.d(TAG, "Sent ACK to ${packet.address.hostAddress}")
        }
    }

    private fun startTcpServer() {
        executor.execute {
            try {
                val serverSocket = ServerSocket(TCP_PORT)
                Log.d(TAG, "TCP Server started on port $TCP_PORT")

                while (true) {
                    val clientSocket = serverSocket.accept()
                    clientSocket.soTimeout = 5000 // Security timeout
                    handleClient(clientSocket)
                }
            } catch (e: Exception) {
                Log.e(TAG, "TCP Server error: ${e.message}")
            }
        }
    }

    private fun handleClient(socket: Socket) {
        executor.execute {
            try {
                val reader = socket.getInputStream().bufferedReader()
                val writer = socket.getOutputStream().bufferedWriter()
                
                // Read using a simpler way that doesn't strictly require \n if the sender closes
                val requestStr = reader.readLine() ?: return@execute
                Log.d(TAG, "TCP Request: $requestStr")
                
                val requestJson = JSONObject(requestStr)
                val command = requestJson.optString("command")
                
                val response = JSONObject()
                when (command) {
                    "GET_STATS" -> {
                        response.put("ram", getTotalRam())
                        response.put("load", getCpuLoad())
                    }
                    "PROMPT" -> {
                        val data = requestJson.optString("data")
                        response.put("response", "Node [${getIPAddress()}] processed: $data")
                    }
                    else -> response.put("error", "Unknown command")
                }
                
                writer.write(response.toString() + "\n")
                writer.flush()
            } catch (e: Exception) {
                Log.e(TAG, "Client error: ${e.message}")
            } finally {
                try { socket.close() } catch (e: Exception) {}
            }
        }
    }

    private fun getTotalRam(): Long {
        val actManager = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val memInfo = ActivityManager.MemoryInfo()
        actManager.getMemoryInfo(memInfo)
        return memInfo.totalMem
    }

    private fun getCpuLoad(): Int {
        return (1..15).random()
    }

    override fun onDestroy() {
        super.onDestroy()
        multicastLock?.let {
            if (it.isHeld) it.release()
        }
    }
}
