import json

import pytest
from types import SimpleNamespace

from backend.helpers.security_helpers import (
    auth_token_is_weak,
    auth_token_preview,
    build_security_audit_aggregate_report_payload,
    build_security_audit_archive_policy_payload,
    build_security_audit_siem_export_payload,
    ceil_seconds,
    content_hash,
    hash_secret,
    normalize_auth_role,
    normalize_sso_config_update,
    pkce_code_challenge,
    role_rank,
    safe_epoch_seconds,
    sanitize_log_value,
    sanitize_request_path,
    security_audit_detail_value,
    security_audit_event_org,
    security_audit_event_tenant,
    security_audit_event_to_payload,
    security_audit_redacted_details,
    security_audit_siem_event_payload,
    filter_security_audit_events,
    share_link_audit_payload,
    sso_callback_url_for_mode,
    sso_session_token_hash,
    token_fingerprint,
    token_preview,
)


def _normalize_auth_role(role, *, default="viewer"):
    normalized = str(role or "").strip().lower()
    return normalized if normalized in {"viewer", "editor", "admin"} else default


def test_hash_secret_returns_short_digest_and_no_key_sentinel():
    assert hash_secret("") == "no-key"
    assert hash_secret("secret") == "2bb80d537b1d"


def test_token_fingerprint_normalizes_and_redacts_empty_values():
    assert token_fingerprint("") == "empty"
    assert token_fingerprint(" token-value ") == "e6c02a5742ea"


def test_token_preview_preserves_short_values_and_truncates_long_values():
    assert token_preview("short") == "short"
    assert token_preview("long-token-value") == "long-t...alue"


def test_auth_token_preview_masks_short_values_and_truncates_long_values():
    assert auth_token_preview("") == "empty"
    assert auth_token_preview("abcd") == "****"
    assert auth_token_preview("abcdef") == "ab...ef"
    assert auth_token_preview("long-token-value") == "long...ue"


def test_normalize_auth_role_and_role_rank_use_configured_fallback():
    role_ranks = {"viewer": 1, "editor": 2, "admin": 3}

    assert normalize_auth_role(" ADMIN ", role_ranks=role_ranks) == "admin"
    assert (
        normalize_auth_role("owner", role_ranks=role_ranks, default="editor")
        == "editor"
    )
    assert (
        role_rank(
            "owner",
            role_ranks=role_ranks,
            normalize_role=lambda value: normalize_auth_role(
                value, role_ranks=role_ranks, default="viewer"
            ),
        )
        == 1
    )


def test_sanitize_log_value_strips_control_whitespace_and_truncates():
    assert sanitize_log_value(" a\n\t  b ") == "a b"
    assert sanitize_log_value("abcdef", max_length=5) == "ab..."


def test_sanitize_request_path_redacts_share_tokens():
    assert sanitize_request_path("") == "/"
    assert sanitize_request_path(" /api/share-links/raw-token ") == (
        "/api/share-links/<token>"
    )
    assert sanitize_request_path("/shared/raw-token") == "/shared/<token>"
    assert sanitize_request_path("/api/security/status") == "/api/security/status"


def test_auth_token_is_weak_uses_minimum_length():
    assert auth_token_is_weak("short", min_length=8) is True
    assert auth_token_is_weak("long-enough", min_length=8) is False


def test_ceil_seconds_matches_rate_limit_header_rounding():
    assert ceil_seconds(-1) == 0
    assert ceil_seconds(0) == 0
    assert ceil_seconds(0.1) == 1
    assert ceil_seconds(2.0) == 2
    assert ceil_seconds(2.1) == 3


