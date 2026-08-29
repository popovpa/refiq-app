from __future__ import annotations

import uuid
from typing import Any

from app.modules.ai.generation import (
    GeneratedImage,
    GenerationResult,
    ImageGenerationRequest,
    ProviderUsage,
    StructuredGenerationRequest,
    TextGenerationRequest,
)


MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeTextGenerationProvider:
    def __init__(self) -> None:
        self.structured_responses: list[dict[str, Any]] = []
        self.text_responses: list[str] = []
        self.error: Exception | None = None
        self.calls: list[StructuredGenerationRequest | TextGenerationRequest] = []

    def queue_structured(self, data: dict[str, Any]) -> None:
        self.structured_responses.append(data)

    def fail_with(self, error: Exception) -> None:
        self.error = error

    def reset(self) -> None:
        self.structured_responses.clear()
        self.text_responses.clear()
        self.error = None
        self.calls.clear()

    async def generate(self, request: TextGenerationRequest) -> GenerationResult:
        self.calls.append(request)
        if self.error:
            raise self.error
        content = self.text_responses.pop(0) if self.text_responses else "ok"
        return self._result(content=content, structured=None)

    async def generate_structured(self, request: StructuredGenerationRequest) -> GenerationResult:
        self.calls.append(request)
        if self.error:
            raise self.error
        data = self.structured_responses.pop(0) if self.structured_responses else {}
        return self._result(content=None, structured=data)

    def _result(self, *, content: str | None, structured: dict[str, Any] | None) -> GenerationResult:
        return GenerationResult(
            generation_id=str(uuid.uuid4()),
            provider="fake",
            model="fake-model",
            structured_data=structured,
            content=content,
            usage=ProviderUsage(
                input_tokens=11,
                output_tokens=7,
                total_tokens=18,
                cached_input_tokens=2,
                reasoning_tokens=0,
                provider_request_id="fake-req",
                metadata={"prompt_tokens": 11, "completion_tokens": 7},
            ),
            provider_metadata={"id": "fake-req", "finish_reason": "stop"},
            retry_count=0,
        )


class FakeImageGenerationProvider:
    def __init__(self) -> None:
        self.images: list[bytes] = []
        self.error: Exception | None = None
        self.calls: list[ImageGenerationRequest] = []

    def queue_image(self, data: bytes | None = None) -> None:
        self.images.append(data if data is not None else MIN_PNG)

    def fail_with(self, error: Exception) -> None:
        self.error = error

    def reset(self) -> None:
        self.images.clear()
        self.error = None
        self.calls.clear()

    async def generate(self, request: ImageGenerationRequest) -> GenerationResult:
        self.calls.append(request)
        if self.error:
            raise self.error
        payload = self.images.pop(0) if self.images else MIN_PNG
        return GenerationResult(
            generation_id=str(uuid.uuid4()),
            provider="fake",
            model="fake-image",
            structured_data=None,
            content=None,
            usage=ProviderUsage(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                provider_request_id="fake-img-req",
                metadata={"n": request.n},
            ),
            provider_metadata={"id": "fake-img-req", "finish_reason": "stop"},
            retry_count=0,
            images=[
                GeneratedImage(
                    data=payload,
                    mime_type="image/png",
                    width=1024,
                    height=1024,
                    revised_prompt=request.prompt,
                )
            ],
        )
