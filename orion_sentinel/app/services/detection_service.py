import threading
import queue
import time
import base64
import cv2
import numpy as np
from app.core import events, logger, config
from app.sensors import camera as camera_mod
from app.ai import vision
from app.services import alert_service

log = logger.get_logger()

THREAT_CLASSES = ["excavator", "bus", "car", "motorcycle", "truck", "person"]

# Dedicated circular queue for audio events (maxsize=5 to prevent OOM)
audio_event_queue = queue.Queue(maxsize=5)

def vision_worker(get_location, cam):
    while True:
        event = audio_event_queue.get()
        if event is None:
            break
            
        try:
                
            # Prevent staleness: if the event is older than 3 seconds, drop it
            event_time = event.get("timestamp", 0)
            if time.time() - event_time > 3.0:
                log.warning("DetectionWorker: Audio event too stale (>3s). Dropping.")
                continue
                
            location = get_location()
            audio_threat = str(event.get("threatType") or event.get("label") or "suspicious_noise").lower()
            audio_confidence = float(event.get("confidence", 0.8))

            # 2) Wake camera and run AI verification
            try:
                if getattr(cam.picam, "started", None) is False:
                    cam.picam.start()
            except Exception:
                pass

            frame = cam.capture()
            image_b64 = None
            if frame is not None:
                try:
                    ok, jpeg = cv2.imencode('.jpg', frame)
                    if ok:
                        image_b64 = base64.b64encode(jpeg.tobytes()).decode()
                except Exception as e:
                    log.error(f"DetectionWorker: JPEG encoding error: {e}")

            # 1) Mic triggers first alert
            try:
                alert_service.send_alert(
                    sentinel_id=config.DEVICE_ID,
                    threat_type=audio_threat,
                    confidence=audio_confidence,
                    location=location,
                    image_data=image_b64,
                    trigger_type="microphone",
                    triggered_sensors=["mic"]
                )
            except Exception as e:
                log.error(f"DetectionWorker: Failed to send initial mic alert: {e}")
                
            if frame is None:
                log.error("DetectionWorker: Camera frame is None, verification skipped.")
                audio_event_queue.task_done()
                continue

            verify_frames = max(1, int(config.AI_VERIFY_FRAMES))
            min_positive_frames = max(1, int(config.AI_VERIFY_MIN_POSITIVE))
            min_positive_frames = min(min_positive_frames, verify_frames)
            positive_frames = 0
            best_result = {"detected": False, "class": None, "confidence": 0.0, "annotated_frame": frame}

            for idx in range(verify_frames):
                if idx > 0:
                    frame = cam.capture()
                    if frame is None:
                        continue
                result = vision.detect_detailed(frame)
                det_log = [
                    {
                        "class": d["class"],
                        "confidence": round(float(d["confidence"]), 4),
                        "bbox": d["bbox"]
                    }
                    for d in result.get("detections", [])
                ]
                log.info(
                    f"DetectionWorker AI frame {idx + 1}/{verify_frames}: detected={result.get('detected')} top_class={result.get('class')} confidence={result.get('confidence')} boxes={det_log}"
                )
                if result.get("detected"):
                    positive_frames += 1
                    if float(result.get("confidence", 0.0)) > float(best_result.get("confidence", 0.0)):
                        best_result = result

            ai_verified = positive_frames >= min_positive_frames and best_result.get("class") in THREAT_CLASSES

            # 3) If true, send second confirmation alert
            if ai_verified:
                confirm_image_b64 = image_b64
                try:
                    confirm_frame = best_result.get("annotated_frame")
                    if confirm_frame is None and frame is not None:
                        confirm_frame = frame.copy()

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

                    ok, jpeg = cv2.imencode('.jpg', confirm_frame) if confirm_frame is not None else (False, None)
                    if ok:
                        confirm_image_b64 = base64.b64encode(jpeg.tobytes()).decode()
                except Exception as e:
                    log.error(f"DetectionWorker: Confirm image encoding error: {e}")

                if confirm_image_b64 is None:
                    try:
                        fallback = cam.capture()
                        if fallback is not None:
                            ok, jpeg = cv2.imencode('.jpg', fallback)
                            if ok:
                                confirm_image_b64 = base64.b64encode(jpeg.tobytes()).decode()
                    except Exception as e:
                        log.error(f"DetectionWorker: Fallback confirm capture failed: {e}")

                alert_service.send_alert(
                    sentinel_id=config.DEVICE_ID,
                    threat_type=best_result["class"],
                    confidence=best_result["confidence"],
                    location=location,
                    image_data=confirm_image_b64,
                    trigger_type="ai",
                    triggered_sensors=["mic", "camera"]
                )
                log.info(
                    f"DetectionWorker: AI confirmed after {positive_frames}/{verify_frames} positive frames; class={best_result.get('class')} confidence={best_result.get('confidence')}"
                )
            else:
                # 4) If false, close camera and do not send confirmation alert
                try:
                    if cam.picam is not None:
                        cam.picam.stop()
                        log.info(
                            f"DetectionWorker: AI not confirmed ({positive_frames}/{verify_frames} positive frames), camera stopped."
                        )
                except Exception as e:
                    log.error(f"DetectionWorker: Failed to stop camera: {e}")

        except Exception as e:
            log.error(f"DetectionWorker error: {e}")
        finally:
            audio_event_queue.task_done()

def detection_loop(get_location):
    cam = camera_mod.Camera()
    
    # Start the async background vision processor
    worker = threading.Thread(target=vision_worker, args=(get_location, cam), daemon=True)
    worker.start()
    
    while True:
        try:
            event = events.listen()
            if event.get("type") == "AUDIO_TRIGGER":
                event["timestamp"] = time.time()
                log.info(f"DetectionService: Received AUDIO_TRIGGER: {event} - Queuing for Vision AI.")
                
                # Circular Queue Logic: Drop oldest if full
                try:
                    audio_event_queue.put_nowait(event)
                except queue.Full:
                    try:
                        dropped = audio_event_queue.get_nowait()
                        audio_event_queue.task_done()
                        log.warning("DetectionService: Queue full, dropped oldest event.")
                    except queue.Empty:
                        pass
                    try:
                        audio_event_queue.put_nowait(event)
                    except queue.Full:
                        pass
        except Exception as e:
            log.error(f"DetectionService error: {e}")
