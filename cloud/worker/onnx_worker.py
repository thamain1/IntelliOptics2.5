#IntelliOptics
#!/usr/bin/env python3
"""
ONNX inference worker for IntelliOptics (AKS + Azure Service Bus)

- Robust SB message parsing (handles JSON bytes/str, generator bodies, or app props)
- Fetches images over HTTP(S) with Azure Blob fallback (shared key or SAS)
- Supports YOLO-style heads:
    * (1, N, 4+nc) or (1, 4+nc, N) -> cls scores per class (no objness)
    * (1, N, 6) -> [x1,y1,x2,y2,score,class]
- Letterbox preproc, NMS postproc, optional “binary” class gating (e.g. person only)
- Health endpoint on :8081/health
"""
from __future__ import annotations

import io
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import numpy as np
import requests
import onnxruntime as ort  # runtime must be in the image or injected before start
import cv2

try:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage
    from azure.storage.blob import BlobClient
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False

# -----------------------------
# Logging
# -----------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("io-onnx-worker")

# -----------------------------
# Env / Config
# -----------------------------
SB_CONN   = os.getenv("SERVICE_BUS_CONN") or os.getenv("SB_CONN")
QUEUE_IN  = os.getenv("QUEUE_IN", "image-queries")
QUEUE_OUT = os.getenv("QUEUE_OUT", "inference-results")

MODEL_URI  = os.getenv("MODEL_URI") or os.getenv("MODEL_URL") or os.getenv("MODEL_URL_FALLBACK")
MODEL_DIR  = os.getenv("MODEL_CACHE_DIR", "/app/models")
MODEL_NAME = os.getenv("MODEL_NAME", (os.path.basename((MODEL_URI or "model.onnx").split("?")[0]) or "model.onnx"))

AZ_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")  # full connection string (shared key)
AZ_ACCOUNT  = os.getenv("AZ_BLOB_ACCOUNT")  # optional (only for logs)

# Inference tuning
IO_MODE        = os.getenv("IO_MODE", "onnx").lower()     # "onnx" or "binary" (binary gates on one class)
IO_IMG_SIZE    = int(os.getenv("IO_IMG_SIZE", "640"))
IO_CONF_THRESH = float(os.getenv("IO_CONF_THRESH", "0.50"))
IO_NMS_IOU     = float(os.getenv("IO_NMS_IOU", "0.45"))
BINARY_CLASS   = os.getenv("IO_BINARY_CLASS", "person").lower()  # only used when IO_MODE=="binary"

# Health
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8081"))

# COCO80 labels (index 0 == "person")
COCO = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck","boat","traffic light",
    "fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse","sheep","cow",
    "elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee",
    "skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard","surfboard",
    "tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple",
    "sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch",
    "potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone",
    "microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear",
    "hair drier","toothbrush"
]

os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_NAME)

# -----------------------------
# Health server + Inference HTTP endpoint
# -----------------------------
# Global session variable for HTTP endpoint
_INFERENCE_SESSION = None

