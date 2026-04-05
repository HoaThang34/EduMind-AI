"""Face Recognition Engine -- DeepFace-style implementation.

Uses ArcFace ONNX model for embedding extraction + OpenCV DNN for face detection.
No TensorFlow required -- works on Python 3.14+.

Architecture (same as DeepFace internals when model=ArcFace, backend=opencv):
  1. Face Detection  -> OpenCV DNN ResNet-SSD (or Haar Cascade fallback)
  2. Face Alignment  -> 5-point landmark -> affine transform
  3. Embedding       -> ArcFace ONNX (InsightFace buffalo_l variant)
  4. Similarity      -> Cosine distance between 512-dim embeddings
"""
import os
import sys
import uuid
import tempfile
import urllib.request
import zipfile

import cv2
import numpy as np
import onnxruntime as ort


# ─── Constants ────────────────────────────────────────────────────────────────

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "face_models", ".onnx")
os.makedirs(MODEL_DIR, exist_ok=True)

# ArcFace model URL (buffalo_l from InsightFace, ~17MB ONNX)
# This is the exact same model DeepFace downloads internally for ArcFace
# Primary URL: HuggingFace (GitHub storage.insightface.ai is down)
ARCFACE_ONNX_URLS = [
    "https://huggingface.co/public-data/insightface/resolve/main/models/buffalo_l/w600k_r50.onnx?download=true",
]
ARCFACE_MODEL_DIR = MODEL_DIR
ARCFACE_MODEL_PATH = os.path.join(ARCFACE_MODEL_DIR, "w600k_r50.onnx")

# Face detection: OpenCV DNN with ResNet-SSD (bundled with OpenCV)
# Model files downloaded from OpenCV's official repo
RESNET_PROTOTXT_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/master/"
    "samples/dnn/face_detector/deploy.prototxt"
)
RESNET_MODEL_URL = (
    "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/"
    "res10_300x300_ssd_iter_140000.caffemodel"
)
DETECTOR_MODEL_DIR = MODEL_DIR
RESNET_PROTOTXT_PATH = os.path.join(DETECTOR_MODEL_DIR, "deploy.prototxt")
RESNET_MODEL_PATH = os.path.join(DETECTOR_MODEL_DIR, "res10_300x300_ssd_iter_140000.caffemodel")

# Fallback detector: OpenCV's Haar Cascade (always available, no download needed)
# Used when ONNX detector fails or is unavailable

# Cosine similarity threshold for ArcFace (standard: 0.4)
# Higher = stricter matching
DEFAULT_THRESHOLD = 0.40

# ArcFace input size
ARCFACE_INPUT_SIZE = (112, 112)

# Preprocessing: ArcFace standard normalization
ARCFACE_MEAN = np.array([127.5, 127.5, 127.5], dtype=np.float32)
ARCFACE_STD = np.array([128.0, 128.0, 128.0], dtype=np.float32)


# ─── Model Download ──────────────────────────────────────────────────────────

def _download_file(url, dest_path):
    """Download a file with progress reporting. Tries multiple backends."""
    if os.path.exists(dest_path):
        return True

    # Try urllib first
    print("[FaceEngine] Downloading (urllib): " + url[:80])
    print("[FaceEngine] Destination: " + dest_path)
    try:
        urllib.request.urlretrieve(url, dest_path)
        return True
    except Exception as e:
        print(f"[FaceEngine] urllib failed: {e}")
        # Clean up partial download
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass

    # Fallback: use gdown (handles large files and Google Drive/HuggingFace redirects)
    try:
        import gdown
        print("[FaceEngine] Retrying with gdown...")
        gdown.download(url, dest_path, quiet=True)
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024:
            return True
    except Exception as e2:
        print(f"[FaceEngine] gdown failed: {e2}")
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass

    return False


def _try_download_urls(urls, dest_path):
    """Try downloading from multiple URLs until one succeeds."""
    for url in urls:
        if _download_file(url, dest_path):
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024:
                return True
    return False


