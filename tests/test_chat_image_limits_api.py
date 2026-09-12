from fastapi.testclient import TestClient

import backend.api_server as api_server


def _image_payload(index: int) -> dict[str, str]:
    return {
        "name": f"image-{index}.png",
        "media_type": "image/png",
        "data_url": "data:image/png;base64,YQ==",
    }


def test_chat_endpoint_rejects_images_above_configured_count(monkeypatch):
    monkeypatch.setattr(api_server, "CHAT_IMAGE_MAX_COUNT", 4)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/chat/single",
        json={
            "session_id": "image-limit-test",
            "message": "describe these images",
            "images": [_image_payload(index) for index in range(5)],
            "panel_config": {
                "panel_id": "panel-1",
                "provider": "ollama",
                "model": "qwen2.5-vl:7b",
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "每条消息最多只能附加 4 张图片。"
