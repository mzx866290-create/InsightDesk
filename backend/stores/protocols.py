"""Protocol contracts for application store adapters."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.artifact_service import ArtifactRecord
from backend.deck_service import DeckSpec
from backend.stores.config_store import StoredConfigValue
from backend.stores.security_audit_store import SecurityAuditEventStoredRecord
from backend.stores.share_link_store import ShareLinkRecord
from backend.stores.task_store import AttachmentPromotionRecord, TaskRecord
from backend.stores.identity_store import (
    MembershipRecord,
    OrganizationRecord,
    UserRecord,
)
from backend.stores.resource_access_store import (
    ResourceAccessRecord,
    ResourceGrantRecord,
)


@runtime_checkable
class AppConfigStore(Protocol):
    def get(self, key: str) -> StoredConfigValue | None: ...

    def get_value(self, key: str, default: str = "") -> str: ...

    def set(self, key: str, value: str) -> StoredConfigValue: ...

    def delete(self, key: str) -> bool: ...


@runtime_checkable
class SecurityAuditStore(Protocol):
    history_limit: int

    def append(self, event: dict[str, Any]) -> SecurityAuditEventStoredRecord: ...

    def list_events(
        self,
        *,
        limit: int = 50,
        action: str = "",
        result: str = "",
    ) -> list[SecurityAuditEventStoredRecord]: ...

    def count_events(self) -> int: ...

    def trim_to_latest(self, keep_latest: int = 0) -> int: ...

    def prune(self) -> None: ...


@runtime_checkable
class ShareLinkStore(Protocol):
    def upsert(
        self,
        *,
        share_token: str,
        resource_type: str,
        resource_id: str,
        created_at: float,
        expires_at: float,
        created_by: str = "",
        meta: dict[str, Any] | None = None,
    ) -> ShareLinkRecord: ...

    def get(self, share_token: str) -> ShareLinkRecord | None: ...

    def get_active(
        self,
        *,
        share_token: str,
        now: float | None = None,
    ) -> ShareLinkRecord | None: ...

    def list_links(
        self,
        *,
        resource_type: str = "",
        resource_id: str = "",
        include_revoked: bool = False,
        limit: int = 100,
    ) -> list[ShareLinkRecord]: ...

    def revoke(self, share_token: str) -> bool: ...

    def delete_for_resource(self, resource_type: str, resource_id: str) -> int: ...

    def record_access(self, share_token: str, *, accessed_at: float) -> bool: ...


@runtime_checkable
class SsoSessionStore(Protocol):
    def save(
        self,
        *,
        token_hash: str,
        user_id: str,
        role: str,
        auth_source: str,
        created_at: float,
        expires_at: float,
    ): ...

    def get_active(
        self,
        token_hash: str,
        *,
        now: float | None = None,
    ): ...

    def delete(self, token_hash: str) -> bool: ...

    def prune(self, *, now: float | None = None) -> int: ...


@runtime_checkable
class TaskStore(Protocol):
    history_limit: int
    ttl_seconds: int

    def save(self, record: TaskRecord) -> TaskRecord: ...

    def get(self, task_id: str) -> TaskRecord | None: ...

    def list_recent(self, limit: int = 20) -> list[TaskRecord]: ...

    def get_attachment_promotion(
        self,
        attachment_id: str,
        vector_store_path: str,
    ) -> AttachmentPromotionRecord | None: ...

    def get_attachment_promotion_task(
        self,
        attachment_id: str,
        vector_store_path: str,
    ) -> TaskRecord | None: ...

    def delete_for_session(self, session_id: str) -> dict[str, int]: ...

    def prune(self, *, now: float | None = None) -> None: ...


@runtime_checkable
class SessionMemoryStore(Protocol):
    def list_session_memory(
        self,
        session_id: str,
        *,
        kind: str | None = None,
        limit: int | None = None,
        newest_first: bool = False,
    ) -> list[dict[str, Any]]: ...

    def create_session_memory(
        self,
        session_id: str,
        *,
        kind: str,
        content: Any,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None: ...

    def pin_session_memory(
        self,
        session_id: str,
        *,
        content: Any,
        kind: str = "fact",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None: ...

    def update_session_memory(
        self,
        session_id: str,
        memory_id: str,
        *,
        content: Any = None,
        kind: Any = None,
        meta: Any = None,
        update_content: bool = False,
        update_kind: bool = False,
        update_meta: bool = False,
    ) -> dict[str, Any] | None: ...

    def delete_session_memory(self, session_id: str, memory_id: str) -> bool: ...

    def clear_session_memory(self, session_id: str) -> None: ...

    def replace_session_panels(
        self,
        session_id: str,
        panel_configs: list[dict[str, Any]],
    ) -> None: ...

    def upsert_session_panel(
        self,
        session_id: str,
        panel_config: dict[str, Any],
    ) -> None: ...

    def get_session_panels(self, session_id: str) -> list[dict[str, Any]]: ...


@runtime_checkable
class RetrievalFeedbackStore(Protocol):
    def set_retrieval_feedback(
        self,
        session_id: str,
        *,
        panel_id: str,
        answer_group_id: str,
        source: dict[str, Any],
        feedback_value: int,
    ) -> dict[str, Any]: ...

    def list_retrieval_feedback(
        self,
        session_id: str,
        *,
        panel_id: str,
        answer_group_id: str,
    ) -> list[dict[str, Any]]: ...

    def aggregate_retrieval_feedback_by_source(
        self,
        *,
        source_type: str | None = None,
    ) -> list[dict[str, Any]]: ...


@runtime_checkable
class ArtifactStore(Protocol):
    def save(self, artifact: ArtifactRecord) -> ArtifactRecord: ...

    def get(self, artifact_id: str) -> ArtifactRecord: ...

    def list_recent(
        self,
        *,
        limit: int = 100,
        artifact_type: str = "",
    ) -> list[ArtifactRecord]: ...

    def list_by_session(
        self,
        session_id: str,
        *,
        artifact_type: str = "",
    ) -> list[ArtifactRecord]: ...

    def list_by_linked_resource(
        self,
        linked_resource_type: str,
        linked_resource_id: str,
    ) -> list[ArtifactRecord]: ...

    def delete_by_session(self, session_id: str) -> int: ...


@runtime_checkable
class DeckStore(Protocol):
    def save(self, deck: DeckSpec) -> DeckSpec: ...

    def get(self, deck_id: str) -> DeckSpec: ...

    def list_recent(self, *, limit: int = 100) -> list[DeckSpec]: ...

    def list_ids_by_session(self, session_id: str) -> list[str]: ...

    def delete_by_session(self, session_id: str) -> int: ...


@runtime_checkable
class IdentityStore(Protocol):
    def ensure_default_org(self, *, now: float) -> OrganizationRecord: ...

    def upsert_org(
        self,
        *,
        org_id: str,
        name: str,
        description: str = "",
        now: float,
    ) -> OrganizationRecord: ...

    def get_org(self, org_id: str) -> OrganizationRecord | None: ...

    def list_orgs(self, *, limit: int = 100) -> list[OrganizationRecord]: ...

    def upsert_user(
        self,
        *,
        user_id: str,
        display_name: str,
        email: str = "",
        now: float,
    ) -> UserRecord: ...

    def get_user(self, user_id: str) -> UserRecord | None: ...

    def list_users(self, *, limit: int = 100) -> list[UserRecord]: ...

    def set_membership(
        self,
        *,
        org_id: str,
        user_id: str,
        role: str,
        now: float,
    ) -> MembershipRecord: ...

    def get_membership(
        self, *, org_id: str, user_id: str
    ) -> MembershipRecord | None: ...

    def list_memberships(
        self,
        *,
        org_id: str = "",
        user_id: str = "",
        limit: int = 100,
    ) -> list[MembershipRecord]: ...


@runtime_checkable
class ResourceAccessStore(Protocol):
    def upsert_grant(
        self,
        *,
        resource_type: str,
        resource_id: str,
        role: str,
        now: float,
        org_id: str = "",
        user_id: str = "",
    ) -> ResourceGrantRecord: ...

    def get_grant(
        self,
        *,
        resource_type: str,
        resource_id: str,
        org_id: str = "",
        user_id: str = "",
    ) -> ResourceGrantRecord | None: ...

    def list_grants(
        self,
        *,
        resource_type: str = "",
        resource_id: str = "",
        org_id: str = "",
        user_id: str = "",
        limit: int = 100,
        offset: int = 0,
        role: str = "",
        subject_type: str = "",
    ) -> list[ResourceGrantRecord]: ...

    def count_grants(
        self,
        *,
        resource_type: str = "",
        resource_id: str = "",
        org_id: str = "",
        user_id: str = "",
        role: str = "",
        subject_type: str = "",
    ) -> int: ...

    def delete_grant(
        self,
        *,
        resource_type: str,
        resource_id: str,
        org_id: str = "",
        user_id: str = "",
    ) -> bool: ...

    def resolve_user_access(
        self,
        *,
        resource_type: str,
        resource_id: str,
        user_id: str,
        identity_store: Any,
        minimum_role: str = "viewer",
    ) -> ResourceAccessRecord: ...