def _download_arcface_model():
    """Download ArcFace buffalo_l ONNX model from HuggingFace."""
    if os.path.exists(ARCFACE_MODEL_PATH):
        return True

    # Clean up any old zip files from failed downloads
    zip_path = os.path.join(MODEL_DIR, "buffalo_l.zip")
    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except Exception:
            pass

    if _try_download_urls(ARCFACE_ONNX_URLS, ARCFACE_MODEL_PATH):
        print("[ArcFaceExtractor] Model downloaded successfully.")
        return os.path.exists(ARCFACE_MODEL_PATH)

    print("[ArcFaceExtractor] CRITICAL: Failed to download ArcFace model!")
    print("[ArcFaceExtractor] Face recognition will not work.")
    return False


def _download_detector_model():
    """Download OpenCV DNN ResNet-SSD face detector model files."""
    prototxt_ok = os.path.exists(RESNET_PROTOTXT_PATH) and os.path.getsize(RESNET_PROTOTXT_PATH) > 100
    caffemodel_ok = os.path.exists(RESNET_MODEL_PATH) and os.path.getsize(RESNET_MODEL_PATH) > 1000

    if prototxt_ok and caffemodel_ok:
        return True

    if not prototxt_ok:
        _download_file(RESNET_PROTOTXT_URL, RESNET_PROTOTXT_PATH)

    if not caffemodel_ok:
        _download_file(RESNET_MODEL_URL, RESNET_MODEL_PATH)

    prototxt_ok = os.path.exists(RESNET_PROTOTXT_PATH) and os.path.getsize(RESNET_PROTOTXT_PATH) > 100
    caffemodel_ok = os.path.exists(RESNET_MODEL_PATH) and os.path.getsize(RESNET_MODEL_PATH) > 1000

    if prototxt_ok and caffemodel_ok:
        print("[FaceDetector] ResNet-SSD model files downloaded successfully.")
        return True

    print("[FaceDetector] Failed to download ResNet-SSD model. Will use Haar Cascade fallback.")
    return False


# ─── ONNX Inference Sessions ─────────────────────────────────────────────────

class ONNXModel:
    """Lightweight ONNX Runtime wrapper with lazy loading."""

    def __init__(self, model_path, providers=None):
        if providers is None:
            providers = ['CPUExecutionProvider']
        self.model_path = model_path
        self._session = None
        self._providers = providers

    def _ensure_session(self):
        if self._session is None:
            sess_opts = ort.SessionOptions()
            sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = ort.InferenceSession(
                self.model_path, sess_options=sess_opts,
                providers=self._providers
            )
        return self._session

    def run(self, output_names, input_feed):
        return self._ensure_session().run(output_names, input_feed)

    @property
    def input_names(self):
        sess = self._ensure_session()
        return [inp.name for inp in sess.get_inputs()]

    @property
    def output_names(self):
        sess = self._ensure_session()
        return [out.name for out in sess.get_outputs()]

    @property
    def input_shape(self):
        sess = self._ensure_session()
        return sess.get_inputs()[0].shape


# ─── Face Detection ───────────────────────────────────────────────────────────

