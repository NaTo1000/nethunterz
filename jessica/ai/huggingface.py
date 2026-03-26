"""Hugging Face Integration Layer — full uncensored model access with
parallel and series inference, model placement control, and caching.

Wraps the ``huggingface_hub`` and ``transformers`` libraries to provide
a high‑level async API for the rest of the JESSICA platform.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jessica.ai.huggingface")


@dataclass
class ModelInfo:
    """Metadata about a loaded or available model."""

    model_id: str
    task: str = ""  # "text-generation", "zero-shot-classification", "feature-extraction"
    loaded: bool = False
    device: str = "cpu"
    parameters: dict[str, Any] = field(default_factory=dict)


class HuggingFaceLayer:
    """Manages Hugging Face model loading, inference, and lifecycle.

    Features:
    - Full model catalogue access (including uncensored community models)
    - Model placement control (CPU / GPU / specific device)
    - Parallel inference (multiple models simultaneously)
    - Series inference (chained model pipeline)
    - Intelligent caching via HF Hub cache
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._cfg = config
        hf_cfg = config.get("huggingface", config)
        self._enabled = hf_cfg.get("enabled", True)
        self._cache_dir = hf_cfg.get("model_cache", os.getenv("HF_HOME", "/tmp/hf_cache"))
        self._default_models = hf_cfg.get("default_models", {})
        self._placement_control = hf_cfg.get("placement_control", True)
        self._parallel_inference = hf_cfg.get("parallel_inference", True)
        self._series_inference = hf_cfg.get("series_inference", True)

        self._loaded_models: dict[str, ModelInfo] = {}
        self._pipelines: dict[str, Any] = {}

    # ── lifecycle ─────────────────────────────────────────

    async def start(self) -> None:
        if not self._enabled:
            logger.info("HuggingFaceLayer disabled by config")
            return
        logger.info(
            "HuggingFaceLayer started — cache=%s  parallel=%s  series=%s",
            self._cache_dir,
            self._parallel_inference,
            self._series_inference,
        )

    async def stop(self) -> None:
        self._pipelines.clear()
        self._loaded_models.clear()
        logger.info("HuggingFaceLayer stopped — all models unloaded")

    # ── model management ──────────────────────────────────

    async def load_model(self, model_id: str, task: str = "text-generation", device: str = "cpu") -> ModelInfo:
        """Load a model from Hugging Face Hub (or cache)."""
        if model_id in self._loaded_models:
            return self._loaded_models[model_id]

        info = ModelInfo(model_id=model_id, task=task, device=device)

        try:
            from transformers import pipeline as hf_pipeline  # type: ignore[import-untyped]

            pipe = hf_pipeline(
                task,
                model=model_id,
                device=device,
                cache_dir=self._cache_dir,
            )
            self._pipelines[model_id] = pipe
            info.loaded = True
        except ImportError:
            logger.warning("transformers library not available — model %s registered but not loaded", model_id)
        except Exception as exc:
            logger.error("Failed to load model %s: %s", model_id, exc)

        self._loaded_models[model_id] = info
        logger.info("Model registered: %s (loaded=%s, device=%s)", model_id, info.loaded, device)
        return info

    def unload_model(self, model_id: str) -> None:
        self._pipelines.pop(model_id, None)
        info = self._loaded_models.pop(model_id, None)
        if info:
            logger.info("Model unloaded: %s", model_id)

    def list_models(self) -> list[ModelInfo]:
        return list(self._loaded_models.values())

    # ── inference ─────────────────────────────────────────

    async def generate(self, prompt: str, model_id: str | None = None, **kwargs: Any) -> str:
        """Generate text using a loaded model."""
        mid = model_id or self._default_models.get("text_generation", "")
        pipe = self._pipelines.get(mid)
        if pipe is None:
            logger.warning("Model %s not loaded — returning empty", mid)
            return ""
        max_tokens = kwargs.get("max_new_tokens", 512)
        result = pipe(prompt, max_new_tokens=max_tokens, do_sample=True)
        if isinstance(result, list) and result:
            return result[0].get("generated_text", "")
        return str(result)

    async def classify(self, text: str, labels: list[str], model_id: str | None = None) -> dict[str, Any]:
        """Zero‑shot classification."""
        mid = model_id or self._default_models.get("classification", "")
        pipe = self._pipelines.get(mid)
        if pipe is None:
            logger.warning("Classification model %s not loaded — returning stub", mid)
            return {"label": labels[0] if labels else "", "score": 0.0}
        result = pipe(text, candidate_labels=labels)
        return {"label": result["labels"][0], "score": result["scores"][0]}

    async def embed(self, texts: list[str], model_id: str | None = None) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        mid = model_id or self._default_models.get("embedding", "")
        pipe = self._pipelines.get(mid)
        if pipe is None:
            logger.warning("Embedding model %s not loaded — returning empty", mid)
            return [[0.0]] * len(texts)
        outputs = pipe(texts)
        # Flatten CLS token embeddings
        return [out[0].tolist() if hasattr(out[0], "tolist") else out[0] for out in outputs]

    # ── placement control ─────────────────────────────────

    async def move_model(self, model_id: str, target_device: str) -> None:
        """Move a loaded model to a different device (CPU ↔ GPU)."""
        if not self._placement_control:
            raise RuntimeError("Model placement control is disabled")
        pipe = self._pipelines.get(model_id)
        if pipe is None:
            raise KeyError(f"Model {model_id} not loaded")
        if hasattr(pipe, "model") and hasattr(pipe.model, "to"):
            pipe.model.to(target_device)
            info = self._loaded_models.get(model_id)
            if info:
                info.device = target_device
            logger.info("Model %s moved to %s", model_id, target_device)