def _start_health_server(port: int = HEALTH_PORT) -> None:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args, **_kwargs):  # silence default access logs
            return

        def do_GET(self):  # noqa: N802
            if self.path.rstrip("/") == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):  # noqa: N802
            """Handle POST /infer requests for detector-aware inference"""
            if self.path.rstrip("/") == "/infer":
                try:
                    from detector_inference import run_detector_inference
                    from email import message_from_string
                    from io import BytesIO

                    # Parse multipart form data
                    content_type = self.headers.get('Content-Type', '')

                    if 'multipart/form-data' in content_type:
                        # Extract boundary
                        boundary = content_type.split('boundary=')[1]
                        content_length = int(self.headers.get('Content-Length', 0))
                        body = self.rfile.read(content_length)

                        # Parse multipart data manually
                        parts = body.split(('--' + boundary).encode())

                        image_bytes = None
                        detector_config = None

                        for part in parts:
                            if b'Content-Disposition' in part and b'name="image"' in part:
                                # Extract image data
                                image_start = part.find(b'\r\n\r\n') + 4
                                image_end = part.rfind(b'\r\n')
                                image_bytes = part[image_start:image_end]

                            elif b'Content-Disposition' in part and b'name="config"' in part:
                                # Extract config JSON
                                config_start = part.find(b'\r\n\r\n') + 4
                                config_end = part.rfind(b'\r\n')
                                config_json = part[config_start:config_end].decode('utf-8')
                                detector_config = json.loads(config_json)

                        if not image_bytes or not detector_config:
                            self.send_response(400)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(json.dumps({"error": "Missing image or config"}).encode())
                            return

                        # Run detector-aware inference
                        result = run_detector_inference(
                            detector_id=detector_config["detector_id"],
                            detector_config=detector_config,
                            image_bytes=image_bytes
                        )

                        # Return result
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())

                        log.info("Detector-aware inference completed: detector=%s detections=%d latency_ms=%d",
                                detector_config["detector_id"], len(result.get("detections", [])), result.get("latency_ms", 0))

                    else:
                        # Fallback: raw image bytes (legacy)
                        content_length = int(self.headers.get('Content-Length', 0))
                        image_bytes = self.rfile.read(content_length)

                        if not image_bytes:
                            self.send_response(400)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(json.dumps({"error": "No image data"}).encode())
                            return

                        # Run legacy inference with global model
                        start_ts = time.perf_counter()
                        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
                        if img is None:
                            self.send_response(400)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(json.dumps({"error": "Failed to decode image"}).encode())
                            return

                        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                        global _INFERENCE_SESSION
                        if _INFERENCE_SESSION is None:
                            self.send_response(503)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(json.dumps({"error": "Model not loaded"}).encode())
                            return

                        result = _infer(_INFERENCE_SESSION, rgb)
                        latency_ms = int((time.perf_counter() - start_ts) * 1000.0)
                        result["latency_ms"] = latency_ms

                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())

                        log.info("Legacy inference completed: detections=%d latency_ms=%d",
                                len(result.get("detections", [])), latency_ms)

                except Exception as e:
                    log.exception("HTTP inference failed: %s", e)
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
            else:
                self.send_response(404)
                self.end_headers()

    def _serve():
        httpd = HTTPServer(("0.0.0.0", port), HealthHandler)
        log.info("Health+Inference server http://0.0.0.0:%d/health http://0.0.0.0:%d/infer", port, port)
        while True:
            httpd.handle_request()

    t = threading.Thread(target=_serve, name="healthz", daemon=True)
    t.start()

# -----------------------------
# Helpers
# -----------------------------
def _redact_sas(url: str) -> str:
    try:
        if "sig=" in url:
            before, _sig = url.split("sig=", 1)
            return before + "sig=REDACTED"
    except Exception:
        pass
    return url

def _split_container_blob_from_url(blob_url: str) -> Tuple[str, str]:
    """
    Given: https://<acct>.blob.core.windows.net/<container>/<path/to/blob>
    Returns: (container, blob_path)
    """
    u = urlparse(blob_url)
    parts = [p for p in u.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot parse container/blob from URL: {blob_url}")
    container = parts[0]
    blob_path = "/".join(parts[1:])
    return container, blob_path

def _fetch_bytes(url: str) -> bytes:
    # Direct HTTP first
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as http_err:
        log.warning("HTTP fetch failed (%s): %s", _redact_sas(url), http_err)

    # Blob fallback
    try:
        if "?" in url:
            # SAS present
            bc = BlobClient.from_blob_url(url)
        elif AZ_CONN_STR:
            container, blob = _split_container_blob_from_url(url)
            bc = BlobClient.from_connection_string(AZ_CONN_STR, container_name=container, blob_name=blob)
        else:
            raise RuntimeError("No credentials for BlobClient fallback")
        return bc.download_blob().readall()
    except Exception as blob_err:
        raise RuntimeError(f"Blob download failed: {blob_err}") from blob_err

def _download_model() -> str:
    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 0:
        log.info("Model present: %s", MODEL_PATH)
        return MODEL_PATH
    if not MODEL_URI:
        raise RuntimeError("MODEL_URI is required")
    log.info("Fetching model: %s", _redact_sas(MODEL_URI))
    data = _fetch_bytes(MODEL_URI)
    with open(MODEL_PATH, "wb") as f:
        f.write(data)
    log.info("Model saved: %s (%d bytes)", MODEL_PATH, len(data))
    return MODEL_PATH

# -----------------------------
# Pre/Post processing
# -----------------------------
def _letterbox(im: np.ndarray, new: int, color=(114, 114, 114)) -> Tuple[np.ndarray, float, Tuple[int, int]]:
    h, w = im.shape[:2]
    r = min(new / h, new / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    imr = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_LINEAR)
    top  = (new - nh) // 2
    left = (new - nw) // 2
    canvas = np.full((new, new, 3), color, dtype=np.uint8)
    canvas[top:top+nh, left:left+nw] = imr
    return canvas, r, (left, top)

def _xywh2xyxy(xywh: np.ndarray) -> np.ndarray:
    x, y, w, h = xywh.T
    return np.stack([x - w/2, y - h/2, x + w/2, y + h/2], axis=1)

def _nms(boxes: np.ndarray, scores: np.ndarray, iou: float) -> List[int]:
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: List[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        inds = np.where(ovr <= iou)[0]
        order = order[inds + 1]
    return keep

def _clip(dets: List[Dict[str, Any]], W: int, H: int) -> List[Dict[str, Any]]:
    out = []
    for d in dets:
        x1 = max(0.0, min(float(d["x1"]), W - 1))
        y1 = max(0.0, min(float(d["y1"]), H - 1))
        x2 = max(0.0, min(float(d["x2"]), W - 1))
        y2 = max(0.0, min(float(d["y2"]), H - 1))
        if x2 > x1 and y2 > y1:
            dd = dict(d)
            dd.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2})
            out.append(dd)
    return out

