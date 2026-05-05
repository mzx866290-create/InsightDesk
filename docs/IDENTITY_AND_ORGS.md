# Identity And Organization Runtime

## Scope

This is the first foundation layer for multi-user and organization-aware access control. It adds persistent identity data without forcing every existing resource route to change in the same step.

Current persisted entities:

- organizations
- users
- organization memberships

Current API surface:

- `GET /api/identity` lists organizations, users, and memberships for authenticated viewers.
- `POST /api/identity/orgs` upserts an organization for admins.
- `POST /api/identity/users` upserts a user for admins.
- `POST /api/identity/memberships` sets a user's organization role for admins.
- `GET /api/auth/sso/config` exposes sanitized SSO/OIDC readiness metadata for authenticated viewers.
- `PUT /api/auth/sso/config` lets admins persist runtime SSO/OIDC settings without returning the raw client secret.
- `GET /api/auth/sso/login` builds an OIDC authorization URL with state, nonce, and PKCE challenge.
- `GET /api/auth/sso/callback` exchanges an authorization code, verifies ID token claims, and syncs identity.
- `POST /api/identity/sso/sync` maps verified external identity claims into local users and memberships for admins.
- `GET /api/security/audit-summary?category=identity|auth` returns sanitized security audit aggregates for identity and SSO review loops.

## Store boundary

Identity persistence lives in `backend/stores/identity_store.py` and is exposed through the `IdentityStore` protocol in `backend/stores/protocols.py`.

`backend/stores/factory.py` owns construction through `create_identity_store()`. Future PostgreSQL identity storage should be added behind that factory/protocol boundary.

## Relationship to token auth

Existing token auth remains the request authentication mechanism. The identity store is a durable user/org membership catalog that future resource-level authorization can query. This keeps the migration incremental:

1. authenticate request with existing token catalog
2. map token `user_id` to persisted `users`
3. check persisted `memberships`
4. enforce resource ownership/grants in later route updates

## Next authorization step

The next step is to attach `org_id` or resource grants to sessions, knowledge bases, artifacts, decks, and share links, then enforce access through route-level helpers.

## SSO reservation layer

SSO/OIDC now has a complete MVP login path. The backend exposes safe readiness metadata:

```http
GET /api/auth/sso/config
```

Supported environment variables:

- `SSO_PROVIDER=none|oidc`
- `OIDC_ISSUER_URL`
- `OIDC_AUTHORIZATION_ENDPOINT`
- `OIDC_TOKEN_ENDPOINT`
- `OIDC_JWKS_URL`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`
- `OIDC_SCOPES=openid email profile`
- `OIDC_ALLOWED_DOMAINS=example.com,ops.example.com`
- `SSO_DEFAULT_ROLE=viewer`
- `SSO_SESSION_TTL_SECONDS=28800`

The response reports provider/client readiness, non-secret endpoints, scopes, default role, session TTL, and the planned claim mapping (`sub`, `email`, `name`, `groups`). It never returns the raw client secret.

Admins can persist the same runtime settings through the encrypted app config store:

```http
PUT /api/auth/sso/config
Content-Type: application/json

{
  "provider": "oidc",
  "issuer_url": "https://idp.example.com",
  "authorization_endpoint": "https://idp.example.com/oauth2/v1/authorize",
  "token_endpoint": "https://idp.example.com/oauth2/v1/token",
  "jwks_url": "https://idp.example.com/oauth2/v1/keys",
  "client_id": "insightdesk",
  "client_secret": "new-secret",
  "allowed_domains": "example.com,ops.example.com",
  "scopes": "openid email profile",
  "default_role": "viewer",
  "session_ttl_seconds": 28800
}
```

Leave `client_secret` blank to keep the existing secret. Send `clear_client_secret=true` to remove the stored secret; an environment-provided secret may still be effective after clearing persisted config.

The login bootstrap endpoint returns the IdP authorization URL plus non-secret correlation metadata:

```http
GET /api/auth/sso/login
```

It requires `SSO_PROVIDER=oidc`, `OIDC_CLIENT_ID`, and `OIDC_AUTHORIZATION_ENDPOINT`. The server stores the PKCE verifier in memory for a short TTL and returns only the S256 challenge to the client.

SSO login and callback audit entries now include a compact security summary. Login audit details include response mode plus short SHA-256 fingerprints for `state` and `nonce`; callback audit details include provider, mapped user, resolved app role, membership count, external group count, token type, IdP token expiry, application session expiry, and a short fingerprint of the issued application session token. Raw state, nonce, and application session tokens are never written to the audit log.

Reviewers can close the SSO and identity audit loop through the summarized audit endpoint:

```http
GET /api/security/audit-summary?category=identity
GET /api/security/audit-summary?category=auth
```

The summary groups recent security audit events by `action` and `result`, and returns the recent event count for the selected category. It is intended for permission and SSO review dashboards, and keeps the same redaction boundary as the underlying audit events: no raw secret, token, state, nonce, or client credential is exposed.

The callback endpoint consumes the stored state, exchanges the authorization code with `OIDC_TOKEN_ENDPOINT`, verifies the ID token through `OIDC_JWKS_URL` using PyJWT, validates issuer/audience/nonce, then maps verified claims into `users` and `memberships`. A successful callback also issues a short-lived application session token. The token is accepted through the existing `Authorization: Bearer <token>` path, uses `SSO_DEFAULT_ROLE` as its global app role, and expires after `SSO_SESSION_TTL_SECONDS`.

Issued SSO session tokens are now persisted in SQLite instead of memory-only state. The store keeps only a SHA-256 token hash plus the resolved app user, role, auth source, and expiry time, so the bearer token itself is not written to disk in plaintext. This allows session survival across process restarts while preserving the existing runtime auth flow.

The settings modal now exposes SSO readiness, editable OIDC settings, and a browser login button. The frontend starts login with:

```http
GET /api/auth/sso/login?response_mode=fragment
```

In this mode, the callback writes the issued application session token to `sessionStorage` and returns the browser to `/`, so existing API calls reuse the same token plumbing as manual API tokens.

Admins can also exercise the same post-verification mapping path directly:

```http
POST /api/identity/sso/sync
Content-Type: application/json

{
  "provider": "oidc",
  "claims": {
    "sub": "external-user-id",
    "email": "alice@example.com",
    "name": "Alice Example",
    "groups": ["engineering"]
  },
  "allowed_domains": ["example.com"],
  "group_org_map": {"engineering": "org-acme"},
  "group_role_map": {"engineering": "editor"}
}
```

This endpoint is admin-only and assumes the supplied claims were already verified by a trusted SSO layer. It prefixes local user IDs with the provider (`oidc:<sub>`), enforces optional email domain allow-lists, upserts the user record, and maps configured external groups to existing organizations. Unknown groups are ignored; missing organizations are rejected so membership state cannot drift silently.
