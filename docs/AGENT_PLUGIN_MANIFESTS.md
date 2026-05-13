# Agent Plugin Manifests

This project supports declarative Agent plugin manifests under
`config/agent_plugins/`.

## What They Do

- Register static or declarative workflow catalog entries only.
- Do not import or execute plugin code.
- Keep startup safe by skipping invalid or duplicate manifests.

## Environment Variables

- `AGENT_PLUGIN_MANIFESTS_ENABLED`
  Enables or disables manifest loading. Defaults to `true`.

- `AGENT_PLUGIN_MANIFEST_DIRS`
  Optional `pathsep`-separated list of manifest directories.

## Manifest Schema

```json
{
  "enabled": true,
  "name": "market_research",
  "version": "1.0.0",
  "runtime": "static_manifest",
  "description": "Market research workflow plugin.",
  "capabilities": ["market_research", "competitive_scan"],
  "output_prefix": "Market research plugin completed",
  "risk_level": "medium",
  "requires_approval": false,
  "approval_reason": "",
  "metadata": {
    "category": "research",
    "owner": "example"
  }
}
```

### Required Fields

- `name`: `1-64` characters, letters / numbers / `. _ -` only.
- `description`: non-empty string.
- `capabilities`: non-empty string array.

### Optional Fields

- `enabled`: set to `false` to keep an example manifest inert.
- `runtime`: `static_manifest` for deterministic static output, or
  `workflow_manifest` for a safe declarative workflow.
- `version`: copied into catalog metadata.
- `output_prefix`: fallback text shown by the static agent.
- `risk_level`: `low`, `medium`, `high`, or `critical`; copied into plan metadata.
- `requires_approval`: forces an orchestrator approval gate before execution.
- `approval_reason`: human-readable explanation shown with approval metadata.
- `metadata`: scalar-safe metadata copied into the catalog.

### Workflow Runtime

`workflow_manifest` lets a plugin define ordered steps without importing or
executing Python / JavaScript code:

```json
{
  "enabled": true,
  "name": "customer_health_workflow",
  "runtime": "workflow_manifest",
  "description": "Customer health review workflow.",
  "capabilities": ["customer_health", "account_review"],
  "output_prefix": "Customer health workflow completed",
  "workflow": [
    {
      "id": "signals",
      "title": "Collect health signals",
      "prompt": "Review support, usage, and renewal signals for {description}.",
      "artifact_type": "analysis_note"
    },
    {
      "id": "actions",
      "title": "Recommend actions",
      "prompt": "Create next-best actions for {task_type}.",
      "artifact_type": "action_plan"
    }
  ]
}
```

Supported prompt placeholders are `{description}`, `{input}`, `{task_type}`,
`{task_id}`, and `{context_keys}`. Workflow manifests are capped at 12 steps.
Unsupported runtimes are rejected; `entrypoint` fields are ignored and never
executed.

## Runtime Governance

- Manifest metadata is copied into orchestrator plan steps.
- `requires_approval: true` pauses execution at the human approval gate.
- `risk_level: high` or `critical` participates in `task_approval_policy`
  when `high_risk_requires_approval` is enabled.

## Validation Feedback

The Agent Catalog now reports manifest load diagnostics:

- `scanned_count`: JSON files scanned
- `loaded_count`: valid manifests loaded
- `issue_count`: invalid or duplicate manifests skipped
- `issues[]`: file-level diagnostics with `code` and `message`

## Marketplace Templates

The Agent Catalog response also includes an `marketplace` block with curated
installable templates:

- Built-in templates are returned without reading or executing plugin code.
- Optional JSON templates can be placed under `config/agent_plugin_marketplace/`.
- Disabled `*.example.json` files under `config/agent_plugins/` are treated as
  installable examples with `enabled: true` in the install payload.
- Installing a marketplace template writes a sanitized manifest to the active
  plugin manifest directory and always reports `executed_entrypoint: false`.

Use `AGENT_PLUGIN_MARKETPLACE_DIRS` to provide a `pathsep`-separated list of
additional marketplace template directories.

## Management API

- `GET /api/agents/catalog`: lists built-in agents, manifest plugins,
  manifest diagnostics, and marketplace templates.
- `POST /api/agents/plugins/install`: validates and writes a sanitized
  manifest; plugin entrypoints are never executed.
- `DELETE /api/agents/plugins/{name}`: removes the persisted manifest for a
  non-built-in plugin and refreshes the returned catalog.

## Example

See `config/agent_plugins/market_research.example.json`.