def test_content_hash_handles_empty_string_plain_text_and_stable_json():
    assert content_hash(None) == ""
    assert content_hash("") == ""
    assert (
        content_hash("plain-text")
        == "2fee8e92250845894bd3dc8d0c0a1ed8a25416b9d43718089d6b402f67b3609d"
    )
    assert (
        content_hash({"b": 2, "a": 1})
        == "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )


def test_normalize_sso_config_update_accepts_supported_providers():
    assert (
        normalize_sso_config_update(
            "provider",
            " OIDC ",
            normalize_auth_role=_normalize_auth_role,
        )
        == "oidc"
    )
    assert (
        normalize_sso_config_update(
            "provider",
            "",
            normalize_auth_role=_normalize_auth_role,
        )
        == "none"
    )


def test_normalize_sso_config_update_rejects_unsupported_provider():
    with pytest.raises(ValueError) as exc_info:
        normalize_sso_config_update(
            "provider",
            "saml",
            normalize_auth_role=_normalize_auth_role,
        )

    assert str(exc_info.value) == "SSO provider must be none or oidc"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("300", "300"),
        (604800, "604800"),
    ],
)
def test_normalize_sso_config_update_accepts_session_ttl_bounds(value, expected):
    assert (
        normalize_sso_config_update(
            "session_ttl_seconds",
            value,
            normalize_auth_role=_normalize_auth_role,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("abc", "SSO session TTL must be an integer number of seconds"),
        (299, "SSO session TTL must be between 300 and 604800 seconds"),
        (604801, "SSO session TTL must be between 300 and 604800 seconds"),
    ],
)
def test_normalize_sso_config_update_rejects_invalid_session_ttl(value, message):
    with pytest.raises(ValueError) as exc_info:
        normalize_sso_config_update(
            "session_ttl_seconds",
            value,
            normalize_auth_role=_normalize_auth_role,
        )

    assert str(exc_info.value) == message


def test_normalize_sso_config_update_normalizes_default_role():
    assert (
        normalize_sso_config_update(
            "default_role",
            " EDITOR ",
            default_auth_role="viewer",
            normalize_auth_role=_normalize_auth_role,
        )
        == "editor"
    )
    assert (
        normalize_sso_config_update(
            "default_role",
            "owner",
            default_auth_role="viewer",
            normalize_auth_role=_normalize_auth_role,
        )
        == "viewer"
    )


def test_sso_callback_url_for_mode_appends_fragment_response_mode_only_when_requested():
    callback_url = "http://testserver/api/auth/sso/callback"

    assert (
        sso_callback_url_for_mode(callback_url, "fragment")
        == "http://testserver/api/auth/sso/callback?response_mode=fragment"
    )
    assert sso_callback_url_for_mode(callback_url, "") == callback_url