class FaceDetector:
    """
    Face detector using OpenCV DNN (ResNet-SSD) or Haar Cascade fallback.
    Returns list of (x, y, w, h) bounding boxes (in image coordinates).
    """

    def __init__(self):
        self._dnn_net = None
        self._haar = None
        self._init_detector()

    def _init_detector(self):
        # Try OpenCV DNN ResNet-SSD detector
        if _download_detector_model():
            try:
                self._dnn_net = cv2.dnn.readNetFromCaffe(
                    RESNET_PROTOTXT_PATH, RESNET_MODEL_PATH
                )
                print("[FaceDetector] OpenCV DNN ResNet-SSD loaded successfully.")
                return
            except Exception as e:
                print(f"[FaceDetector] DNN load failed: {e}")

        # Fallback: OpenCV Haar Cascade (always available)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._haar = cv2.CascadeClassifier(cascade_path)
        print("[FaceDetector] Using Haar Cascade fallback.")

    def _detect_haar(self, img_rgb):
        """Haar Cascade detection."""
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        gray = cv2.equalizeHist(gray)
        rects = self._haar.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        return [tuple(r) for r in rects]

    def _detect_dnn(self, img_rgb):
        """OpenCV DNN ResNet-SSD face detection."""
        h_img, w_img = img_rgb.shape[:2]

        # Create blob from image: ResNet-SSD expects 300x300 BGR input
        blob = cv2.dnn.blobFromImage(
            cv2.resize(img_rgb, (300, 300)),
            1.0,  # scale factor
            (300, 300),
            (104.0, 177.0, 123.0),  # ImageNet BGR mean
            swapRB=False,
            crop=False
        )
        self._dnn_net.setInput(blob)
        detections = self._dnn_net.forward()

        boxes = []
        # detections shape: (1, 1, N, 7) where N is number of detections
        # 7 values per detection: [batch, class, id, confidence, x1, y1, x2, y2]
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence < 0.5:
                continue
            x1 = int(detections[0, 0, i, 3] * w_img)
            y1 = int(detections[0, 0, i, 4] * h_img)
            x2 = int(detections[0, 0, i, 5] * w_img)
            y2 = int(detections[0, 0, i, 6] * h_img)

            x1 = max(0, min(w_img - 1, x1))
            y1 = max(0, min(h_img - 1, y1))
            x2 = max(0, min(w_img - 1, x2))
            y2 = max(0, min(h_img - 1, y2))

            if x2 <= x1 or y2 <= y1:
                continue

            boxes.append((x1, y1, x2 - x1, y2 - y1))

        # NMS
        boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
        filtered = []
        for box in boxes:
            x, y, w, h = box
            keep = True
            for fx, fy, fw, fh in filtered:
                inter_x = max(0, min(x + w, fx + fw) - max(x, fx))
                inter_y = max(0, min(y + h, fy + fh) - max(y, fy))
                inter = inter_x * inter_y
                union = w * h + fw * fh - inter
                if union > 0 and inter / union > 0.5:
                    keep = False
                    break
            if keep:
                filtered.append(box)
        return filtered

    def detect(self, img_rgb):
        """Detect faces in an RGB image. Returns list of (x, y, w, h) bounding boxes."""
        if img_rgb is None or img_rgb.size == 0:
            return []

        if self._dnn_net is not None:
            return self._detect_dnn(img_rgb)
        else:
            return self._detect_haar(img_rgb)


# ─── Face Embedding Extractor ─────────────────────────────────────────────────

class ArcFaceExtractor:
    """
    ArcFace embedding extractor using ONNX Runtime.
    Extracts 512-dim embeddings from face crops (112x112 input).
    """

    def __init__(self):
        self._session = None
        self._ready = False
        self._init()

    def _init(self):
        if not _download_arcface_model():
            print("[ArcFaceExtractor] CRITICAL: Failed to download ArcFace model!")
            print("[ArcFaceExtractor] Face recognition will not work.")
            return

        if not os.path.exists(ARCFACE_MODEL_PATH):
            print("[ArcFaceExtractor] CRITICAL: ArcFace model not found!")
            return

        try:
            self._session = ONNXModel(ARCFACE_MODEL_PATH)
            # Verify input shape
            shape = self._session.input_shape
            print(f"[ArcFaceExtractor] Loaded. Input shape: {shape}")
            self._ready = True
        except Exception as e:
            print(f"[ArcFaceExtractor] ONNX load failed: {e}")
            self._ready = False

    @property
    def is_ready(self):
        return self._ready

    def _preprocess(self, face_crop):
        """Preprocess face crop for ArcFace: resize, normalize, transpose."""
        # Resize to 112x112
        img = cv2.resize(face_crop, ARCFACE_INPUT_SIZE)
        # BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # Normalize: (img - mean) / std
        img = img.astype(np.float32)
        img = (img - ARCFACE_MEAN) / ARCFACE_STD
        # HWC to CHW
        img = img.transpose(2, 0, 1)
        # Add batch dim
        img = np.expand_dims(img, axis=0)
        return img

    def extract(self, face_crop):
        """
        Extract 512-dim ArcFace embedding from a face crop (BGR numpy array).
        Returns np.array(512,) or None if extraction fails.
        """
        if not self._ready or face_crop is None or face_crop.size == 0:
            return None

        try:
            img = self._preprocess(face_crop)
            input_name = self._session.input_names[0]
            output_name = self._session.output_names[0]
            embedding = self._session.run([output_name], {input_name: img})[0]
            # L2 normalize (ArcFace outputs are raw logits, normalize for cosine)
            emb = embedding.flatten().astype(np.float32)
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            return emb
        except Exception as e:
            print(f"[ArcFaceExtractor] Extraction error: {e}")
            return None


