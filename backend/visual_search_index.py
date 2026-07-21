"""Lightweight visual search index using ONNX Runtime + CLIP embeddings.

We deliberately keep the model small (ViT-B-32 via ONNX) so that CPU inference
is tolerable for a single-server deploy.  The index lives in MongoDB (float32
arrays) instead of pgvector to avoid an extra database dependency.

Heavier solutions (OpenCLIP GPU, FAISS IVF) are intentionally deferred until
the catalog size warrants them.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from PIL import Image

logger = logging.getLogger("shoehunter.visual_search")

_ONNX_MODEL_URL = os.environ.get(
    "CLIP_ONNX_MODEL_URL",
    "https://huggingface.co/nickmuchi/clip-vit-base-patch32-onnx/resolve/main/model.onnx",
)
_MODEL_DIR = Path(__file__).parent / ".models"
_MODEL_PATH = _MODEL_DIR / "clip_visual.onnx"
_EMBEDDING_DIM = 512
_IMAGE_SIZE = 224
_PIXEL_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
_PIXEL_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

_session = None
_session_lock = threading.Lock()


def _preprocess_image(image: Image.Image) -> np.ndarray:
    """Resize, center-crop and normalize an image for CLIP ViT-B-32."""
    image = image.convert("RGB")
    # Resize so the shorter side is _IMAGE_SIZE, then center-crop.
    width, height = image.size
    scale = _IMAGE_SIZE / min(width, height)
    new_width, new_height = int(width * scale), int(height * scale)
    image = image.resize((new_width, new_height), Image.LANCZOS)
    left = (new_width - _IMAGE_SIZE) // 2
    top = (new_height - _IMAGE_SIZE) // 2
    image = image.crop((left, top, left + _IMAGE_SIZE, top + _IMAGE_SIZE))

    pixel_values = np.array(image, dtype=np.float32) / 255.0
    pixel_values = (pixel_values - _PIXEL_MEAN) / _PIXEL_STD
    # HWC -> CHW -> NCHW
    pixel_values = pixel_values.transpose(2, 0, 1)[np.newaxis, ...]
    return pixel_values


def _ensure_model() -> Path:
    """Download the ONNX visual model if it doesn't exist locally."""
    if _MODEL_PATH.exists():
        return _MODEL_PATH
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("CLIP ONNX modeli indiriliyor: %s", _ONNX_MODEL_URL)
    with httpx.Client(timeout=120) as client:
        response = client.get(_ONNX_MODEL_URL, follow_redirects=True)
        response.raise_for_status()
        _MODEL_PATH.write_bytes(response.content)
    logger.info("CLIP ONNX modeli kaydedildi: %s (%d bytes)", _MODEL_PATH, _MODEL_PATH.stat().st_size)
    return _MODEL_PATH


def _get_session():
    """Lazy-load the ONNX inference session."""
    global _session
    if _session is not None:
        return _session
    with _session_lock:
        if _session is not None:
            return _session
        import onnxruntime as ort
        model_path = _ensure_model()
        _session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        logger.info("CLIP ONNX session hazir (%s)", model_path.name)
        return _session


def compute_embedding(image: Image.Image) -> list[float]:
    """Compute a normalized 512-d CLIP embedding from a PIL Image."""
    session = _get_session()
    pixel_values = _preprocess_image(image)
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: pixel_values})
    embedding = outputs[0][0].astype(np.float64)
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    return embedding.tolist()


def compute_embedding_from_bytes(data: bytes) -> list[float]:
    """Compute embedding from raw image bytes."""
    image = Image.open(BytesIO(data))
    return compute_embedding(image)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    vec_a = np.array(a, dtype=np.float64)
    vec_b = np.array(b, dtype=np.float64)
    dot = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def image_hash(data: bytes) -> str:
    """SHA-256 of image bytes for dedup."""
    return hashlib.sha256(data).hexdigest()