def test_pkce_code_challenge_matches_rfc7636_example():
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

    assert (
        pkce_code_challenge(verifier)
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


def test_sso_session_token_hash_normalizes_whitespace():
    assert sso_session_token_hash(" session-token ") == sso_session_token_hash(
        "session-token"
    )
    assert (
        sso_session_token_hash("session-token")
        == "c101e911469c969171040b50d70543313cf968fdef5bacc780776f8fb399ab36"
    )


def test_share_link_audit_payload_redacts_token_and_reports_active_state():
    record = SimpleNamespace(
        resource_type=" session ",
        resource_id=" session-1 ",
        share_token="super-secret-share-token",
        created_at=100,
        expires_at=200,
        revoked_at=None,
        created_by_ip=" 127.0.0.1 ",
        created_user_agent=" test-agent ",
        access_count="2",
        last_accessed_at=150,
        last_accessed_ip=" 127.0.0.2 ",
        last_accessed_user_agent=" browser ",
    )

    payload = share_link_audit_payload(record, current_time=150)

    assert payload["resource_type"] == "session"
    assert payload["resource_id"] == "session-1"
    assert payload["is_active"] is True
    assert payload["access_count"] == 2
    assert payload["share_token_preview"] == "super-...oken"
    assert payload["share_token_fingerprint"]
    assert "super-secret-share-token" not in payload["share_token_fingerprint"]


def test_share_link_audit_payload_marks_revoked_records_inactive():
    record = SimpleNamespace(
        share_token="secret-token",
        expires_at=200,
        revoked_at=120,
    )

    payload = share_link_audit_payload(record, current_time=150)

    assert payload["is_active"] is False
    assert payload["revoked_at"] == 120.0
    assert payload["last_accessed_at"] is None


def test_security_audit_detail_value_extracts_matching_key_names():
    details = "tenant=tenant-a org_id=org-a token=raw-token"

    assert security_audit_detail_value(details, "tenant_id", "tenant") == "tenant-a"
    assert security_audit_detail_value(details, "org") == ""
    assert security_audit_detail_value(details, "org_id", "organization_id") == "org-a"


def test_security_audit_redacted_details_removes_common_secret_patterns():
    details = (
        "Authorization=Bearer abc.def token=raw-token "
        "api_key=raw-key CLIENT_SECRET=raw-secret password=raw-pass\n"
        "safe=value Bearer standalone-token"
    )

    redacted = security_audit_redacted_details(details)

    assert "raw-token" not in redacted
    assert "raw-key" not in redacted
    assert "raw-secret" not in redacted
    assert "raw-pass" not in redacted
    assert "standalone-token" not in redacted
    assert "token=<redacted>" in redacted
    assert "api_key=<redacted>" in redacted
    assert "CLIENT_SECRET=<redacted>" in redacted
    assert "password=<redacted>" in redacted
    assert "Bearer <redacted>" in redacted
    assert "\n" not in redacted
    assert "safe=value" in redacted


def test_safe_epoch_seconds_accepts_non_negative_numbers_only():
    assert safe_epoch_seconds("12.5") == 12.5
    assert safe_epoch_seconds(0) == 0.0
    assert safe_epoch_seconds(-1) is None
    assert safe_epoch_seconds("not-a-number") is None


def test_security_audit_event_to_payload_preserves_optional_tenant_fields():
    record = SimpleNamespace(
        timestamp=10,
        request_id="req-1",
        action="get_auth_tokens",
        result="ok",
        ip="203.0.113.1",
        is_local=False,
        auth_mode="bearer",
        auth_source="test",
        user_id="admin",
        user_role="admin",
        details="tenant=tenant-a",
        tenant_id="tenant-a",
        org_id="org-a",
        legal_hold=True,
    )

    payload = security_audit_event_to_payload(record)

    assert payload["tenant_id"] == "tenant-a"
    assert payload["org_id"] == "org-a"
    assert payload["legal_hold"] is True


def test_security_audit_siem_event_payload_redacts_and_falls_back_to_detail_tenant():
    event = {
        "timestamp": "20",
        "request_id": " req-siem ",
        "action": "upsert_resource_grant",
        "result": "ok",
        "user_id": " alice ",
        "user_role": "admin",
        "details": "tenant=tenant-a org=org-a token=raw-token",
        "ip": "203.0.113.2",
        "auth_mode": "bearer",
        "auth_source": "test",
        "legal_hold": True,
    }

    payload = security_audit_siem_event_payload(event)

    assert payload["time"] == 20.0
    assert payload["category"] == "access"
    assert payload["tenant"] == "tenant-a"
    assert payload["org"] == "org-a"
    assert payload["legal_hold"] is True
    assert "raw-token" not in payload["details"]
    assert "token=<redacted>" in payload["details"]


def test_build_security_audit_siem_export_payload_formats_json_envelope():
    events = [
        {
            "timestamp": "20",
            "request_id": " req-siem ",
            "action": "upsert_resource_grant",
            "result": "ok",
            "user_id": " alice ",
            "details": (
                "tenant=tenant-a org=org-a "
                "token=raw-token client_secret=raw-secret"
            ),
        }
    ]
    filters = {"action": "upsert_resource_grant", "since": 10.0}

    payload = build_security_audit_siem_export_payload(
        events,
        format="json",
        limit=50,
        filters=filters,
    )

    assert payload["format"] == "json"
    assert payload["content_type"] == "application/json"
    assert payload["content"] == ""
    assert payload["total"] == 1
    assert payload["limit"] == 50
    assert payload["filters"] == filters
    assert payload["events"][0]["request_id"] == "req-siem"
    assert payload["events"][0]["tenant"] == "tenant-a"
    assert payload["events"][0]["org"] == "org-a"
    assert "raw-token" not in payload["events"][0]["details"]
    assert "raw-secret" not in payload["events"][0]["details"]


def test_build_security_audit_siem_export_payload_formats_ndjson_and_fallback():
    events = [
        {
            "timestamp": 30,
            "action": "unknown_custom_action",
            "result": "ok",
            "details": "Authorization: Bearer raw-token",
        }
    ]

    ndjson_payload = build_security_audit_siem_export_payload(
        events,
        format="ndjson",
        limit=1,
    )

    assert ndjson_payload["format"] == "ndjson"
    assert ndjson_payload["content_type"] == "application/x-ndjson"
    assert ndjson_payload["events"] == []
    lines = [line for line in ndjson_payload["content"].splitlines() if line]
    assert len(lines) == 1
    exported = json.loads(lines[0])
    assert exported["category"] == "uncategorized"
    assert "raw-token" not in exported["details"]
    assert "Bearer <redacted>" in exported["details"]

    fallback_payload = build_security_audit_siem_export_payload(
        events,
        format="xml",
        limit=1,
    )

    assert fallback_payload["format"] == "json"
    assert fallback_payload["content_type"] == "application/json"
    assert fallback_payload["events"][0]["category"] == "uncategorized"


def test_build_security_audit_archive_policy_payload_uses_cutoff_and_legal_hold():
    events = [
        {
            "timestamp": 100,
            "request_id": "req-delete",
            "action": "upsert_resource_grant",
            "result": "ok",
            "user_id": "alice",
            "details": "tenant=tenant-a org=org-a token=raw-token",
            "legal_hold": False,
        },
        {
            "timestamp": 120,
            "request_id": "req-hold",
            "action": "resource_access_denied",
            "result": "rejected",
            "user_id": "bob",
            "details": "tenant=tenant-b org=org-b secret=raw-secret",
            "legal_hold": True,
        },
        {
            "timestamp": 80000,
            "request_id": "req-recent",
            "action": "get_auth_whoami",
            "result": "ok",
            "user_id": "carol",
            "details": "tenant=tenant-c org=org-c",
            "legal_hold": False,
        },
    ]

    preview_payload = build_security_audit_archive_policy_payload(
        events,
        mode="preview",
        retention_days=1,
        current_time=90000,
        limit=2,
        history_limit=50,
        legal_hold=True,
    )

    assert preview_payload["mode"] == "preview"
    assert preview_payload["retention_days"] == 1
    assert preview_payload["cutoff_timestamp"] == 90000 - 86400
    assert preview_payload["history_limit"] == 50
    assert preview_payload["total"] == 3
    assert preview_payload["archive_candidate_count"] == 1
    assert preview_payload["legal_hold_count"] == 1
    assert preview_payload["legal_hold_preserved_count"] == 1
    assert preview_payload["events"] == []
    assert preview_payload["cleanup_behavior"]["legal_hold_requested"] is True

    export_payload = build_security_audit_archive_policy_payload(
        events,
        mode="export",
        retention_days=1,
        current_time=90000,
        limit=1,
        history_limit=50,
    )

    assert export_payload["mode"] == "export"
    assert export_payload["export_count"] == 1
    assert export_payload["events"][0]["request_id"] == "req-delete"
    assert export_payload["events"][0]["tenant"] == "tenant-a"
    assert export_payload["events"][0]["org"] == "org-a"
    assert "raw-token" not in export_payload["events"][0]["details"]


def test_build_security_audit_archive_policy_payload_normalizes_policy_edges():
    events = [
        {
            "timestamp": 100,
            "request_id": "req-eligible",
            "action": "upsert_resource_grant",
            "result": "ok",
            "details": "tenant=tenant-a org=org-a",
            "legal_hold": False,
        },
        {
            "timestamp": 200,
            "request_id": "req-held",
            "action": "resource_access_denied",
            "result": "rejected",
            "details": "tenant=tenant-b org=org-b",
            "legal_hold": True,
        },
    ]

    payload = build_security_audit_archive_policy_payload(
        events,
        mode="delete",
        retention_days=-7,
        current_time=1000,
        limit=10,
        history_limit=0,
        legal_hold=False,
    )

    assert payload["mode"] == "preview"
    assert payload["retention_days"] == 0
    assert payload["cutoff_timestamp"] is None
    assert payload["history_limit"] == 1
    assert payload["archive_candidate_count"] == 1
    assert payload["export_count"] == 0
    assert payload["events"] == []
    assert payload["legal_hold_count"] == 1
    assert payload["legal_hold_preserved_count"] == 1
    assert payload["cleanup_behavior"]["cleanup_preserves_legal_hold"] is True
    assert payload["cleanup_behavior"]["legal_hold_requested"] is False


def test_build_security_audit_archive_policy_payload_clamps_export_to_history_limit():
    events = [
        {
            "timestamp": timestamp,
            "request_id": f"req-{timestamp}",
            "action": "upsert_resource_grant",
            "result": "ok",
            "details": f"tenant=tenant-{timestamp} org=org-{timestamp}",
            "legal_hold": False,
        }
        for timestamp in (100, 200, 300)
    ]

    preview_payload = build_security_audit_archive_policy_payload(
        events,
        mode="preview",
        retention_days=1,
        current_time=90000,
        limit=99,
        history_limit=2,
        legal_hold=True,
    )
    export_payload = build_security_audit_archive_policy_payload(
        events,
        mode="export",
        retention_days=1,
        current_time=90000,
        limit=99,
        history_limit=2,
        legal_hold=True,
    )

    assert preview_payload["archive_candidate_count"] == 3
    assert preview_payload["export_count"] == 0
    assert preview_payload["events"] == []
    assert preview_payload["cleanup_behavior"]["legal_hold_requested"] is True
    assert export_payload["archive_candidate_count"] == 3
    assert export_payload["export_count"] == 2
    assert [event["request_id"] for event in export_payload["events"]] == [
        "req-100",
        "req-200",
    ]


def test_build_security_audit_aggregate_report_payload_groups_siem_dimensions():
    events = [
        {
            "timestamp": 20,
            "action": "upsert_resource_grant",
            "result": "ok",
            "user_id": "alice",
            "tenant_id": "tenant-a",
            "org_id": "org-a",
        },
        {
            "timestamp": 21,
            "action": "upsert_resource_grant",
            "result": "ok",
            "user_id": "alice",
            "tenant_id": "tenant-a",
            "org_id": "org-a",
        },
        {
            "timestamp": 22,
            "action": "unknown_custom_action",
            "result": "blocked",
            "details": "tenant=tenant-b org=org-b token=raw-token",
        },
    ]
    filters = {"category": "access"}

    payload = build_security_audit_aggregate_report_payload(
        events,
        limit=200,
        filters=filters,
    )

    assert payload["total"] == 3
    assert payload["window_limit"] == 200
    assert payload["filters"] == filters
    assert payload["group_by"] == [
        "tenant",
        "org",
        "user_id",
        "category",
        "action",
        "result",
    ]
    assert payload["rows"] == [
        {
            "tenant": "tenant-a",
            "org": "org-a",
            "user_id": "alice",
            "category": "access",
            "action": "upsert_resource_grant",
            "result": "ok",
            "count": 2,
        },
        {
            "tenant": "tenant-b",
            "org": "org-b",
            "user_id": "unknown",
            "category": "uncategorized",
            "action": "unknown_custom_action",
            "result": "blocked",
            "count": 1,
        },
    ]
    assert payload["totals"]["tenant"] == {"tenant-a": 2, "tenant-b": 1}
    assert payload["totals"]["category"] == {"access": 2, "uncategorized": 1}


def test_security_audit_event_tenant_falls_back_to_org():
    event = {"tenant_id": "", "org_id": "org-a"}

    assert security_audit_event_org(event) == "org-a"
    assert security_audit_event_tenant(event) == "org-a"


def test_filter_security_audit_events_applies_action_category_user_and_time_filters():
    events = [
        {
            "timestamp": 10,
            "action": "upsert_resource_grant",
            "result": "ok",
            "user_id": "alice",
        },
        {
            "timestamp": 11,
            "action": "remote_auth_guard",
            "result": "rejected",
            "user_id": "alice",
        },
        {
            "timestamp": 12,
            "action": "upsert_resource_grant",
            "result": "ok",
            "user_id": "bob",
        },
    ]

    assert filter_security_audit_events(
        events,
        action="upsert_resource_grant",
        category="access",
        result="ok",
        user_id="alice",
        since=9,
        until=10,
    ) == [events[0]]
