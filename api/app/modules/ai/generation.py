from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    provider_request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StructuredGenerationRequest:
    system_prompt: str
    user_prompt: str
    schema: dict[str, Any]
    schema_name: str
    operation: str
    prompt_version: str
    model: str | None = None
    reasoning_effort: str | None = None


@dataclass(frozen=True)
class TextGenerationRequest:
    system_prompt: str
    user_prompt: str
    operation: str
    prompt_version: str


@dataclass(frozen=True)
class ImageGenerationRequest:
    prompt: str
    aspect_ratio: str
    image_format: str
    operation: str
    prompt_version: str
    n: int = 1


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    mime_type: str
    width: int | None = None
    height: int | None = None
    revised_prompt: str | None = None


@dataclass(frozen=True)
class GenerationResult:
    generation_id: str
    provider: str
    model: str
    structured_data: dict[str, Any] | None
    content: str | None
    usage: ProviderUsage
    provider_metadata: dict[str, Any]
    retry_count: int = 0
    images: list[GeneratedImage] = field(default_factory=list)
