using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;
using System.IO;

public class BoilerPlate : MonoBehaviour
{
    private TcpListener tcpListener;
    private Thread tcpListenerThread;
    private TcpClient connectedTcpClient;
    public int port = 5000; // The port to listen on

    void Start()
    {
        // Start the TCP listener thread
        tcpListenerThread = new Thread(new ThreadStart(ListenForIncomingRequests));
        tcpListenerThread.IsBackground = true;
        tcpListenerThread.Start();
    }

    void Update()
    {
        if (connectedTcpClient != null)
        {
            // Check for incoming messages
            NetworkStream stream = connectedTcpClient.GetStream();
            if (stream.DataAvailable)
            {
                byte[] buffer = new byte[1024];
                int bytesRead = stream.Read(buffer, 0, buffer.Length);
                string receivedMessage = Encoding.ASCII.GetString(buffer, 0, bytesRead);

                ArmData armData = JsonUtility.FromJson<ArmData>(receivedMessage); // Modify this if input data changes.

                // Examples of accessing posture value
                // RotateGameObject(armData.shoulder_rotation);
                // UpdateMinMax(armData.shoulder_rotation);
            }
        }
    }

    private void ListenForIncomingRequests()
    {
        try
        {
            tcpListener = new TcpListener(IPAddress.Parse("127.0.0.1"), port);
            tcpListener.Start();

            while (true)
            {
                connectedTcpClient = tcpListener.AcceptTcpClient();
            }
        }
        catch (SocketException socketException)
        {
            Debug.Log("SocketException: " + socketException.ToString());
        }
    }

    private void OnDisable()
    {
        if (tcpListener != null)
        {
            tcpListener.Stop();
        }
        if (tcpListenerThread != null)
        {
            tcpListenerThread.Abort();
        }
    }
}