def _postprocess(pred: np.ndarray, ratio: float, pad: Tuple[int, int], img_wh: Tuple[int, int]) -> List[Dict[str, Any]]:
    """
    Accepts:
      * (1, N, 4+nc)  OR  (1, 4+nc, N)  -> YOLOv8/10 style with per-class scores
      * (1, N, 6)     -> [x1,y1,x2,y2,score,cls]
    Returns detection dicts with xyxy in ORIGINAL image coordinates.
    """
    W, H = img_wh
    if pred.ndim != 3:
        raise RuntimeError(f"Unexpected ONNX output shape: {pred.shape}")

    # Case A: YOLO head (4+nc)
    if pred.shape[1] == 4 + len(COCO) or pred.shape[2] == 4 + len(COCO):
        if pred.shape[1] == 4 + len(COCO):  # (1, 4+nc, N) -> (1, N, 4+nc)
            pred = np.transpose(pred, (0, 2, 1))
        pred = pred[0]  # (N, 4+nc)
        boxes_xywh = pred[:, :4]
        cls_scores = pred[:, 4:]
        conf = cls_scores.max(axis=1)
        cls  = cls_scores.argmax(axis=1)
        keep_mask = conf >= IO_CONF_THRESH
        boxes_xywh, conf, cls = boxes_xywh[keep_mask], conf[keep_mask], cls[keep_mask]
        # map to original image
        boxes = _xywh2xyxy(boxes_xywh)
        left, top = pad
        boxes[:, [0, 2]] -= left
        boxes[:, [1, 3]] -= top
        boxes /= ratio

        out: List[Dict[str, Any]] = []
        for c in np.unique(cls):
            idx = np.where(cls == c)[0]
            k = _nms(boxes[idx], conf[idx], IO_NMS_IOU)
            for j in k:
                x1, y1, x2, y2 = boxes[idx][j].tolist()
                score = float(conf[idx][j])
                label = COCO[int(c)] if int(c) < len(COCO) else str(int(c))
                out.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "conf": score, "label": label})
        return _clip(out, W, H)

    # Case B: SSD-like (x1,y1,x2,y2,score,cls)
    if pred.shape[2] == 6:
        arr = pred[0]  # (N,6)
        x1y1x2y2 = arr[:, 0:4].astype(np.float32)
        score    = arr[:, 4].astype(np.float32)
        cls_id   = arr[:, 5].astype(np.int32)
        m = score >= IO_CONF_THRESH
        x1y1x2y2, score, cls_id = x1y1x2y2[m], score[m], cls_id[m]
        # boxes are assumed in letterboxed space; undo pad/scale to original
        left, top = pad
        boxes = x1y1x2y2.copy()
        boxes[:, [0, 2]] -= left
        boxes[:, [1, 3]] -= top
        boxes /= max(ratio, 1e-9)

        out: List[Dict[str, Any]] = []
        for c in np.unique(cls_id):
            idx = np.where(cls_id == c)[0]
            k = _nms(boxes[idx], score[idx], IO_NMS_IOU)
            for j in k:
                x1, y1, x2, y2 = boxes[idx][j].tolist()
                s = float(score[idx][j])
                label = COCO[int(c)] if 0 <= int(c) < len(COCO) else str(int(c))
                out.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "conf": s, "label": label})
        return _clip(out, W, H)

    raise RuntimeError(f"Unhandled output layout: {pred.shape}")

def _infer(session: ort.InferenceSession, rgb: np.ndarray) -> Dict[str, Any]:
    H, W = rgb.shape[:2]
    img, r, pad = _letterbox(rgb, IO_IMG_SIZE)
    x = img.astype(np.float32) / 255.0
    x = np.transpose(x, (2, 0, 1))[None, ...]  # (1,3,H,W)
    input_name = session.get_inputs()[0].name
    y = session.run(None, {input_name: x})[0]
    dets = _postprocess(y, r, pad, (W, H))

    if IO_MODE == "binary":
        dets = [d for d in dets if d.get("label", "").lower() == BINARY_CLASS]

    return {
        "ok": True,
        "detections": dets,
        "image": {"width": W, "height": H, "mode": "RGB"},
        "model": {
            "name": os.path.basename(MODEL_PATH),
            "mode": IO_MODE,
            "conf": IO_CONF_THRESH,
            "iou": IO_NMS_IOU,
        },
    }

