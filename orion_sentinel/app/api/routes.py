
# === Imports ===
import base64
import time
import cv2
from fastapi import APIRouter, Request, Body, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
from app.services import stream_service, alert_service
from app.services.alert_service import VALID_TRIGGER_TYPES, VALID_THREAT_TYPES
from app.sensors import camera_singleton
from app.ai import vision
from app.core import logger, config

# === Router ===
router = APIRouter()


def camera_available():
    return camera_singleton.picam2 is not None


def ensure_camera_started():
    camera = camera_singleton.picam2
    if camera is None:
        return False
    try:
        if getattr(camera, "started", None) is False:
            camera.start()
        return True
    except Exception as e:
        logger.get_logger().error(f"Camera start failed: {e}")
        camera_singleton.picam2 = None
        return False


def capture_camera_frame():
    if not ensure_camera_started():
        return None
    try:
        return camera_singleton.picam2.capture_array()
    except Exception as e:
        logger.get_logger().error(f"Camera capture failed: {e}")
        camera_singleton.picam2 = None
        return None

# === Helper Functions ===
def mjpeg_stream():
    target_fps = max(1, int(config.STREAM_TARGET_FPS))
    jpeg_quality = max(40, min(95, int(config.STREAM_JPEG_QUALITY)))
    frame_interval = 1.0 / float(target_fps)
    while True:
        start = time.time()
        frame = capture_camera_frame()
        if frame is None:
            break
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        if not ret:
            continue
        jpg_bytes = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpg_bytes + b'\r\n')
        elapsed = time.time() - start
        if elapsed < frame_interval:
            time.sleep(frame_interval - elapsed)

# === Data Models ===
class ManualMicAlertRequest(BaseModel):
    triggerType: str
    threatType: str
    confidence: float = 0.8
    location: Optional[dict] = None
    triggeredSensors: Optional[list] = None

class StatusResponse(BaseModel):
    mode: str
    camera_active: bool
    ai_loaded: bool
    stream_idle_seconds: int

class ControlResponse(BaseModel):
    mode: str

class StreamResponse(BaseModel):
    streamUrl: str

