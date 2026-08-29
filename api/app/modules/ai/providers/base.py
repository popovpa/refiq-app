from typing import Protocol

from app.modules.ai.generation import (
    GenerationResult,
    ImageGenerationRequest,
    StructuredGenerationRequest,
    TextGenerationRequest,
)


class TextGenerationProvider(Protocol):
    async def generate(self, request: TextGenerationRequest) -> GenerationResult: ...

    async def generate_structured(self, request: StructuredGenerationRequest) -> GenerationResult: ...


class ImageGenerationProvider(Protocol):
    async def generate(self, request: ImageGenerationRequest) -> GenerationResult: ...
