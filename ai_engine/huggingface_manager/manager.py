"""
Hugging Face Model Manager.

Handles dynamic download, loading, inference, and deletion of HuggingFace
transformer models via the orchestration engine. Supports uncensored model
selection with on-demand loading to minimize runtime memory footprint.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class ModelStatus(Enum):
    AVAILABLE = "available"      # Registered but not downloaded
    DOWNLOADING = "downloading"  # Currently being fetched
    READY = "ready"             # Downloaded and ready to load
    LOADED = "loaded"           # Currently in memory
    ERROR = "error"             # Download/load failed


@dataclass
class ModelConfig:
    """Configuration for a Hugging Face model."""
    model_id: str                          # e.g. "mistralai/Mistral-7B-v0.1"
    alias: str                             # Short name for orchestration
    quantization: Optional[str] = None    # "4bit", "8bit", None
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    @property
    def cache_key(self) -> str:
        return hashlib.md5(self.model_id.encode()).hexdigest()[:16]


@dataclass
class ModelRecord:
    """Runtime record for a managed model."""
    config: ModelConfig
    status: ModelStatus = ModelStatus.AVAILABLE
    local_path: Optional[str] = None
    download_size_mb: float = 0.0
    downloaded_at: Optional[float] = None
    loaded_at: Optional[float] = None
    inference_count: int = 0
    last_used: Optional[float] = None
    error_message: Optional[str] = None


class HuggingFaceModelManager:
    """
    HuggingFace Model Manager for the Grok 420 / CHAiMERA stack.

    Provides orchestration-controlled model lifecycle:
    - Register models by HuggingFace ID
    - Download models on demand (simulated in offline environments)
    - Load/unload models to manage memory
    - Run inference through the loaded model
    - Delete models from local storage
    - Full model catalog with status tracking
    """

    VERSION = "1.0.0"
    DEFAULT_MODELS_DIR = Path("models")

    # Curated model catalog with uncensored / unrestricted options
    CATALOG: List[ModelConfig] = [
        ModelConfig(
            "mistralai/Mistral-7B-v0.1", "mistral-7b",
            quantization="4bit", tags=["text-gen", "instruction"],
        ),
        ModelConfig(
            "NousResearch/Nous-Hermes-2-Mistral-7B-DPO", "nous-hermes",
            quantization="4bit", tags=["instruction", "chat"],
        ),
        ModelConfig(
            "teknium/OpenHermes-2.5-Mistral-7B", "openhermes",
            quantization="4bit", tags=["chat", "instruction"],
        ),
        ModelConfig(
            "TheBloke/dolphin-2.2-mistral-7B-GGUF", "dolphin",
            quantization="4bit", tags=["uncensored", "chat"],
            notes="Uncensored Dolphin model",
        ),
        ModelConfig(
            "meta-llama/Llama-2-7b-chat-hf", "llama2-7b",
            quantization="4bit", tags=["chat", "instruction"],
        ),
        ModelConfig(
            "codellama/CodeLlama-7b-Instruct-hf", "codellama",
            quantization="4bit", tags=["code", "instruction"],
        ),
        ModelConfig(
            "microsoft/phi-2", "phi-2",
            quantization=None, tags=["small", "fast"],
        ),
        ModelConfig(
            "tiiuae/falcon-7b-instruct", "falcon",
            quantization="4bit", tags=["instruction"],
        ),
    ]

    def __init__(
        self,
        models_dir: Optional[Path] = None,
        max_loaded_models: int = 2,
    ) -> None:
        self.models_dir = models_dir or self.DEFAULT_MODELS_DIR
        self.max_loaded_models = max_loaded_models
        self._registry: Dict[str, ModelRecord] = {}
        self._loaded_order: List[str] = []  # LRU tracking

        # Register catalog models
        for cfg in self.CATALOG:
            self._registry[cfg.alias] = ModelRecord(config=cfg)

    def register(self, config: ModelConfig) -> None:
        """Register a custom model configuration."""
        self._registry[config.alias] = ModelRecord(config=config)
        logger.info(f"[HFManager] Registered model: {config.alias} ({config.model_id})")

    def list_models(
        self,
        status_filter: Optional[ModelStatus] = None,
        tag_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all registered models with optional filtering."""
        results = []
        for alias, record in self._registry.items():
            if status_filter and record.status != status_filter:
                continue
            if tag_filter and tag_filter not in record.config.tags:
                continue
            results.append({
                "alias": alias,
                "model_id": record.config.model_id,
                "status": record.status.value,
                "quantization": record.config.quantization,
                "tags": record.config.tags,
                "inference_count": record.inference_count,
                "local_path": record.local_path,
            })
        return results

    async def download(self, alias: str) -> bool:
        """
        Download a model from HuggingFace Hub.

        In production this calls the transformers library. Here we simulate
        the download for environments without GPU / internet access.
        """
        record = self._registry.get(alias)
        if not record:
            logger.error(f"[HFManager] Unknown model: {alias}")
            return False

        if record.status in (ModelStatus.READY, ModelStatus.LOADED):
            logger.info(f"[HFManager] Model already available: {alias}")
            return True

        record.status = ModelStatus.DOWNLOADING
        logger.info(f"[HFManager] Downloading: {record.config.model_id}")

        try:
            # Simulate download (in production: snapshot_download or hf_hub_download)
            await asyncio.sleep(0.1)  # simulate network I/O

            local_path = self.models_dir / record.config.cache_key
            local_path.mkdir(parents=True, exist_ok=True)

            # Write a model manifest
            manifest = {
                "model_id": record.config.model_id,
                "alias": alias,
                "downloaded_at": time.time(),
                "quantization": record.config.quantization,
                "simulated": True,
            }
            (local_path / "manifest.json").write_text(
                json.dumps(manifest, indent=2)
            )

            record.local_path = str(local_path)
            record.downloaded_at = time.time()
            record.download_size_mb = 4096.0  # simulated size
            record.status = ModelStatus.READY
            logger.info(f"[HFManager] Download complete: {alias}")
            return True

        except Exception as e:
            record.status = ModelStatus.ERROR
            record.error_message = str(e)
            logger.error(f"[HFManager] Download failed: {alias} | {e}")
            return False

    async def load(self, alias: str) -> bool:
        """Load a model into memory, evicting LRU if at capacity."""
        record = self._registry.get(alias)
        if not record:
            return False

        if record.status == ModelStatus.LOADED:
            return True

        if record.status != ModelStatus.READY:
            downloaded = await self.download(alias)
            if not downloaded:
                return False

        # Evict LRU if at capacity
        while len(self._loaded_order) >= self.max_loaded_models:
            evict = self._loaded_order.pop(0)
            self._unload(evict)

        record.status = ModelStatus.LOADED
        record.loaded_at = time.time()
        self._loaded_order.append(alias)
        logger.info(f"[HFManager] Model loaded: {alias}")
        return True

    def _unload(self, alias: str) -> None:
        """Unload a model from memory (keep local files)."""
        record = self._registry.get(alias)
        if record and record.status == ModelStatus.LOADED:
            record.status = ModelStatus.READY
            logger.info(f"[HFManager] Model unloaded: {alias}")

    async def infer(
        self,
        alias: str,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Run inference with the specified model.

        Returns a structured response dict compatible with OpenAI format.
        """
        if not await self.load(alias):
            return {"error": f"Failed to load model: {alias}", "text": ""}

        record = self._registry[alias]
        cfg = record.config

        # Simulate inference (in production: model.generate())
        await asyncio.sleep(0.05)

        record.inference_count += 1
        record.last_used = time.time()

        # Update LRU order
        if alias in self._loaded_order:
            self._loaded_order.remove(alias)
            self._loaded_order.append(alias)

        return {
            "model": alias,
            "model_id": cfg.model_id,
            "prompt": prompt,
            "text": f"[{alias}] Simulated inference response for: {prompt[:50]}...",
            "tokens_generated": max_tokens or cfg.max_tokens,
            "temperature": temperature or cfg.temperature,
            "inference_count": record.inference_count,
            "timestamp": time.time(),
        }

    def delete(self, alias: str) -> bool:
        """Delete a downloaded model from local storage."""
        record = self._registry.get(alias)
        if not record:
            return False

        if record.status == ModelStatus.LOADED:
            self._unload(alias)

        if record.local_path and os.path.exists(record.local_path):
            shutil.rmtree(record.local_path, ignore_errors=True)

        record.local_path = None
        record.status = ModelStatus.AVAILABLE
        record.downloaded_at = None
        logger.info(f"[HFManager] Model deleted: {alias}")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Return model manager statistics."""
        status_counts: Dict[str, int] = {}
        for record in self._registry.values():
            status_counts[record.status.value] = (
                status_counts.get(record.status.value, 0) + 1
            )

        total_inferences = sum(r.inference_count for r in self._registry.values())

        return {
            "total_models": len(self._registry),
            "loaded_models": len(self._loaded_order),
            "max_loaded": self.max_loaded_models,
            "status_counts": status_counts,
            "total_inferences": total_inferences,
            "currently_loaded": list(self._loaded_order),
        }
