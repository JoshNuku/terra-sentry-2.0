#!/bin/bash
# Start Picamera2 streaming and cloudflared tunnel

# Start Picamera2 RTSP stream (example, adjust as needed)
raspivid -o - -t 0 -n | cvlc -vvv stream:///dev/stdin --sout '#rtp{sdp=rtsp://:8554/}' :demux=h264 &

# Start cloudflared tunnel for the HTTP video stream on port 8080
cloudflared tunnel --url http://localhost:8080 &

# Wait for tunnel to initialize
sleep 5