# === Core Endpoints ===
@router.get("/", response_class=HTMLResponse)
def home_page():
        return """
<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Orion Sentinel - FastAPI Tools</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 24px; background: #f5f7fb; color: #1f2937; }
        .card { max-width: 960px; background: #fff; border: 1px solid #dbe3ef; border-radius: 12px; padding: 18px; }
        h1 { margin-top: 0; font-size: 22px; }
        .row { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
        .field { display: flex; flex-direction: column; gap: 6px; min-width: 180px; }
        label { font-size: 13px; color: #4b5563; }
        input, select { border: 1px solid #cbd5e1; border-radius: 8px; padding: 9px 10px; }
        button { background: #0f766e; color: #fff; border: 0; border-radius: 8px; padding: 10px 14px; cursor: pointer; }
        button:hover { background: #0b5f59; }
        a { color: #0f766e; text-decoration: none; }
        pre { background: #0b1020; color: #e5e7eb; padding: 12px; border-radius: 8px; overflow: auto; min-height: 160px; }
        .muted { color: #6b7280; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Orion Sentinel FastAPI Tools</h1>
        <p class="muted">Use this form to trigger manual microphone alerts from FastAPI and view the response.</p>
        <div class=\"row\">
            <a href="/docs" target="_blank" rel="noopener">Open Swagger Docs</a>
        </div>

        <form id="manualForm">
            <div class="row">
                <div class="field">
                    <label for="threatType">Threat Type</label>
                    <select id="threatType">
                        <option value="chainsaw" selected>chainsaw</option>
                        <option value="speech">speech</option>
                        <option value="excavator">excavator</option>
                        <option value="person">person</option>
                        <option value="car">car</option>
                        <option value="truck">truck</option>
                        <option value="motorcycle">motorcycle</option>
                        <option value="bus">bus</option>
                    </select>
                </div>
                <div class="field" style="min-width:320px; flex: 1;">
                    <label>Defaults</label>
                    <input type="text" value="triggerType=microphone, confidence=0.85, location=Legon, triggeredSensors=[SOUND]" readonly />
                </div>
            </div>
            <div class="row">
                <button id="triggerBtn" type="submit">Send Manual Mic Alert</button>
            </div>
        </form>

        <p class="muted">Request payload:</p>
        <pre id="payloadBox"></pre>
        <p class="muted">API response:</p>
        <pre id="responseBox">Submit the form to call /api/alerts/manual-mic ...</pre>
    </div>

    <script>
        const form = document.getElementById('manualForm');
        const payloadBox = document.getElementById('payloadBox');
        const responseBox = document.getElementById('responseBox');
        const triggerBtn = document.getElementById('triggerBtn');

        function buildPayload() {
            const payload = {
                triggerType: 'microphone',
                threatType: document.getElementById('threatType').value,
                confidence: 0.85,
                location: {
                    lat: 5.6500,
                    lng: -0.1870
                },
                triggeredSensors: ['SOUND']
            };
            payloadBox.textContent = JSON.stringify(payload, null, 2);
            return payload;
        }

        form.addEventListener('input', buildPayload);
        buildPayload();

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = buildPayload();
            triggerBtn.disabled = true;
            triggerBtn.textContent = 'Sending...';
            responseBox.textContent = 'Calling /api/alerts/manual-mic ...';
            try {
                const res = await fetch('/api/alerts/manual-mic', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                let data;
                try {
                    data = await res.json();
                } catch (_) {
                    data = { message: 'Non-JSON response', status: res.status };
                }
                responseBox.textContent = JSON.stringify({ status: res.status, ok: res.ok, data }, null, 2);
            } catch (err) {
                responseBox.textContent = JSON.stringify({ error: String(err) }, null, 2);
            } finally {
                triggerBtn.disabled = false;
                triggerBtn.textContent = 'Send Manual Mic Alert';
            }
        });
    </script>
</body>
</html>
"""


@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/status", response_model=StatusResponse)
def get_status():
    return StatusResponse(
        mode="SENTRY",
        camera_active=camera_available(),
        ai_loaded=True,
        stream_idle_seconds=0
    )

@router.get("/stream")
def video_stream():
    if not camera_available():
        raise HTTPException(status_code=503, detail="Camera not available")
    return StreamingResponse(mjpeg_stream(), media_type='multipart/x-mixed-replace; boundary=frame')

@router.post("/control/activate", response_model=ControlResponse)
def activate():
    return ControlResponse(mode="INTRUDER")

@router.post("/control/deactivate", response_model=ControlResponse)
def deactivate():
    return ControlResponse(mode="SENTRY")

@router.post("/control/request_stream", response_model=StreamResponse)
def request_stream():
    log = logger.get_logger()
    try:
        stream_url = stream_service.get_preferred_stream_url()
        if not stream_url:
            log.error("Failed to resolve stream URL.")
            return StreamResponse(streamUrl="")
        log.info(f"Stream started at {stream_url}")
        return StreamResponse(streamUrl=stream_url)
    except Exception as e:
        log.error(f"request_stream error: {e}")
        return StreamResponse(streamUrl="")

@router.post("/stream/keepalive")
def stream_keepalive():
    return {"ok": True}

@router.post("/control/restart")
@router.post("/api/sentinels/{deviceId}/restart")
def control_restart(deviceId: Optional[str] = None):
    import threading
    import os
    import sys
    import subprocess
    
    def delayed_exit():
        time.sleep(1.0)
        logger.get_logger().info("Restart requested: Cleaning up cloudflared and exiting process now...")
        try:
            if sys.platform.startswith("win"):
                subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)
            else:
                subprocess.run(["pkill", "-f", "cloudflared"], capture_output=True)
        except Exception:
            pass
        os._exit(0)
        
    threading.Thread(target=delayed_exit).start()
    return {"success": True, "message": "Service restart initiated successfully"}

