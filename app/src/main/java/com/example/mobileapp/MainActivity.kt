package com.example.mobileapp

import android.os.Bundle
import java.util.UUID
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.eclipse.paho.android.service.MqttAndroidClient
import org.eclipse.paho.client.mqttv3.IMqttActionListener
import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken
import org.eclipse.paho.client.mqttv3.IMqttToken
import org.eclipse.paho.client.mqttv3.MqttCallback
import org.eclipse.paho.client.mqttv3.MqttClient
import org.eclipse.paho.client.mqttv3.MqttConnectOptions
import org.eclipse.paho.client.mqttv3.MqttException
import org.eclipse.paho.client.mqttv3.MqttMessage

class MainActivity : AppCompatActivity() {

    private lateinit var mqttClient: MqttAndroidClient
    private lateinit var textViewCount: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        textViewCount = findViewById(R.id.textViewCount)

        val serverUri = "tcp://BROKER_IP:1883"
        val clientId = "AndroidClient_" + UUID.randomUUID().toString()

        mqttClient = MqttAndroidClient(applicationContext, serverUri, clientId)

        val options = MqttConnectOptions()

        mqttClient.setCallback(object : MqttCallback {
            override fun messageArrived(topic: String?, message: MqttMessage?) {
                val payload = message.toString()
                runOnUiThread {
                    textViewCount.text = "Visitors: $payload"
                }
            }
            override fun connectionLost(cause: Throwable?) { }
            override fun deliveryComplete(token: IMqttDeliveryToken?) { }
        })

        mqttClient.connect(options, null, object : IMqttActionListener {
            override fun onSuccess(asyncActionToken: IMqttToken?) {
                mqttClient.subscribe("visitor/count", 0)
            }
            override fun onFailure(asyncActionToken: IMqttToken?, exception: Throwable?) {
                // virheenkäsittely
            }
        })
    }
}