# -----------------------------
# SB parsing
# -----------------------------
def _parse_sb_message(message) -> Dict[str, Any]:
    body = getattr(message, "body", None)

    raw: bytes | None = None
    if body is None:
        pass
    elif isinstance(body, (bytes, bytearray)):
        raw = bytes(body)
    elif isinstance(body, str):
        raw = body.encode("utf-8", "ignore")
    else:
        # generator case
        try:
            raw = b"".join(
                part if isinstance(part, (bytes, bytearray)) else bytes(part)
                for part in body
            )
        except Exception:
            raw = None

    if raw:
        try:
            txt = raw.decode("utf-8", "ignore").strip()
            if txt.startswith("{") and txt.endswith("}"):
                return json.loads(txt)
        except Exception:
            pass

    if isinstance(body, dict):
        return dict(body)

    # application_properties fallback
    props: Dict[str, Any] = {}
    try:
        ap = getattr(message, "application_properties", None) or {}
        for k, v in ap.items():
            ks = k.decode() if isinstance(k, (bytes, bytearray)) else str(k)
            if isinstance(v, (bytes, bytearray)):
                try:
                    props[ks] = v.decode("utf-8", "ignore")
                except Exception:
                    props[ks] = repr(v)
            else:
                props[ks] = v
    except Exception:
        pass

    return props

# -----------------------------
# Main
# -----------------------------
def _load_session() -> ort.InferenceSession:
    p = _download_model()
    so = ort.SessionOptions()
    # (tuning options can be added)
    sess = ort.InferenceSession(p, sess_options=so, providers=["CPUExecutionProvider"])
    log.info("Loading ONNX model: %s", p)
    return sess

def main() -> None:
    global _INFERENCE_SESSION

    _start_health_server(HEALTH_PORT)

    if MODEL_URI:
        sess = _load_session()
        _INFERENCE_SESSION = sess
        log.info("Global ONNX model loaded — legacy /infer available.")
    else:
        log.warning("MODEL_URI/MODEL_URL not set — skipping global model. Detector-aware /infer still available.")

    if not SB_CONN or SB_CONN.strip().upper() == "DISABLED" or not HAS_AZURE:
        log.warning("Service Bus not available — running in health+infer server mode.")
        while True:
            time.sleep(3600)

    with ServiceBusClient.from_connection_string(SB_CONN, logging_enable=False) as sb:
        with sb.get_queue_receiver(queue_name=QUEUE_IN, max_wait_time=5) as rx:
            log.info("Listening IN=%s OUT=%s", QUEUE_IN, QUEUE_OUT)
            while True:
                try:
                    for msg in rx.receive_messages(max_message_count=10, max_wait_time=5) or []:
                        start_ts = time.perf_counter()
                        try:
                            doc = _parse_sb_message(msg) or {}
                            iq  = doc.get("image_query_id")
                            url = doc.get("blob_url") or doc.get("image_uri")
                            if not iq or not url:
                                raise ValueError("Missing required fields: image_query_id and/or blob_url")

                            log.info(
                                "msg_start iq=%s url=%s",
                                iq,
                                _redact_sas(str(url)),
                            )

                            b = _fetch_bytes(url)
                            img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
                            if img is None:
                                raise RuntimeError("Failed to decode image bytes")
                            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            result = _infer(sess, rgb)

                            latency_ms = int((time.perf_counter() - start_ts) * 1000.0)
                            n_dets = len(result.get("detections", []))

                            payload = {
                                "image_query_id": iq,
                                "ok": True,
                                "result": result,
                                "latency_ms": latency_ms,
                            }

                            log.info(
                                "msg_done iq=%s latency_ms=%d detections=%d",
                                iq,
                                latency_ms,
                                n_dets,
                            )

                            with sb.get_queue_sender(queue_name=QUEUE_OUT) as tx:
                                tx.send_messages(ServiceBusMessage(json.dumps(payload)))
                            rx.complete_message(msg)
                        except Exception as e:
                            log.exception("processing_failed: %s", e)
                            try:
                                rx.dead_letter_message(msg)
                            except Exception:
                                rx.abandon_message(msg)
                except Exception as loop_err:
                    log.warning("receive loop error: %s (sleep 1s)", loop_err)
                    time.sleep(1)

if __name__ == "__main__":
    main()
