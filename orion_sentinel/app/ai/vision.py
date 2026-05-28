
import numpy as np
import tflite_runtime.interpreter as tflite
import cv2
import onnxruntime as ort
from app.core import config, logger

log = logger.get_logger()


import os
COCO_CLASSES_PATH = config.COCO_CLASSES_PATH
with open(COCO_CLASSES_PATH, "r") as f:
    COCO_CLASSES = [line.strip() for line in f.readlines() if line.strip()]
ALLOWED_CLASSES = config.ALLOWED_CLASSES
MODEL_PATH = config.YOLO_TFLITE_PATH
INPUT_SIZE = config.YOLO_INPUT_SIZE
CONF_THRESHOLD = float(os.getenv("YOLO_CONF_THRESHOLD", "0.25"))
NMS_THRESHOLD = float(os.getenv("YOLO_NMS_THRESHOLD", "0.45"))

_interpreter = None
_input_details = None
_output_details = None
_input_width = None
_input_height = None
_ort_session = None
_model_type = None  # "onnx" or "tflite"

def _load_model():
    global _interpreter, _input_details, _output_details, _input_width, _input_height, _ort_session, _model_type
    if _model_type is not None:
        return

    ext = os.path.splitext(MODEL_PATH)[1].lower()
    if ext == ".onnx":
        log.info(f"[VISION] Loading ONNX model from {MODEL_PATH} via ONNX Runtime...")
        _ort_session = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
        _model_type = "onnx"
        _input_height = INPUT_SIZE
        _input_width = INPUT_SIZE
    else:
        log.info(f"[VISION] Loading TFLite model from {MODEL_PATH} via tflite_runtime...")
        _interpreter = tflite.Interpreter(model_path=MODEL_PATH, num_threads=2)
        _interpreter.allocate_tensors()
        _input_details = _interpreter.get_input_details()
        _output_details = _interpreter.get_output_details()
        shape = _input_details[0]["shape"]
        _input_height = int(shape[1])
        _input_width = int(shape[2])
        _model_type = "tflite"

def detect(frame):
    result = detect_detailed(frame)
    return {
        "detected": result["detected"],
        "class": result["class"],
        "confidence": result["confidence"]
    }


def detect_detailed(frame):
    try:
        _load_model()
        input_w = _input_width or INPUT_SIZE
        input_h = _input_height or INPUT_SIZE

        if frame is not None and frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        if _model_type == "onnx":
            # ONNX inference using ONNX Runtime
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (input_w, input_h), swapRB=True, crop=False)
            input_name = _ort_session.get_inputs()[0].name
            outputs = _ort_session.run(None, {input_name: blob})
            detections = outputs[0][0]
        else:
            # TFLite inference
            frame_resized = cv2.resize(frame, (input_w, input_h))
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            input_data = frame_rgb.astype(np.float32) / 255.0
            input_data = np.expand_dims(input_data, axis=0)
            scale, zero_point = _input_details[0]['quantization']
            if scale > 0:
                input_data = (input_data / scale + zero_point).astype(np.uint8)
            _interpreter.set_tensor(_input_details[0]['index'], input_data)
            _interpreter.invoke()
            output = _interpreter.get_tensor(_output_details[0]['index'])
            detections = output[0]
        boxes = detections[:, :4]
        objectness = detections[:, 4]
        class_scores = detections[:, 5:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = objectness * class_scores[np.arange(len(class_scores)), class_ids]

        # Keep a raw top prediction for diagnostics before confidence/class filtering.
        raw_top_idx = int(np.argmax(confidences)) if len(confidences) > 0 else -1
        raw_top_conf = float(confidences[raw_top_idx]) if raw_top_idx >= 0 else 0.0
        raw_top_class = COCO_CLASSES[int(class_ids[raw_top_idx])] if raw_top_idx >= 0 else None

        mask = confidences > CONF_THRESHOLD
        boxes = boxes[mask]
        class_ids = class_ids[mask]
        confidences = confidences[mask]
        # Convert boxes from [x, y, w, h] to [x1, y1, x2, y2]
        if len(boxes) == 0:
            return {
                "detected": False,
                "class": None,
                "confidence": 0.0,
                "bbox": None,
                "detections": [],
                "raw_top_class": raw_top_class,
                "raw_top_confidence": raw_top_conf,
                "raw_above_conf_count": 0,
                "annotated_frame": frame
            }
        boxes_xyxy = []
        for box in boxes:
            x, y, w, h = box
            x1 = int((x - w / 2) * input_w)
            y1 = int((y - h / 2) * input_h)
            x2 = int((x + w / 2) * input_w)
            y2 = int((y + h / 2) * input_h)
            boxes_xyxy.append([x1, y1, x2, y2])
        indices = cv2.dnn.NMSBoxes(boxes_xyxy, confidences.tolist(), CONF_THRESHOLD, NMS_THRESHOLD)
        if len(indices) == 0:
            return {
                "detected": False,
                "class": None,
                "confidence": 0.0,
                "bbox": None,
                "detections": [],
                "raw_top_class": raw_top_class,
                "raw_top_confidence": raw_top_conf,
                "raw_above_conf_count": 0,
                "annotated_frame": frame
            }

        detections = []
        annotated = frame.copy()

        # Keep allowed detections and draw bounding boxes for debugging
        for i in indices.flatten():
            class_id = int(class_ids[i])
            label = COCO_CLASSES[class_id]
            if label in ALLOWED_CLASSES:
                x1, y1, x2, y2 = boxes_xyxy[i]
                conf = float(confidences[i])
                detections.append({
                    "class": label,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2]
                })
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    annotated,
                    f"{label} {conf:.2f}",
                    (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

        if not detections:
            return {
                "detected": False,
                "class": None,
                "confidence": 0.0,
                "bbox": None,
                "detections": [],
                "raw_top_class": raw_top_class,
                "raw_top_confidence": raw_top_conf,
                "raw_above_conf_count": int(len(class_ids)),
                "annotated_frame": frame
            }

        best = max(detections, key=lambda d: d["confidence"])
        return {
            "detected": True,
            "class": best["class"],
            "confidence": best["confidence"],
            "bbox": best["bbox"],
            "detections": detections,
            "raw_top_class": raw_top_class,
            "raw_top_confidence": raw_top_conf,
            "raw_above_conf_count": int(len(class_ids)),
            "annotated_frame": annotated
        }
    except Exception as e:
        log.error(f"YOLOv5n inference error: {e}")
        return {
            "detected": False,
            "class": None,
            "confidence": 0.0,
            "bbox": None,
            "detections": [],
            "raw_top_class": None,
            "raw_top_confidence": 0.0,
            "raw_above_conf_count": 0,
            "annotated_frame": frame
        }
