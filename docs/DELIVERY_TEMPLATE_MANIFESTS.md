# Delivery Template Manifests

Delivery templates expose productized report and Deck/PPT starting points through
`GET /api/delivery-templates/catalog`.

## What They Do

- Register report or Deck template metadata.
- Keep templates visible in Settings without executing template code.
- Support optional JSON manifests under `config/delivery_templates/`.
- Support admin install/uninstall of sanitized manifests from Settings.

## Environment Variables

- `DELIVERY_TEMPLATE_MANIFESTS_ENABLED`
  Enables or disables manifest loading. Defaults to `true`.

- `DELIVERY_TEMPLATE_MANIFEST_DIRS`
  Optional `pathsep`-separated list of manifest directories.

## Manifest Schema

```json
{
  "enabled": true,
  "id": "incident_review",
  "version": "1.0.0",
  "name": "Incident Review",
  "description": "Incident timeline, impact, root cause, and follow-up actions.",
  "artifact_type": "report",
  "category": "operations",
  "tags": ["incident", "postmortem", "ops"],
  "target_format": "markdown",
  "preview": "Timeline → Impact → Root cause → Action items",
  "suggested_options": {
    "scope": "session",
    "include_sources": true
  },
  "metadata": {
    "owner": "ops"
  }
}
```

### Required Fields

- `id`: `1-80` characters, letters / numbers / `. _ -` only.
- `name`: non-empty display name.
- `description`: non-empty description.
- `artifact_type`: `report` or `deck`.
- `tags`: non-empty string array.
- `target_format`: output format such as `markdown` or `pptx`.

### Validation Feedback

The catalog response includes manifest diagnostics:

- `scanned_count`: JSON files scanned
- `loaded_count`: valid manifests loaded
- `issue_count`: invalid or duplicate manifests skipped
- `issues[]`: file-level diagnostics with `code` and `message`

## Management API

- `GET /api/delivery-templates/catalog`: lists built-in and manifest templates
  with validation diagnostics.
- `POST /api/delivery-templates/install`: validates and writes a sanitized
  manifest; template code is never executed.
- `DELETE /api/delivery-templates/{template_id}`: removes a non-built-in
  manifest and refreshes the returned catalog.

## Example

See `config/delivery_templates/incident_review.example.json`.
