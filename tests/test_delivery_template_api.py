from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.delivery_templates import (
    install_delivery_template_manifest_payload,
    uninstall_delivery_template_manifest_payload,
)
from backend.routes.delivery_template_routes import build_delivery_template_router
from backend.schemas.api_models import DeliveryTemplateCatalogResponse


def test_delivery_template_catalog_endpoint_returns_stable_payload():
    app = FastAPI()
    audit_events: list[tuple[str, str]] = []

    app.include_router(
        build_delivery_template_router(
            delivery_template_catalog_response_model=DeliveryTemplateCatalogResponse,
            list_delivery_template_catalog=lambda: {
                "templates": [
                    {
                        "id": "executive_report",
                        "name": "Executive Report",
                        "description": "Executive summary.",
                        "artifact_type": "report",
                        "category": "business",
                        "tags": ["executive"],
                        "target_format": "markdown",
                        "preview": "Summary",
                        "suggested_options": {},
                        "metadata": {"source": "builtin"},
                    }
                ],
                "summary": {
                    "total": 1,
                    "builtin": 1,
                    "manifest": 0,
                    "report": 1,
                    "deck": 0,
                },
                "manifests": {
                    "enabled": True,
                    "directory_count": 1,
                    "scanned_count": 0,
                    "loaded_count": 0,
                    "issue_count": 0,
                    "issues": [],
                },
            },
            install_delivery_template_manifest_payload=lambda manifest: {
                "templates": [],
                "summary": {"total": 0, "builtin": 0, "manifest": 0, "report": 0, "deck": 0},
                "manifests": {"enabled": True, "directory_count": 1},
                "installed": {
                    "id": str(manifest.get("id") or ""),
                    "manifest_path": "unused",
                    "executed_template_code": False,
                },
            },
            uninstall_delivery_template_manifest_payload=lambda template_id: {
                "templates": [],
                "summary": {"total": 0, "builtin": 0, "manifest": 0, "report": 0, "deck": 0},
                "manifests": {"enabled": True, "directory_count": 1},
                "uninstalled": {
                    "id": template_id,
                    "manifest_path": "unused",
                    "deleted_manifest": True,
                    "existed": True,
                },
            },
            require_remote_viewer=lambda request: {"role": "viewer"},
            require_remote_admin=lambda request: {"role": "admin"},
            audit_security_event=lambda action, request, details="": audit_events.append(
                (action, details)
            ),
        )
    )

    response = TestClient(app).get("/api/delivery-templates/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total"] == 1
    assert payload["templates"][0]["id"] == "executive_report"
    assert audit_events == [("get_delivery_template_catalog", "total=1 manifest=0")]


def test_delivery_template_install_and_uninstall_endpoints_manage_manifests(tmp_path):
    app = FastAPI()
    audit_events: list[tuple[str, str]] = []
    template_dir = tmp_path / "delivery_templates"

    app.include_router(
        build_delivery_template_router(
            delivery_template_catalog_response_model=DeliveryTemplateCatalogResponse,
            list_delivery_template_catalog=lambda: {
                "templates": [],
                "summary": {},
                "manifests": {},
            },
            install_delivery_template_manifest_payload=lambda manifest: install_delivery_template_manifest_payload(
                manifest,
                template_dirs=[template_dir],
            ),
            uninstall_delivery_template_manifest_payload=lambda template_id: uninstall_delivery_template_manifest_payload(
                template_id,
                template_dirs=[template_dir],
            ),
            require_remote_viewer=lambda request: {"role": "viewer"},
            require_remote_admin=lambda request: {"role": "admin"},
            audit_security_event=lambda action, request, details="": audit_events.append(
                (action, details)
            ),
        )
    )

    install_response = TestClient(app).post(
        "/api/delivery-templates/install",
        json={
            "manifest": {
                "id": "sales_readout",
                "name": "Sales Readout",
                "description": "Sales team readout deck.",
                "artifact_type": "deck",
                "category": "sales",
                "tags": ["sales", "deck"],
                "target_format": "pptx",
            },
        },
    )
    uninstall_response = TestClient(app).delete("/api/delivery-templates/sales_readout")

    assert install_response.status_code == 200
    assert install_response.json()["installed"]["id"] == "sales_readout"
    assert install_response.json()["installed"]["executed_template_code"] is False
    assert uninstall_response.status_code == 200
    assert uninstall_response.json()["uninstalled"]["id"] == "sales_readout"
    assert not (template_dir / "sales_readout.json").exists()
    assert audit_events == [
        ("install_delivery_template_manifest", "id=sales_readout total=4"),
        ("uninstall_delivery_template_manifest", "id=sales_readout total=3"),
    ]


def test_delivery_template_install_endpoint_rejects_invalid_manifest(tmp_path):
    app = FastAPI()

    app.include_router(
        build_delivery_template_router(
            delivery_template_catalog_response_model=DeliveryTemplateCatalogResponse,
            list_delivery_template_catalog=lambda: {"templates": [], "summary": {}, "manifests": {}},
            install_delivery_template_manifest_payload=lambda manifest: install_delivery_template_manifest_payload(
                manifest,
                template_dirs=[tmp_path / "delivery_templates"],
            ),
            uninstall_delivery_template_manifest_payload=lambda template_id: uninstall_delivery_template_manifest_payload(
                template_id,
                template_dirs=[tmp_path / "delivery_templates"],
            ),
            require_remote_viewer=lambda request: {"role": "viewer"},
            require_remote_admin=lambda request: {"role": "admin"},
            audit_security_event=lambda *args, **kwargs: None,
        )
    )

    response = TestClient(app).post(
        "/api/delivery-templates/install",
        json={"manifest": {"id": "bad template", "artifact_type": "report", "tags": []}},
    )

    assert response.status_code == 400
    assert "Delivery template id" in response.json()["detail"]