# === Alert Endpoints ===
@router.post("/api/alerts/manual-mic")
def manual_mic_alert(req: ManualMicAlertRequest = Body(...)):
    # Validate against backend-accepted enums
    trigger = (req.triggerType or "").lower()
    threat = (req.threatType or "").lower()
    if trigger not in VALID_TRIGGER_TYPES:
        raise HTTPException(status_code=400, detail=f"triggerType must be one of {VALID_TRIGGER_TYPES}")
    if threat not in VALID_THREAT_TYPES:
        raise HTTPException(status_code=400, detail=f"threatType must be one of {VALID_THREAT_TYPES}")
    location = req.location or {"lat": config.DEFAULT_LAT, "lng": config.DEFAULT_LNG}

    # Capture one frame early so first mic alert can include imageData.
    frame = None
    image_data = None
    try:
        frame = capture_camera_frame()
        if frame is None:
            raise RuntimeError("Camera unavailable")
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            image_data = base64.b64encode(buffer.tobytes()).decode('utf-8')
    except Exception as e:
        logger.get_logger().error(f"Manual mic alert: pre-capture failed: {e}")

    # 1) Send initial microphone alert immediately
    try:
        alert_service.send_alert(
            sentinel_id=config.DEVICE_ID,
            threat_type=threat,
            confidence=req.confidence,
            location=location,
            image_data=image_data,
            trigger_type="microphone",
            triggered_sensors=["mic"]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    stream_url = stream_service.get_preferred_stream_url()

    if frame is None:
        return {
            "success": True,
            "message": "Manual mic alert sent; camera unavailable for AI verification",
            "aiVerified": False,
            "verification": {
                "framesSampled": 0,
                "positiveFrames": 0,
                "minPositiveFrames": 0,
                "class": None,
                "confidence": 0.0,
                "bbox": None
            },
            "streamUrl": stream_url
        }

    # 2) Wake camera and verify with AI
    if frame is None:
        try:
            if ensure_camera_started():
                frame = camera_singleton.picam2.capture_array()
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception:
            pass

    # 2) Verify across multiple frames (video-like window) instead of one frame.
    verify_frames = max(1, int(config.AI_VERIFY_FRAMES))
    min_positive_frames = max(1, int(config.AI_VERIFY_MIN_POSITIVE))
    min_positive_frames = min(min_positive_frames, verify_frames)
    positive_frames = 0
    best_result = {"detected": False, "class": None, "confidence": 0.0, "annotated_frame": frame}

    for idx in range(verify_frames):
        if idx > 0:
            frame = capture_camera_frame()
            if frame is None:
                logger.get_logger().warning("Manual mic alert: camera became unavailable during verification.")
                break
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        result = vision.detect_detailed(frame)
        detections = result.get("detections", [])
        det_log = [
            {
                "class": d["class"],
                "confidence": round(float(d["confidence"]), 4),
                "bbox": d["bbox"]
            }
            for d in detections
        ]
        logger.get_logger().info(
            f"Manual mic AI frame {idx + 1}/{verify_frames}: detected={result.get('detected')} top_class={result.get('class')} confidence={result.get('confidence')} raw_top_class={result.get('raw_top_class')} raw_top_conf={result.get('raw_top_confidence')} raw_above_conf={result.get('raw_above_conf_count')} boxes={det_log}"
        )

        if result.get("detected"):
            positive_frames += 1
            if float(result.get("confidence", 0.0)) > float(best_result.get("confidence", 0.0)):
                best_result = result

        time.sleep(0.08)

    # 3) If AI confirms threat, send a second confirmation alert
    ai_verified = positive_frames >= min_positive_frames and best_result.get("class") in VALID_THREAT_TYPES
    if ai_verified:
        confirm_frame = None
        try:
            confirm_frame = best_result.get("annotated_frame")
            if confirm_frame is None and frame is not None:
                confirm_frame = frame.copy()

            # Ensure bbox overlay exists on confirmation capture.
            bbox = best_result.get("bbox")
            if confirm_frame is not None and bbox:
                x1, y1, x2, y2 = [int(v) for v in bbox]
                label = best_result.get("class") or "threat"
                conf = float(best_result.get("confidence", 0.0))
                cv2.rectangle(confirm_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    confirm_frame,
                    f"{label} {conf:.2f}",
                    (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

            ret, buffer = cv2.imencode('.jpg', confirm_frame) if confirm_frame is not None else (False, None)
            image_data = base64.b64encode(buffer.tobytes()).decode('utf-8') if ret else None
        except Exception as e:
            image_data = None
            logger.get_logger().error(f"Manual mic alert: image encode failed: {e}")

        if image_data is None:
            # Fallback: capture a fresh frame and attach it rather than sending no image.
            try:
                fallback = capture_camera_frame()
                if fallback is not None:
                    fallback = cv2.cvtColor(fallback, cv2.COLOR_RGB2BGR)
                else:
                    raise RuntimeError("Camera unavailable")
                ret, buffer = cv2.imencode('.jpg', fallback)
                if ret:
                    image_data = base64.b64encode(buffer.tobytes()).decode('utf-8')
            except Exception as e:
                logger.get_logger().error(f"Manual mic alert: fallback capture failed: {e}")

        try:
            alert_service.send_alert(
                sentinel_id=config.DEVICE_ID,
                threat_type=best_result.get("class"),
                confidence=float(best_result.get("confidence", req.confidence)),
                location=location,
                image_data=image_data,
                trigger_type="ai",
                triggered_sensors=["mic", "camera"]
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        return {
            "success": True,
            "message": "Manual mic alert sent and AI confirmed",
            "aiVerified": True,
            "verification": {
                "framesSampled": verify_frames,
                "positiveFrames": positive_frames,
                "minPositiveFrames": min_positive_frames,
                "class": best_result.get("class"),
                "confidence": best_result.get("confidence"),
                "bbox": best_result.get("bbox")
            },
            "streamUrl": stream_url
        }

    # 4) If not confirmed, close camera and do not send second alert
    try:
        if camera_singleton.picam2 is not None:
            camera_singleton.picam2.stop()
    except Exception as e:
        logger.get_logger().error(f"Manual mic alert: failed to stop camera after false verification: {e}")

    return {
        "success": True,
        "message": "Manual mic alert sent; AI did not confirm",
        "aiVerified": False,
        "verification": {
            "framesSampled": verify_frames,
            "positiveFrames": positive_frames,
            "minPositiveFrames": min_positive_frames,
            "class": best_result.get("class"),
            "confidence": best_result.get("confidence"),
            "bbox": best_result.get("bbox")
        },
        "streamUrl": stream_url
    }

# === Dashboard/Backend-Aligned Endpoints ===
@router.post("/api/sentinels/{deviceId}/stream/start")
def dashboard_stream_start(deviceId: str, request: Request):
    log = logger.get_logger()
    try:
        stream_url = stream_service.get_preferred_stream_url()
        if not stream_url:
            log.error("Failed to resolve stream URL (dashboard request).")
            return {"success": False, "streamUrl": ""}
        from app.services import heartbeat_service
        location = {"lat": config.DEFAULT_LAT, "lng": config.DEFAULT_LNG}
        battery_level = heartbeat_service.get_battery_level() if hasattr(heartbeat_service, "get_battery_level") else 100
        import socket
        try:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
        except Exception:
            ip_address = "127.0.0.1"
        stream_service.register_stream(
            stream_url=stream_url,
            location=location,
            battery_level=battery_level,
            ip_address=ip_address,
            trigger_type="dashboard"
        )
        log.info(f"[Dashboard] Stream started and registered at {stream_url}")
        return {"success": True, "streamUrl": stream_url}
    except Exception as e:
        log.error(f"dashboard_stream_start error: {e}")
        return {"success": False, "streamUrl": ""}

@router.post("/api/sentinels/{deviceId}/stream/stop")
def dashboard_stream_stop(deviceId: str, request: Request):
    log = logger.get_logger()
    try:
        import subprocess
        import psutil
        stopped = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'cloudflared' in proc.info['name']:
                    proc.terminate()
                    stopped = True
            except Exception:
                continue
        log.info(f"[Dashboard] Stream stop requested for {deviceId}. Cloudflared stopped: {stopped}")
        return {"success": True, "cloudflaredStopped": stopped}
    except Exception as e:
        log.error(f"dashboard_stream_stop error: {e}")
        return {"success": False, "error": str(e)}

import threading
_last_keepalive = {}

@router.post("/api/sentinels/{deviceId}/keepalive")
def dashboard_keepalive(deviceId: str, request: Request):
    log = logger.get_logger()
    _last_keepalive[deviceId] = time.time()
    log.info(f"[Dashboard] Keepalive received for {deviceId} at {_last_keepalive[deviceId]}")
    return {"success": True, "lastKeepalive": _last_keepalive[deviceId]}

@router.get("/api/sentinels/{deviceId}/pi-status")
def dashboard_pi_status(deviceId: str):
    return get_status()


@router.post("/control/verify_vision")
def verify_vision():
    log = logger.get_logger()
    log.info("[VISION] Manual vision AI verification requested by operator.")
    
    # 1) Capture frame
    frame = capture_camera_frame()
    if frame is None:
        log.error("[VISION] Failed to capture camera frame for manual verification.")
        return {
            "success": False,
            "detected": False,
            "message": "Camera is currently busy or unavailable. Please try again."
        }
        
    try:
        # Convert RGB to BGR for OpenCV / YOLO
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # 2) Run object detection
        result = vision.detect_detailed(frame)
        detected = result.get("detected", False)
        threat_class = result.get("class")
        confidence = float(result.get("confidence", 0.0))
        
        if detected and threat_class in VALID_THREAT_TYPES:
            log.info(f"[VISION] AI detected threat: {threat_class} ({confidence:.2f})")
            
            # Annotate bbox and label
            annotated_frame = result.get("annotated_frame")
            if annotated_frame is None:
                annotated_frame = frame.copy()
                
            bbox = result.get("bbox")
            if bbox:
                x1, y1, x2, y2 = [int(v) for v in bbox]
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    annotated_frame,
                    f"{threat_class} {confidence:.2f}",
                    (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )
                
            # Encode frame to base64 JPEG
            ret, buffer = cv2.imencode('.jpg', annotated_frame)
            image_data = base64.b64encode(buffer.tobytes()).decode('utf-8') if ret else None
            
            # Send alert to backend — propagate failure so operator knows if it was actually saved
            location = {"lat": config.DEFAULT_LAT, "lng": config.DEFAULT_LNG}
            try:
                alert_service.send_alert(
                    sentinel_id=config.DEVICE_ID,
                    threat_type=threat_class,
                    confidence=confidence,
                    location=location,
                    image_data=image_data,
                    trigger_type="ai",
                    triggered_sensors=["camera"]
                )
            except Exception as alert_err:
                log.error(f"[VISION] Threat detected but alert dispatch failed: {alert_err}")
                return {
                    "success": True,
                    "detected": True,
                    "class": threat_class,
                    "confidence": confidence,
                    "message": f"AI detected {threat_class} ({int(confidence * 100)}% confidence) but alert could not be sent to backend. Check connectivity."
                }
            
            return {
                "success": True,
                "detected": True,
                "class": threat_class,
                "confidence": confidence,
                "message": f"AI verified threat: {threat_class} ({int(confidence * 100)}% confidence). Alert generated!"
            }
        else:
            log.info("[VISION] AI verification complete. No threats detected in the frame.")
            return {
                "success": True,
                "detected": False,
                "message": "AI analysis complete: No threats detected in the frame. System state clear."
            }
            
    except Exception as e:
        log.error(f"[VISION] Manual AI verification failed: {e}")
        return {
            "success": False,
            "detected": False,
            "message": f"AI analysis failed: {str(e)}"
        }


