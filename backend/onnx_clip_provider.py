"""Verified, local-only CLIP image embedding provider.

The provider never downloads a model.  A caller supplies a local ONNX file,
its expected SHA-256 and its declared license.  The model contract is checked
before the first image can be embedded.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image
from visual_candidates import (
    EmbeddingDescriptor,
    EmbeddingProviderUnavailable,
    VisualCandidateError,
)

IMAGE_SIZE = 224
PIXEL_MEAN = np.asarray([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
PIXEL_STD = np.asarray([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preprocess_clip_image(image: Image.Image) -> np.ndarray:
    """Apply the model card's resize, center-crop and normalization contract."""

    source = image.convert("RGB")
    width, height = source.size
    if width < 1 or height < 1:
        raise VisualCandidateError("image dimensions are invalid")
    scale = IMAGE_SIZE / min(width, height)
    resized_width = max(IMAGE_SIZE, round(width * scale))
    resized_height = max(IMAGE_SIZE, round(height * scale))
    source = source.resize((resized_width, resized_height), Image.Resampling.BICUBIC)
    left = (resized_width - IMAGE_SIZE) // 2
    top = (resized_height - IMAGE_SIZE) // 2
    source = source.crop((left, top, left + IMAGE_SIZE, top + IMAGE_SIZE))
    pixels = np.asarray(source, dtype=np.float32) / np.float32(255.0)
    pixels = (pixels - PIXEL_MEAN) / PIXEL_STD
    return np.ascontiguousarray(pixels.transpose(2, 0, 1)[None, ...], dtype=np.float32)


class VerifiedOnnxClipProvider:
    """CPU ONNX adapter with immutable model provenance and no network access."""

    def __init__(
        self,
        *,
        model_path: str | Path,
        expected_sha256: str,
        license_id: str,
        model_name: str = "Qdrant-clip-ViT-B-32-vision",
        weights_id: str = "model.onnx",
        dimensions: int = 512,
    ) -> None:
        path = Path(model_path).expanduser().resolve()
        if not path.is_file() or path.is_symlink():
            raise EmbeddingProviderUnavailable("CLIP ONNX model dosyası bulunamadı veya güvenli değil")
        actual_sha256 = sha256_file(path)
        if actual_sha256 != str(expected_sha256 or "").strip().lower():
            raise EmbeddingProviderUnavailable("CLIP ONNX model SHA-256 doğrulaması başarısız")
        self._descriptor = EmbeddingDescriptor(
            provider="onnxruntime",
            model_name=model_name,
            weights_id=weights_id,
            weights_sha256=actual_sha256,
            license_id=license_id,
            dimensions=dimensions,
        )
        try:
            import onnxruntime as ort

            session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        except Exception as exc:  # pragma: no cover - runtime/platform dependent
            raise EmbeddingProviderUnavailable("CLIP ONNX modeli yüklenemedi") from exc
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if len(inputs) != 1 or inputs[0].name != "pixel_values":
            raise EmbeddingProviderUnavailable("CLIP ONNX giriş sözleşmesi beklenen biçimde değil")
        matching_outputs = [
            output
            for output in outputs
            if output.name == "image_embeds"
            and len(output.shape) == 2
            and output.shape[-1] == dimensions
        ]
        if len(matching_outputs) != 1:
            raise EmbeddingProviderUnavailable("CLIP ONNX çıkış sözleşmesi beklenen biçimde değil")
        self._session = session
        self._input_name = inputs[0].name
        self._output_name = matching_outputs[0].name

    @property
    def descriptor(self) -> EmbeddingDescriptor:
        return self._descriptor

    def embed(self, image: Image.Image) -> Sequence[float]:
        try:
            pixels = preprocess_clip_image(image.copy())
            output = self._session.run([self._output_name], {self._input_name: pixels})[0]
            vector = np.asarray(output[0], dtype=np.float64)
        except Exception as exc:  # pragma: no cover - onnxruntime failures are platform dependent
            raise EmbeddingProviderUnavailable("CLIP ONNX görüntü çıkarımı başarısız") from exc
        if vector.shape != (self._descriptor.dimensions,) or not np.isfinite(vector).all():
            raise EmbeddingProviderUnavailable("CLIP ONNX geçersiz embedding üretti")
        return vector.tolist()
