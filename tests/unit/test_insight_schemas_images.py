"""Strict insights boundary and secure chart-image tests."""

from __future__ import annotations

import base64
import hashlib
from io import BytesIO

import pytest
from PIL import Image, PngImagePlugin
from pydantic import ValidationError

from cepe_fynsp.insights.images import InvalidChartImageError, validate_chart_image
from cepe_fynsp.insights.schemas import (
    ChartImageInput,
    InsightAiMetadata,
    InsightRequest,
    InsightResponse,
)


def _png_input(*, width: int = 20, height: int = 10, metadata: bool = False) -> ChartImageInput:
    output = BytesIO()
    info = None
    if metadata:
        info = PngImagePlugin.PngInfo()
        info.add_text("untrusted", "metadata must be stripped")
    Image.new("RGB", (width, height), "white").save(output, format="PNG", pnginfo=info)
    content = output.getvalue()
    return ChartImageInput(
        mime_type="image/png",
        data_base64=base64.b64encode(content).decode("ascii"),
        width=width,
        height=height,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "dashboard_id": "dashboard_01_pit_production",
        "question_id": "q1",
        "chart_id": "dashboard_01_pit_production_q1",
        "action": "summarize",
        "active_filter_state": {"fiscal_year": ["FY2029"]},
        "query": None,
        "chart_image": None,
        "client_metadata": {
            "image_capture_status": "unavailable",
            "device_pixel_ratio": 1,
        },
    }
    payload.update(overrides)
    return payload


def test_request_schema_rejects_unknown_fields_paths_and_query_bypass() -> None:
    with pytest.raises(ValidationError):
        InsightRequest.model_validate({**_request(), "client_aggregate_data": []})
    with pytest.raises(ValidationError):
        InsightRequest.model_validate(_request(dashboard_id="../dashboard_01_pit_production"))
    with pytest.raises(ValidationError):
        InsightRequest.model_validate(_request(query="override"))


def test_custom_query_preserves_multiline_and_rejects_blank_or_oversized() -> None:
    request = InsightRequest.model_validate(
        _request(action="custom_query", query="First line\nSecond line")
    )
    assert request.query == "First line\nSecond line"
    with pytest.raises(ValidationError, match="nonblank"):
        InsightRequest.model_validate(_request(action="custom_query", query="  \n "))
    with pytest.raises(ValidationError):
        InsightRequest.model_validate(_request(action="custom_query", query="x" * 2001))


def test_image_rejects_mime_base64_hash_dimensions_and_size() -> None:
    valid = _png_input()
    with pytest.raises(ValidationError):
        ChartImageInput.model_validate({**valid.model_dump(), "mime_type": "image/jpeg"})
    with pytest.raises(InvalidChartImageError, match="base64"):
        validate_chart_image(valid.model_copy(update={"data_base64": "not-base64"}))
    with pytest.raises(InvalidChartImageError, match="hash"):
        validate_chart_image(valid.model_copy(update={"sha256": "0" * 64}))
    with pytest.raises(InvalidChartImageError, match="dimensions"):
        validate_chart_image(valid.model_copy(update={"width": valid.width + 1}))
    with pytest.raises(ValidationError):
        ChartImageInput.model_validate({**valid.model_dump(), "width": 2401})


def test_image_is_reencoded_and_metadata_is_stripped() -> None:
    cleaned = validate_chart_image(_png_input(metadata=True))
    assert cleaned.mime_type == "image/png"
    assert hashlib.sha256(cleaned.content).hexdigest() == cleaned.sha256
    with Image.open(BytesIO(cleaned.content)) as image:
        assert "untrusted" not in image.info


def test_response_schema_rejects_unexpected_or_uncited_answered_output() -> None:
    metadata = InsightAiMetadata(model="synthetic", prompt_version="test", request_id="request-id")
    with pytest.raises(ValidationError, match="evidence citations"):
        InsightResponse.model_validate(
            {
                "schema_version": "1.0",
                "status": "answered",
                "answer": "Plausible but uncited.",
                "ai_metadata": metadata.model_dump(),
            }
        )
    with pytest.raises(ValidationError):
        InsightResponse.model_validate(
            {
                "schema_version": "1.0",
                "status": "unavailable",
                "unexpected": True,
                "ai_metadata": metadata.model_dump(),
            }
        )
