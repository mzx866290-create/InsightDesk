# Backend Architecture Notes

## Current backend layering

`backend/api_server.py` is now kept as the FastAPI composition entrypoint. It should only own application bootstrap, environment/runtime constants, compatibility wrappers, middleware registration, router registration calls, and static frontend mounting.

Core business implementation should live in focused modules:

- `backend/routes/`: FastAPI route builders.
- `backend/helpers/`: route/service helper logic.
- `backend/stores/`: SQLite-backed persistence adapters.
- `backend/services/`: service compatibility proxies and domain services.
- `backend/schemas/`: Pydantic request/response models.
- `backend/core/`: application runtime wiring, security, metrics, task runtime, configuration, and session summary helpers.

## Compatibility modules

Top-level `backend/api_*.py` files are compatibility re-exports for older tests, scripts, and imports. New code should import from the canonical modules under `backend/routes`, `backend/helpers`, `backend/stores`, `backend/schemas`, or `backend/core`.

These compatibility modules should not contain new business logic. If one needs behavior changes, update the canonical module first and keep the `api_*` file as a thin re-export only.

## Refactor boundary

When adding new backend functionality:

1. Put schemas in `backend/schemas`.
2. Put route handlers in `backend/routes` as router builders.
3. Put persistence in `backend/stores`.
4. Put cross-cutting runtime logic in `backend/core`.
5. Keep `backend/api_server.py` as a thin composition layer.
6. Avoid adding new `backend/api_*.py` modules unless they are temporary compatibility shims.
