"""Local model policy for the LXRION development runtime."""
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Capability(str, Enum):
    CHAT = "chat"
    CODING = "coding"
    REASONING = "reasoning"
    EMBEDDING = "embedding"
    VISION = "vision"


@dataclass(frozen=True)
class Model:
    tag: str
    capabilities: tuple[Capability, ...]


# Ordered by preference within each role. Smaller models reduce cold-load cost
# on the supported HDD-backed host. A capability is policy, not a benchmark.
MODELS = (
    Model("llama3.2:3b", (Capability.CHAT,)),
    Model("qwen2.5-coder:1.5b", (Capability.CODING,)),
    Model("qwen3:1.7b", (Capability.CHAT, Capability.REASONING)),
    Model("nomic-embed-text:latest", (Capability.EMBEDDING,)),
    Model("qwen2.5-coder:3b", (Capability.CODING,)),
    Model("qwen3:4b", (Capability.CHAT, Capability.REASONING)),
    Model("gemma3:4b", (Capability.CHAT, Capability.VISION)),
    Model("qwen2.5-coder:7b", (Capability.CODING,)),
    Model("deepseek-r1:7b", (Capability.REASONING,)),
)


def select_model(capability: Capability, installed: Iterable[str]) -> Model | None:
    available = set(installed)
    return next(
        (model for model in MODELS if capability in model.capabilities and model.tag in available),
        None,
    )
