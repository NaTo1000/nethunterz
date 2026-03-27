"""Configuration and settings for the Grok 420 system."""

from __future__ import annotations

import os
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class HardwareClass(str, Enum):
    CPU = "cpu"
    GPU = "gpu"
    TPU = "tpu"
    QUANTUM = "quantum"


class SpeedMode(str, Enum):
    LOW_LATENCY = "low_latency"
    BALANCED = "balanced"
    HIGH_FIDELITY = "high_fidelity"


class ChainMode(str, Enum):
    PARALLEL = "parallel"
    SERIES = "series"
    HYBRID = "hybrid"


class DecisionMode(str, Enum):
    PRECISION = "precision"
    FUSION = "fusion"
    ADAPTIVE = "adaptive"


class ConductorConfig(BaseModel):
    """NayDoev1 Conductor configuration."""

    max_bots: int = Field(default=1000, ge=1, description="Maximum bot count")
    hardware_class: HardwareClass = Field(default=HardwareClass.CPU)
    inference_power: float = Field(default=0.8, ge=0.0, le=1.0)
    latency_vs_accuracy: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="0.0 = pure latency, 1.0 = pure accuracy",
    )
    handshake_timeout_s: float = Field(default=5.0, ge=0.1)
    resource_poll_interval_s: float = Field(default=1.0, ge=0.1)


class OrchestrationConfig(BaseModel):
    """Grok 420x1000 Orchestration Engine configuration."""

    cluster_count: int = Field(default=4, ge=1)
    health_check_interval_s: float = Field(default=10.0, ge=1.0)
    load_balance_strategy: str = Field(default="round_robin")
    auto_discovery: bool = Field(default=True)
    max_parallel_tasks: int = Field(default=100, ge=1)


class CHAiMERAConfig(BaseModel):
    """CHAiMERA chain system configuration."""

    speed_mode: SpeedMode = Field(default=SpeedMode.BALANCED)
    chain_mode: ChainMode = Field(default=ChainMode.HYBRID)
    layer_count: int = Field(default=3, ge=1, le=32)
    superconductor_threads: int = Field(default=4, ge=1)
    adaptive_learning_rate: float = Field(default=0.01, ge=0.0, le=1.0)


class TwinBrainConfig(BaseModel):
    """TWINBRAIN algorithm configuration."""

    sync_interval_ms: int = Field(default=100, ge=10)
    consensus_threshold: float = Field(default=0.6, ge=0.5, le=1.0)
    shared_memory_size_mb: int = Field(default=256, ge=1)
    max_divergence_retries: int = Field(default=3, ge=1)


class BlockchainConfig(BaseModel):
    """Blockchain memory system configuration."""

    shard_count: int = Field(default=16, ge=1)
    chain_count: int = Field(default=3, ge=1)
    block_size_kb: int = Field(default=64, ge=1)
    replication_factor: int = Field(default=3, ge=1)
    cross_chain_sync: bool = Field(default=True)


class SecurityConfig(BaseModel):
    """Security and monitoring configuration."""

    encryption_algorithm: str = Field(default="AES-256-GCM")
    audit_trail_enabled: bool = Field(default=True)
    integrity_check_interval_s: float = Field(default=30.0, ge=1.0)
    alert_webhook_url: str = Field(default="")

    @field_validator("encryption_algorithm")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        allowed = {"AES-256-GCM", "ChaCha20-Poly1305"}
        if v not in allowed:
            raise ValueError(f"algorithm must be one of {allowed}")
        return v


class HuggingFaceConfig(BaseModel):
    """Hugging Face integration configuration."""

    cache_dir: str = Field(default="/tmp/grok420_models")
    db_path: str = Field(default="/tmp/grok420_models.json")
    max_cached_models: int = Field(default=10, ge=1)
    default_revision: str = Field(default="main")


class Grok420Settings(BaseModel):
    """Top-level settings aggregating all sub-configurations."""

    conductor: ConductorConfig = Field(default_factory=ConductorConfig)
    orchestration: OrchestrationConfig = Field(
        default_factory=OrchestrationConfig
    )
    chaimera: CHAiMERAConfig = Field(default_factory=CHAiMERAConfig)
    twinbrain: TwinBrainConfig = Field(default_factory=TwinBrainConfig)
    blockchain: BlockchainConfig = Field(default_factory=BlockchainConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    huggingface: HuggingFaceConfig = Field(default_factory=HuggingFaceConfig)

    @classmethod
    def from_env(cls) -> "Grok420Settings":
        """Build settings from environment variables with sane defaults."""
        overrides: dict[str, Any] = {}
        if os.environ.get("GROK420_MAX_BOTS"):
            overrides["conductor"] = ConductorConfig(
                max_bots=int(os.environ["GROK420_MAX_BOTS"])
            )
        if os.environ.get("GROK420_SPEED_MODE"):
            overrides["chaimera"] = CHAiMERAConfig(
                speed_mode=SpeedMode(os.environ["GROK420_SPEED_MODE"])
            )
        return cls(**overrides)
