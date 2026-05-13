import json

import pytest

from backend.delivery_templates import (
    install_delivery_template_manifest_payload,
    list_delivery_template_catalog,
    load_delivery_template_manifest_report,
    uninstall_delivery_template_manifest_payload,
    validate_delivery_template_selection,
)


def test_delivery_template_catalog_lists_builtin_templates():
    payload = list_delivery_template_catalog(template_dirs=[])

    assert payload["summary"] == {
        "total": 3,
        "builtin": 3,
        "manifest": 0,
        "report": 2,
        "deck": 1,
    }
    assert [template["id"] for template in payload["templates"]] == [
        "executive_report",
        "research_brief",
        "board_deck",
    ]


def test_validate_delivery_template_selection_accepts_matching_artifact_type():
    template = validate_delivery_template_selection(
        "board_deck",
        artifact_type="deck",
        template_dirs=[],
    )

    assert template is not None
    assert template["id"] == "board_deck"
    assert template["artifact_type"] == "deck"


def test_validate_delivery_template_selection_rejects_unknown_or_wrong_type():
    with pytest.raises(ValueError, match="Unknown delivery template"):
        validate_delivery_template_selection(
            "missing_template",
            artifact_type="report",
            template_dirs=[],
        )

    with pytest.raises(ValueError, match="not report"):
        validate_delivery_template_selection(
            "board_deck",
            artifact_type="report",
            template_dirs=[],
        )


def test_delivery_template_manifest_loader_reports_invalid_and_duplicates(tmp_path):
    template_dir = tmp_path / "delivery_templates"
    template_dir.mkdir()
    valid_payload = {
        "id": "sales_readout",
        "name": "Sales Readout",
        "description": "Sales team readout deck.",
        "artifact_type": "deck",
        "category": "sales",
        "tags": ["sales", "deck"],
        "target_format": "pptx",
    }
    (template_dir / "a.json").write_text(json.dumps(valid_payload), encoding="utf-8")
    (template_dir / "b.json").write_text(json.dumps(valid_payload), encoding="utf-8")
    (template_dir / "bad.json").write_text(
        json.dumps({"id": "bad", "artifact_type": "report", "tags": []}),
        encoding="utf-8",
    )

    report = load_delivery_template_manifest_report([template_dir])

    assert report.scanned_count == 3
    assert [template.id for template in report.templates] == ["sales_readout"]
    assert [issue.code for issue in report.issues] == [
        "duplicate_id",
        "invalid_manifest",
    ]


def test_delivery_template_catalog_merges_manifest_templates(tmp_path):
    template_dir = tmp_path / "delivery_templates"
    template_dir.mkdir()
    (template_dir / "custom-report.json").write_text(
        json.dumps(
            {
                "id": "custom_report",
                "name": "Custom Report",
                "description": "Custom report manifest.",
                "artifact_type": "report",
                "category": "custom",
                "tags": ["custom"],
                "target_format": "markdown",
                "metadata": {"unsafe": {"ignored": True}, "owner": "ops"},
            }
        ),
        encoding="utf-8",
    )

    payload = list_delivery_template_catalog(template_dirs=[template_dir])

    assert payload["summary"]["total"] == 4
    assert payload["summary"]["manifest"] == 1
    assert payload["manifests"]["loaded_count"] == 1
    assert payload["templates"][-1]["id"] == "custom_report"
    assert payload["templates"][-1]["metadata"]["source"] == "template_manifest"
    assert "unsafe" not in payload["templates"][-1]["metadata"]


def test_install_delivery_template_manifest_persists_sanitized_manifest(tmp_path):
    template_dir = tmp_path / "delivery_templates"

    payload = install_delivery_template_manifest_payload(
        {
            "id": "sales_readout",
            "version": "1.0.0",
            "name": "Sales Readout",
            "description": "Sales team readout deck.",
            "artifact_type": "deck",
            "category": "sales",
            "tags": ["sales", "deck"],
            "target_format": "pptx",
            "preview": "Pipeline -> Risks -> Actions",
            "suggested_options": {"target_slide_count": 6},
            "metadata": {"owner": "sales", "source": "spoofed", "unsafe": {"ignored": True}},
        },
        template_dirs=[template_dir],
    )

    saved = json.loads((template_dir / "sales_readout.json").read_text(encoding="utf-8"))

    assert payload["installed"]["id"] == "sales_readout"
    assert payload["installed"]["executed_template_code"] is False
    assert payload["summary"]["manifest"] == 1
    assert saved == {
        "artifact_type": "deck",
        "category": "sales",
        "description": "Sales team readout deck.",
        "enabled": True,
        "id": "sales_readout",
        "metadata": {"owner": "sales"},
        "name": "Sales Readout",
        "preview": "Pipeline -> Risks -> Actions",
        "suggested_options": {"target_slide_count": 6},
        "tags": ["sales", "deck"],
        "target_format": "pptx",
        "version": "1.0.0",
    }


def test_uninstall_delivery_template_manifest_removes_persisted_manifest(tmp_path):
    template_dir = tmp_path / "delivery_templates"
    install_delivery_template_manifest_payload(
        {
            "id": "sales_readout",
            "name": "Sales Readout",
            "description": "Sales team readout deck.",
            "artifact_type": "deck",
            "category": "sales",
            "tags": ["sales", "deck"],
            "target_format": "pptx",
        },
        template_dirs=[template_dir],
    )

    payload = uninstall_delivery_template_manifest_payload(
        "sales_readout",
        template_dirs=[template_dir],
    )

    assert payload["uninstalled"]["id"] == "sales_readout"
    assert payload["uninstalled"]["deleted_manifest"] is True
    assert not (template_dir / "sales_readout.json").exists()
    assert payload["summary"]["manifest"] == 0


def test_delivery_template_manifest_management_rejects_builtin_invalid_and_missing(tmp_path):
    template_dir = tmp_path / "delivery_templates"

    with pytest.raises(ValueError, match="conflicts with built-in"):
        install_delivery_template_manifest_payload(
            {
                "id": "board_deck",
                "name": "Board Deck Override",
                "description": "Conflicting deck.",
                "artifact_type": "deck",
                "tags": ["deck"],
                "target_format": "pptx",
            },
            template_dirs=[template_dir],
        )

    with pytest.raises(ValueError, match="Delivery template id"):
        uninstall_delivery_template_manifest_payload("bad template", template_dirs=[template_dir])

    with pytest.raises(ValueError, match="not found"):
        uninstall_delivery_template_manifest_payload("missing_template", template_dirs=[template_dir])
