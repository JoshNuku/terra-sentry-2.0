#!/bin/bash
# Start Picamera2 streaming and ngrok tunnel

# Start Picamera2 RTSP stream (example, adjust as needed)
# raspivid -o - -t 0 -n | cvlc -vvv stream:///dev/stdin --sout '#rtp{sdp=rtsp://:8554/}' :demux=h264 &

# Start ngrok TCP tunnel for RTSP
ngrok tcp 8554 &

# Wait for ngrok to initialize
sleep 5

# Print ngrok public URL
curl -s http://localhost:4040/api/tunnels | grep -o 'tcp://[^"]*'