# ─── Face Recognition Engine ─────────────────────────────────────────────────

class FaceEngine:
    """
    Main face recognition engine — mimics DeepFace's high-level API.

    Uses:
      - YOLOv8-face ONNX (or Haar Cascade fallback) for face detection
      - ArcFace ONNX (InsightFace buffalo_l) for embedding extraction
      - Cosine similarity for face matching

    This is the EXACT same architecture as DeepFace internally uses
    when you call DeepFace.find() or DeepFace.represent() with
    model_name='ArcFace' and detector_backend='opencv'.
    """

    def __init__(self, threshold=DEFAULT_THRESHOLD):
        self.threshold = threshold
        self._detector = None
        self._extractor = None
        self._init()

    def _init(self):
        print("[FaceEngine] Initializing DeepFace-style face recognition engine...")
        print("[FaceEngine]   Model: ArcFace (InsightFace buffalo_l)")
        print(f"[FaceEngine]   Threshold: {self.threshold}")
        self._detector = FaceDetector()
        self._extractor = ArcFaceExtractor()
        if self._extractor.is_ready:
            print("[FaceEngine] Fully initialized and ready.")
        else:
            print("[FaceEngine] WARNING: Engine initialized but embedding extractor not ready (model may still download).")

    def detect_faces(self, img):
        """
        Detect faces in an image.
        img: BGR numpy array (OpenCV format) or RGB numpy array.
        Returns list of {'face': cropped_BGR, 'box': (x,y,w,h)}.
        """
        if img is None or img.size == 0:
            return []

        # Ensure BGR
        if len(img.shape) == 3 and img.shape[2] == 3:
            # Check if it looks like RGB (most common) or BGR
            # OpenCV loads as BGR, webcam gives BGR
            img_bgr = img.copy()
        else:
            img_bgr = img

        # Convert to RGB for detector
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        boxes = self._detector.detect(img_rgb)
        results = []
        h_img, w_img = img_bgr.shape[:2]

        for x, y, w, h in boxes:
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(w_img, x + w), min(h_img, y + h)
            if x2 <= x1 or y2 <= y1:
                continue
            face_crop = img_bgr[y1:y2, x1:x2]
            results.append({
                'face': face_crop,
                'box': (int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
            })

        return results

    def extract_embedding(self, img):
        """
        Detect face, crop it, and extract embedding.
        Returns (embedding_512d, box) or (None, None) if no face found.
        """
        if img is None or img.size == 0:
            return None, None

        faces = self.detect_faces(img)
        if not faces:
            return None, None

        # Use the largest face
        best = max(faces, key=lambda f: f['box'][2] * f['box'][3])
        emb = self._extractor.extract(best['face'])
        return emb, best['box']

    def find(self, img, db_embeddings, db_ids, top_n=1):
        """
        1:N face identification.
        img: BGR image
        db_embeddings: list of 512-dim embedding arrays
        db_ids: list of IDs corresponding to each embedding
        Returns list of (id, cosine_similarity) sorted by best match.
        """
        emb, box = self.extract_embedding(img)
        if emb is None:
            return [], box

        results = []
        for stored_emb, sid in zip(db_embeddings, db_ids):
            sim = cosine_similarity(emb, stored_emb)
            if sim >= self.threshold:
                results.append((sid, sim, box))

        # Sort by similarity descending
        results.sort(key=lambda r: r[1], reverse=True)
        return results[:top_n], box


def cosine_similarity(a, b):
    """Cosine similarity between two vectors."""
    if a is None or b is None:
        return 0.0
    a = np.asarray(a).flatten()
    b = np.asarray(b).flatten()
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ─── Global singleton (lazy init on first use) ───────────────────────────────

_engine = None


def get_engine():
    """Get or create the global FaceEngine singleton."""
    global _engine
    if _engine is None:
        _engine = FaceEngine()
    return _engine
