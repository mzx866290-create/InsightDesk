from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from backend.chat_store import connect_sqlite

_ENCRYPTED_PREFIX = "enc:v1:"
_MASTER_KEY_ENV = "APP_CONFIG_MASTER_KEY"
_MASTER_KEY_PATH_ENV = "APP_CONFIG_MASTER_KEY_PATH"


@dataclass
class StoredConfigValue:
    key: str
    value: str
    updated_at: float


class SQLiteAppConfigStore:
    """Persist small runtime config values in the shared SQLite database."""

    def __init__(self, db_path: str = "./chat_history.db"):
        self.db_path = db_path
        self._master_key = self._load_master_key()
        self._init_db()

    def _default_master_key_path(self) -> Path:
        configured = str(os.getenv(_MASTER_KEY_PATH_ENV) or "").strip()
        if configured:
            return Path(configured).expanduser()
        db_path = Path(self.db_path).resolve()
        return db_path.parent / ".app_config.key"

    def _load_master_key(self) -> bytes:
        env_key = str(os.getenv(_MASTER_KEY_ENV) or "").strip()
        if env_key:
            return hashlib.sha256(env_key.encode("utf-8")).digest()

        key_path = self._default_master_key_path()
        if key_path.exists():
            return key_path.read_bytes()

        key_path.parent.mkdir(parents=True, exist_ok=True)
        master_key = secrets.token_bytes(32)
        key_path.write_bytes(master_key)
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            # Best effort only; Windows may ignore POSIX-style permission bits.
            pass
        return master_key

    @staticmethod
    def _xor_bytes(left: bytes, right: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(left, right))

    def _derive_keystream(self, nonce: bytes, length: int) -> bytes:
        blocks: list[bytes] = []
        counter = 0
        while sum(len(block) for block in blocks) < length:
            counter_bytes = counter.to_bytes(4, "big")
            blocks.append(hmac.new(self._master_key, nonce + counter_bytes, hashlib.sha256).digest())
            counter += 1
        return b"".join(blocks)[:length]

    def _encrypt_value(self, value: str) -> str:
        normalized = str(value or "")
        if not normalized:
            return ""

        plain = normalized.encode("utf-8")
        nonce = secrets.token_bytes(16)
        cipher = self._xor_bytes(plain, self._derive_keystream(nonce, len(plain)))
        tag = hmac.new(
            self._master_key,
            b"app-config-v1" + nonce + cipher,
            hashlib.sha256,
        ).digest()
        payload = base64.urlsafe_b64encode(nonce + tag + cipher).decode("ascii")
        return f"{_ENCRYPTED_PREFIX}{payload}"

    def _decrypt_value(self, value: str) -> str:
        normalized = str(value or "")
        if not normalized:
            return ""
        if not normalized.startswith(_ENCRYPTED_PREFIX):
            return normalized

        encoded = normalized[len(_ENCRYPTED_PREFIX) :]
        payload = base64.urlsafe_b64decode(encoded.encode("ascii"))
        if len(payload) < 48:
            raise ValueError("encrypted app config payload is too short")

        nonce = payload[:16]
        tag = payload[16:48]
        cipher = payload[48:]
        expected_tag = hmac.new(
            self._master_key,
            b"app-config-v1" + nonce + cipher,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("encrypted app config payload failed integrity check")

        plain = self._xor_bytes(cipher, self._derive_keystream(nonce, len(cipher)))
        return plain.decode("utf-8")

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS app_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_app_config_updated_at
                ON app_config(updated_at DESC)
                """
            )
            conn.commit()

    def get(self, key: str) -> StoredConfigValue | None:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return None
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, value, updated_at FROM app_config WHERE key = ?",
                (normalized_key,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return StoredConfigValue(
            key=str(row[0] or ""),
            value=self._decrypt_value(str(row[1] or "")),
            updated_at=float(row[2] or 0.0),
        )

    def get_value(self, key: str, default: str = "") -> str:
        record = self.get(key)
        return record.value if record is not None else str(default or "")

    def set(self, key: str, value: str) -> StoredConfigValue:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            raise ValueError("config key must not be empty")
        normalized_value = str(value or "").strip()
        updated_at = time.time()
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO app_config(key, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (normalized_key, self._encrypt_value(normalized_value), updated_at),
            )
            conn.commit()
        return StoredConfigValue(
            key=normalized_key,
            value=normalized_value,
            updated_at=updated_at,
        )

    def delete(self, key: str) -> bool:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return False
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM app_config WHERE key = ?", (normalized_key,))
            deleted = cursor.rowcount > 0
            conn.commit()
        return deleted
