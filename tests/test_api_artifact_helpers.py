from types import SimpleNamespace

from backend.helpers.artifact_helpers import artifact_payload


class FakeArtifact:
    def model_dump(self, mode="json"):
        return {"artifact_type": "report", "title": "Board Update", "mode": mode}


def test_artifact_payload_adds_available_formats():
    payload = artifact_payload(
        FakeArtifact(),
        artifact_export_formats=lambda artifact: ["md", "pptx"],
    )

    assert payload["artifact_type"] == "report"
    assert payload["title"] == "Board Update"
    assert payload["available_formats"] == ["md", "pptx"]


def test_artifact_payload_preserves_model_dump_mode_argument():
    calls = []

    class TracingArtifact:
        def model_dump(self, mode="json"):
            calls.append(mode)
            return {"artifact_type": "deck"}

    payload = artifact_payload(
        TracingArtifact(),
        artifact_export_formats=lambda artifact: ["pptx"],
    )

    assert payload["available_formats"] == ["pptx"]
    assert calls == ["json"]
