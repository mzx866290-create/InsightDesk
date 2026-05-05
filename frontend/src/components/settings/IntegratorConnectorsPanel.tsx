import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, CalendarClock, CheckCircle, History, Play, PlugZap, Plus, RefreshCw, RotateCcw, Save, Trash2, Zap } from 'lucide-react'

import {
  getIntegratorAuditEvents,
  getIntegratorConnectors,
  getIntegratorSchedules,
  getMcpConfig,
  getMcpRuntimeHealth,
  probeIntegratorConnector,
  rotateIntegratorConnectorCredentials,
  saveIntegratorConnectors,
  saveIntegratorSchedules,
  saveMcpConfig,
  testIntegratorConnector,
  triggerIntegratorSchedule,
  triggerIntegratorScheduleTick,
} from '../../api/client'
import type {
  IntegratorAuditEvent,
  IntegratorConnector,
  IntegratorConnectorCredentialsRotationResponse,
  IntegratorConnectorProbeResponse,
  IntegratorConnectorTestResult,
  IntegratorConnectorsResponse,
  IntegratorSchedule,
  IntegratorSchedulesResponse,
  IntegratorScheduleTickResponse,
  McpConfigResponse,
  McpConnector,
  McpRuntimeHealthResponse,
} from '../../api/client'
import { Button } from '../ui/Button'

type ConnectorDraft = IntegratorConnector & {
  settingsJson: string
}

type ScheduleDraft = IntegratorSchedule

type ScheduleRuntime = NonNullable<IntegratorSchedulesResponse['scheduler']>

type CredentialMode = 'fields' | 'json'

type CredentialInputKey =
  | 'token'
  | 'api_key'
  | 'client_id'
  | 'client_secret'
  | 'username'
  | 'password'
  | 'authorization'

type CredentialFormValues = Record<CredentialInputKey, string>

interface CredentialFieldDefinition {
  key: CredentialInputKey
  label: string
  placeholder: string
  sensitive: boolean
}

interface CredentialTemplate {
  id: string
  label: string
  description: string
  fields: CredentialInputKey[]
}

const MIN_SCHEDULE_INTERVAL_MINUTES = 5
const MAX_SCHEDULE_INTERVAL_MINUTES = 60 * 24 * 30

const CRON_FIELD_DEFINITIONS = [
  { name: 'minute', min: 0, max: 59 },
  { name: 'hour', min: 0, max: 23 },
  { name: 'day', min: 1, max: 31 },
  { name: 'month', min: 1, max: 12 },
  { name: 'weekday', min: 0, max: 7 },
] as const

type CronFieldDefinition = typeof CRON_FIELD_DEFINITIONS[number]

const SCHEDULE_CRON_MACROS = new Set([
  '@hourly',
  '@daily',
  '@weekly',
  '@monthly',
  '@yearly',
  '@annually',
  '@midnight',
])

const SCHEDULE_CRON_PRESETS = [
  { value: '@hourly', label: 'Hourly' },
  { value: '@daily', label: 'Daily' },
  { value: '@weekly', label: 'Weekly' },
  { value: '@monthly', label: 'Monthly' },
  { value: '@yearly', label: 'Yearly' },
  { value: '0 9 ? * MON-FRI', label: 'Weekday 09:00' },
  { value: '0 0 1 * ?', label: 'Monthly midnight' },
] as const

const CRON_MONTH_ALIASES: Record<string, number> = {
  JAN: 1,
  FEB: 2,
  MAR: 3,
  APR: 4,
  MAY: 5,
  JUN: 6,
  JUL: 7,
  AUG: 8,
  SEP: 9,
  OCT: 10,
  NOV: 11,
  DEC: 12,
}

const CRON_WEEKDAY_ALIASES: Record<string, number> = {
  SUN: 0,
  MON: 1,
  TUE: 2,
  WED: 3,
  THU: 4,
  FRI: 5,
  SAT: 6,
}

const COMMON_TIMEZONES = [
  'UTC',
  'Asia/Shanghai',
  'Asia/Tokyo',
  'Asia/Singapore',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'Australia/Sydney',
] as const

const DEFAULT_CONNECTOR: ConnectorDraft = {
  type: 'webhook',
  name: 'Ops Webhook',
  description: '',
  enabled: true,
  approved: false,
  settings: {
    url: '',
    token: '',
  },
  settingsJson: '{\n  "url": "",\n  "token": ""\n}',
}

const DEFAULT_CREDENTIAL_PATCH_JSON = '{\n  "token": ""\n}'
const DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS = 3
const MIN_EXTERNAL_PROBE_TIMEOUT_SECONDS = 0.1
const MAX_EXTERNAL_PROBE_TIMEOUT_SECONDS = 10
const REDACTED_CREDENTIAL_VALUE = '***redacted***'
const SENSITIVE_SETTING_KEY_PATTERN = /(url|token|secret|client_secret|password|credential|authorization|auth|api_key|key|username)/i
const SENSITIVE_PROBE_DISPLAY_KEY_PATTERN = /(url|token|secret|client_secret|password|credential|authorization|auth|api_key|key)/i
const URL_LIKE_VALUE_PATTERN = /^https?:\/\//i

const EMPTY_CREDENTIAL_FORM: CredentialFormValues = {
  token: '',
  api_key: '',
  client_id: '',
  client_secret: '',
  username: '',
  password: '',
  authorization: '',
}

const CREDENTIAL_FIELD_DEFINITIONS: CredentialFieldDefinition[] = [
  { key: 'token', label: 'Token', placeholder: 'Paste a bearer or webhook token', sensitive: true },
  { key: 'api_key', label: 'API key', placeholder: 'Paste an API key', sensitive: true },
  { key: 'client_id', label: 'Client ID', placeholder: 'OAuth client identifier', sensitive: false },
  { key: 'client_secret', label: 'Client secret', placeholder: 'Paste the OAuth client secret', sensitive: true },
  { key: 'username', label: 'Username', placeholder: 'Basic auth username', sensitive: false },
  { key: 'password', label: 'Password', placeholder: 'Basic auth password', sensitive: true },
  { key: 'authorization', label: 'Authorization header', placeholder: 'Bearer, Basic, or custom header value', sensitive: true },
]

const CREDENTIAL_TEMPLATES: CredentialTemplate[] = [
  {
    id: 'token',
    label: 'Token',
    description: 'Rotate a single token field.',
    fields: ['token'],
  },
  {
    id: 'api_key',
    label: 'API key',
    description: 'Rotate API key based integrations.',
    fields: ['api_key'],
  },
  {
    id: 'oauth_client',
    label: 'OAuth client',
    description: 'Rotate client_id and client_secret together.',
    fields: ['client_id', 'client_secret'],
  },
  {
    id: 'basic_auth',
    label: 'Basic auth',
    description: 'Rotate username and password fields.',
    fields: ['username', 'password'],
  },
  {
    id: 'authorization',
    label: 'Auth header',
    description: 'Rotate a full authorization header value.',
    fields: ['authorization'],
  },
]

const DEFAULT_SCHEDULE: ScheduleDraft = {
  name: 'Hourly sync',
  connector_id: '',
  cron: '0 * * * *',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  interval_minutes: 60,
  enabled: true,
  settings: {},
  last_run_at: null,
  next_run_at: null,
}

function redactSettingsForDisplay(settings: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(settings).map(([key, value]) => {
      if (SENSITIVE_SETTING_KEY_PATTERN.test(key)) {
        return [key, value === '' || value === null || value === undefined ? value : REDACTED_CREDENTIAL_VALUE]
      }
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        return [key, redactSettingsForDisplay(value as Record<string, unknown>)]
      }
      return [key, value]
    }),
  )
}

function toDraft(connector: IntegratorConnector): ConnectorDraft {
  const displaySettings = redactSettingsForDisplay(connector.settings ?? {})
  return {
    ...connector,
    settings: displaySettings,
    settingsJson: JSON.stringify(displaySettings, null, 2),
  }
}

function draftToConnector(draft: ConnectorDraft): IntegratorConnector {
  let settings: Record<string, unknown> = {}
  try {
    const parsed = JSON.parse(draft.settingsJson || '{}') as unknown
    settings = typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : {}
  } catch {
    throw new Error(`Connector settings JSON is invalid: ${draft.name || draft.id || draft.type}`)
  }
  return {
    id: draft.id?.trim() || undefined,
    type: draft.type || 'webhook',
    name: draft.name?.trim() || undefined,
    description: draft.description?.trim() || undefined,
    enabled: draft.enabled !== false,
    approved: draft.approved === true,
    settings,
  }
}

function parseCredentialsPatchJson(value: string): Record<string, unknown> {
  const parsed = JSON.parse(value || '{}') as unknown
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Credential patch must be a JSON object.')
  }
  return parsed as Record<string, unknown>
}

function credentialTemplateById(templateId: string): CredentialTemplate {
  return CREDENTIAL_TEMPLATES.find((template) => template.id === templateId) ?? CREDENTIAL_TEMPLATES[0]
}

function credentialFieldDefinition(field: CredentialInputKey): CredentialFieldDefinition {
  return CREDENTIAL_FIELD_DEFINITIONS.find((definition) => definition.key === field) ?? CREDENTIAL_FIELD_DEFINITIONS[0]
}

function buildCredentialPatchFromFields(
  values: CredentialFormValues,
  fields: CredentialInputKey[],
): Record<string, unknown> {
  const patch = Object.fromEntries(
    fields
      .map((field) => [field, values[field].trim()] as const)
      .filter(([, value]) => value.length > 0),
  )
  if (Object.keys(patch).length === 0) {
    throw new Error('Enter at least one credential field or switch to JSON patch.')
  }
  return patch
}

function connectorIdentifier(connector: ConnectorDraft): string {
  return connector.id?.trim() || connector.name?.trim() || connector.type
}

function formatFieldList(fields: string[]): string {
  return fields.length > 0 ? fields.join(', ') : '-'
}

function displayName(connector: ConnectorDraft): string {
  return connector.name || connector.id || connector.type || 'connector'
}

function scheduleDisplayName(schedule: ScheduleDraft): string {
  return schedule.name || schedule.schedule_id || 'schedule'
}

function draftToSchedule(draft: ScheduleDraft): IntegratorSchedule {
  return {
    schedule_id: draft.schedule_id?.trim() || undefined,
    name: draft.name.trim() || 'Integrator schedule',
    connector_id: draft.connector_id.trim(),
    cron: draft.cron.trim() || '0 * * * *',
    timezone: normalizeScheduleTimezone(draft.timezone),
    interval_minutes: Math.trunc(Number(draft.interval_minutes) || 60),
    enabled: draft.enabled !== false,
    settings: draft.settings ?? {},
    last_run_at: draft.last_run_at ?? null,
    next_run_at: draft.next_run_at ?? null,
  }
}

function validateScheduleCron(cron: string): string | null {
  const value = cron.trim()
  if (!value) return 'Cron is required.'
  if (value.startsWith('@')) {
    return SCHEDULE_CRON_MACROS.has(value.toLowerCase())
      ? null
      : 'Cron macro must be one of @hourly, @daily, @weekly, @monthly, @yearly, @annually, or @midnight.'
  }

  const fields = value.split(/\s+/)
  if (fields.length !== 5) return 'Cron must use 5 fields, for example */15 * * * *.'

  for (const [index, field] of fields.entries()) {
    const error = validateCronField(field, CRON_FIELD_DEFINITIONS[index])
    if (error) return error
  }
  return null
}

function validateCronField(field: string, definition: CronFieldDefinition): string | null {
  if (!field) return `Cron ${definition.name} field is required.`
  if (field === '?') {
    return definition.name === 'day' || definition.name === 'weekday'
      ? null
      : `Cron ${definition.name} field does not support ?. Use ? only in day or weekday fields.`
  }
  if (field.includes('?')) {
    return `Cron ${definition.name} field only supports ? as the whole day or weekday field.`
  }

  const parts = field.split(',')
  if (parts.some((part) => part.trim() === '')) {
    return `Cron ${definition.name} field has an empty list item.`
  }

  for (const rawPart of parts) {
    const error = validateCronFieldPart(rawPart.trim(), definition)
    if (error) return error
  }
  return null
}

function validateCronFieldPart(part: string, definition: CronFieldDefinition): string | null {
  const wildcardStep = part.match(/^\*\/(\d+)$/)
  if (part === '*') return null
  if (wildcardStep) {
    return validateCronStep(Number(wildcardStep[1]), definition, definition.max - definition.min + 1)
  }

  const rangeStep = part.match(/^([A-Za-z]+|\d+)-([A-Za-z]+|\d+)\/(\d+)$/)
  if (rangeStep) {
    const start = parseCronToken(rangeStep[1], definition)
    const end = parseCronToken(rangeStep[2], definition)
    const tokenError = start.error ?? end.error
    if (tokenError) return tokenError
    const step = Number(rangeStep[3])
    return validateCronRange(start.value, end.value, definition)
      ?? validateCronStep(step, definition, end.value - start.value + 1)
  }

  const range = part.match(/^([A-Za-z]+|\d+)-([A-Za-z]+|\d+)$/)
  if (range) {
    const start = parseCronToken(range[1], definition)
    const end = parseCronToken(range[2], definition)
    const tokenError = start.error ?? end.error
    if (tokenError) return tokenError
    return validateCronRange(start.value, end.value, definition)
  }

  const token = parseCronToken(part, definition)
  if (!token.error) return validateCronNumber(token.value, definition)

  return token.error
}

function parseCronToken(token: string, definition: CronFieldDefinition): { value: number; error: null } | { value: 0; error: string } {
  if (/^\d+$/.test(token)) {
    return { value: Number(token), error: null }
  }

  if (!/^[A-Za-z]+$/.test(token)) {
    return {
      value: 0,
      error: `Cron ${definition.name} field has unsupported token "${token}". Use *, */n, numbers, lists, ranges, range steps, or supported month/weekday aliases.`,
    }
  }

  const alias = token.toUpperCase()
  if (definition.name === 'month') {
    const value = CRON_MONTH_ALIASES[alias]
    return value
      ? { value, error: null }
      : { value: 0, error: `Cron month field has unsupported alias "${token}". Use JAN-DEC or 1-12.` }
  }
  if (definition.name === 'weekday') {
    const value = CRON_WEEKDAY_ALIASES[alias]
    return value !== undefined
      ? { value, error: null }
      : { value: 0, error: `Cron weekday field has unsupported alias "${token}". Use SUN-SAT or 0-7.` }
  }
  return {
    value: 0,
    error: `Cron ${definition.name} field does not support alias "${token}". Use a number in ${definition.min}-${definition.max}.`,
  }
}

function validateCronRange(start: number, end: number, definition: CronFieldDefinition): string | null {
  return validateCronNumber(start, definition)
    ?? validateCronNumber(end, definition)
    ?? (start > end ? `Cron ${definition.name} field range ${start}-${end} must start before it ends.` : null)
}

function validateCronNumber(value: number, definition: CronFieldDefinition): string | null {
  if (!Number.isInteger(value)) {
    return `Cron ${definition.name} field value must be a whole number.`
  }
  if (value < definition.min || value > definition.max) {
    return `Cron ${definition.name} field value ${value} is outside ${definition.min}-${definition.max}.`
  }
  return null
}

function validateCronStep(step: number, definition: CronFieldDefinition, span: number): string | null {
  if (!Number.isInteger(step) || step < 1) {
    return `Cron ${definition.name} field step must be at least 1.`
  }
  if (step > span) {
    return `Cron ${definition.name} field step ${step} is larger than its ${span}-value range.`
  }
  return null
}

function validateScheduleInterval(intervalMinutes: number): string | null {
  if (!Number.isInteger(intervalMinutes)) return 'Interval must be a whole number of minutes.'
  if (intervalMinutes < MIN_SCHEDULE_INTERVAL_MINUTES) {
    return `Interval must be at least ${MIN_SCHEDULE_INTERVAL_MINUTES} minutes.`
  }
  if (intervalMinutes > MAX_SCHEDULE_INTERVAL_MINUTES) {
    return `Interval must be no more than ${MAX_SCHEDULE_INTERVAL_MINUTES} minutes.`
  }
  return null
}

function normalizeScheduleTimezone(timezone: string | undefined): string {
  return timezone?.trim() || 'UTC'
}

function validateScheduleTimezone(timezone: string | undefined): string | null {
  const value = normalizeScheduleTimezone(timezone)
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: value })
    return null
  } catch {
    return 'Timezone must be a valid IANA timezone such as UTC, Asia/Shanghai, or America/New_York.'
  }
}

function scheduleValidationMessages(schedules: ScheduleDraft[]): string[] {
  return schedules.flatMap((schedule, index) => {
    const label = scheduleDisplayName(schedule) || `Schedule ${index + 1}`
    return [
      validateScheduleCron(schedule.cron),
      validateScheduleTimezone(schedule.timezone),
      validateScheduleInterval(Number(schedule.interval_minutes)),
    ]
      .filter((message): message is string => Boolean(message))
      .map((message) => `${label}: ${message}`)
  })
}

function scheduleStatusTone(schedule: ScheduleDraft): string {
  return schedule.enabled ? 'bg-accent-green/15 text-accent-green' : 'bg-bg-hover text-text-secondary'
}

function scheduleStatusLabel(schedule: ScheduleDraft): string {
  return schedule.enabled ? 'Enabled' : 'Disabled'
}

function hasConfiguredEndpoint(connector: ConnectorDraft): boolean {
  const settings = connector.settings ?? {}
  return Boolean(settings.url || settings.webhook_url || settings.endpoint || settings.to)
}

function statusTone(connector: ConnectorDraft): string {
  if (!connector.enabled) return 'bg-bg-hover text-text-secondary'
  if (!connector.approved) return 'bg-amber-300/15 text-amber-300'
  return 'bg-accent-green/15 text-accent-green'
}

function statusLabel(connector: ConnectorDraft): string {
  if (!connector.enabled) return 'Disabled'
  if (!connector.approved) return 'Needs approval'
  return 'Approved'
}

const SENSITIVE_AUDIT_KEY_PATTERN = /(url|token|secret|client_secret|password|credential|authorization|auth|key)/i

function formatAuditTime(timestamp: number): string {
  if (!Number.isFinite(timestamp) || timestamp <= 0) return '-'
  const millis = timestamp > 10_000_000_000 ? timestamp : timestamp * 1000
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(millis))
}

function safeAuditDetails(details: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(details)
    .filter(([key]) => !SENSITIVE_AUDIT_KEY_PATTERN.test(key))
    .map(([key, value]) => {
      const rendered = typeof value === 'string' ? value : JSON.stringify(value)
      return [key, rendered ?? ''] as [string, string]
    })
    .filter(([, value]) => value && !/^https?:\/\//i.test(value) && !SENSITIVE_AUDIT_KEY_PATTERN.test(value))
    .slice(0, 4)
}

function clampExternalProbeTimeout(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS
  return Math.max(
    MIN_EXTERNAL_PROBE_TIMEOUT_SECONDS,
    Math.min(MAX_EXTERNAL_PROBE_TIMEOUT_SECONDS, value),
  )
}

function safeProbeEntries(record: Record<string, unknown> | undefined): Array<[string, string]> {
  if (!record) return []
  return Object.entries(record)
    .filter(([key]) => !SENSITIVE_PROBE_DISPLAY_KEY_PATTERN.test(key))
    .map(([key, value]) => {
      const rendered = typeof value === 'string' ? value : JSON.stringify(value)
      return [key, rendered ?? ''] as [string, string]
    })
    .filter(([, value]) => value && !URL_LIKE_VALUE_PATTERN.test(value) && !SENSITIVE_PROBE_DISPLAY_KEY_PATTERN.test(value))
    .slice(0, 4)
}

function mcpConnectorTone(connector: McpConnector): string {
  if (connector.healthy) return 'bg-accent-green/15 text-accent-green'
  if (connector.enabled) return 'bg-amber-300/15 text-amber-300'
  return 'bg-bg-hover text-text-secondary'
}

function mcpConnectorLabel(connector: McpConnector): string {
  if (connector.healthy) return 'Healthy'
  if (connector.enabled) return connector.status || 'Needs check'
  return connector.status || 'Disabled'
}

function normalizeMcpCategoryId(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, '-')
}

function mcpCategoryLabel(value: string): string {
  return value
    .trim()
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export const IntegratorConnectorsPanel: React.FC = () => {
  const [connectors, setConnectors] = useState<ConnectorDraft[]>([])
  const [schedules, setSchedules] = useState<ScheduleDraft[]>([])
  const [auditEvents, setAuditEvents] = useState<IntegratorAuditEvent[]>([])
  const [supportedTypes, setSupportedTypes] = useState<string[]>(['webhook', 'email', 'feishu', 'dingtalk'])
  const [persistence, setPersistence] = useState<IntegratorConnectorsResponse['persistence'] | null>(null)
  const [scheduleRuntime, setScheduleRuntime] = useState<ScheduleRuntime | null>(null)
  const [mcpConfig, setMcpConfig] = useState<McpConfigResponse | null>(null)
  const [mcpRuntimeHealth, setMcpRuntimeHealth] = useState<McpRuntimeHealthResponse | null>(null)
  const [mcpMarketplaceCategoryId, setMcpMarketplaceCategoryId] = useState('all')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [selectedScheduleIndex, setSelectedScheduleIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const [scheduleLoading, setScheduleLoading] = useState(false)
  const [auditLoading, setAuditLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [scheduleSaving, setScheduleSaving] = useState(false)
  const [triggeringScheduleId, setTriggeringScheduleId] = useState<string | null>(null)
  const [scheduleTicking, setScheduleTicking] = useState(false)
  const [mcpLoading, setMcpLoading] = useState(false)
  const [mcpPinging, setMcpPinging] = useState(false)
  const [mcpHotUpdating, setMcpHotUpdating] = useState(false)
  const [testing, setTesting] = useState(false)
  const [rotatingCredentials, setRotatingCredentials] = useState(false)
  const [probingConnector, setProbingConnector] = useState(false)
  const [testResult, setTestResult] = useState<IntegratorConnectorTestResult | null>(null)
  const [credentialMode, setCredentialMode] = useState<CredentialMode>('fields')
  const [credentialTemplateId, setCredentialTemplateId] = useState(CREDENTIAL_TEMPLATES[0].id)
  const [credentialFormValues, setCredentialFormValues] = useState<CredentialFormValues>(EMPTY_CREDENTIAL_FORM)
  const [credentialPatchJson, setCredentialPatchJson] = useState(DEFAULT_CREDENTIAL_PATCH_JSON)
  const [rotationResult, setRotationResult] = useState<IntegratorConnectorCredentialsRotationResponse | null>(null)
  const [probeResult, setProbeResult] = useState<IntegratorConnectorProbeResponse | null>(null)
  const [externalProbeEnabled, setExternalProbeEnabled] = useState(false)
  const [externalProbeTimeoutSeconds, setExternalProbeTimeoutSeconds] = useState(DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS)
  const [scheduleTickResult, setScheduleTickResult] = useState<IntegratorScheduleTickResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [scheduleError, setScheduleError] = useState<string | null>(null)
  const [auditError, setAuditError] = useState<string | null>(null)
  const [mcpError, setMcpError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [scheduleNotice, setScheduleNotice] = useState<string | null>(null)
  const [mcpNotice, setMcpNotice] = useState<string | null>(null)

  const loadMcpProductization = useCallback(async () => {
    setMcpLoading(true)
    setMcpError(null)
    setMcpNotice(null)
    try {
      const [configPayload, healthPayload] = await Promise.all([
        getMcpConfig(),
        getMcpRuntimeHealth(),
      ])
      setMcpConfig(configPayload)
      setMcpRuntimeHealth(healthPayload)
    } catch (err) {
      setMcpError(err instanceof Error ? err.message : String(err || 'Failed to load MCP connector status'))
    } finally {
      setMcpLoading(false)
    }
  }, [])

  const loadConnectors = useCallback(async () => {
    setLoading(true)
    setError(null)
    setNotice(null)
    try {
      const payload = await getIntegratorConnectors()
      setConnectors(payload.connectors.map(toDraft))
      setSupportedTypes(payload.supported_types.length > 0 ? payload.supported_types : ['webhook', 'email', 'feishu', 'dingtalk'])
      setPersistence(payload.persistence)
      setTestResult(null)
      setSelectedIndex(0)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to load integration connectors'))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadAuditEvents = useCallback(async () => {
    setAuditLoading(true)
    setAuditError(null)
    try {
      const payload = await getIntegratorAuditEvents(20)
      setAuditEvents(payload.events)
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : String(err || 'Failed to load integration audit records'))
    } finally {
      setAuditLoading(false)
    }
  }, [])

  const loadSchedules = useCallback(async () => {
    setScheduleLoading(true)
    setScheduleError(null)
    setScheduleNotice(null)
    try {
      const payload = await getIntegratorSchedules()
      setSchedules(payload.schedules)
      setScheduleRuntime(payload.scheduler ?? null)
      setScheduleTickResult(null)
      setSelectedScheduleIndex(0)
    } catch (err) {
      setScheduleError(err instanceof Error ? err.message : String(err || 'Failed to load integration schedules'))
    } finally {
      setScheduleLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadMcpProductization()
    void loadConnectors()
    void loadAuditEvents()
    void loadSchedules()
  }, [loadAuditEvents, loadConnectors, loadMcpProductization, loadSchedules])

  useEffect(() => {
    setCredentialMode('fields')
    setCredentialTemplateId(CREDENTIAL_TEMPLATES[0].id)
    setCredentialFormValues({ ...EMPTY_CREDENTIAL_FORM })
    setCredentialPatchJson(DEFAULT_CREDENTIAL_PATCH_JSON)
    setRotationResult(null)
    setProbeResult(null)
    setExternalProbeEnabled(false)
    setExternalProbeTimeoutSeconds(DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS)
  }, [selectedIndex])

  const selectedConnector = connectors[selectedIndex] ?? null
  const selectedCredentialTemplate = credentialTemplateById(credentialTemplateId)
  const selectedSchedule = schedules[selectedScheduleIndex] ?? null
  const configuredCount = useMemo(
    () => connectors.filter((connector) => connector.enabled && hasConfiguredEndpoint(connector)).length,
    [connectors],
  )
  const approvedCount = useMemo(
    () => connectors.filter((connector) => connector.approved).length,
    [connectors],
  )
  const scheduleValidationErrors = useMemo(() => scheduleValidationMessages(schedules), [schedules])
  const mcpConnectors = mcpConfig?.connectors ?? []
  const mcpMarketplaceSummary = useMemo(() => {
    const backendSummary = mcpConfig?.marketplace?.summary
    if (backendSummary) {
      return {
        total: backendSummary.total,
        enabled: backendSummary.enabled,
        healthy: backendSummary.healthy,
        approval: backendSummary.requires_approval,
        builtin: backendSummary.builtin,
        custom: backendSummary.custom,
        categories: backendSummary.categories,
      }
    }
    return {
      total: mcpConnectors.length,
      enabled: mcpConnectors.filter((connector) => connector.enabled).length,
      healthy: mcpConnectors.filter((connector) => connector.healthy).length,
      approval: mcpConnectors.filter((connector) => connector.requires_approval).length,
      builtin: mcpConnectors.filter((connector) => connector.builtin).length,
      custom: mcpConnectors.filter((connector) => !connector.builtin).length,
      categories: new Set(mcpConnectors.map((connector) => connector.category || 'custom')).size,
    }
  }, [mcpConfig?.marketplace?.summary, mcpConnectors])
  const mcpMarketplaceCategories = useMemo(() => {
    const backendCategories = mcpConfig?.marketplace?.categories ?? []
    if (backendCategories.length > 0) {
      return backendCategories.map((category) => ({
        id: normalizeMcpCategoryId(category.id || category.label || 'custom'),
        label: category.label || mcpCategoryLabel(category.id || 'custom'),
        total: category.total,
        enabled: category.enabled,
        healthy: category.healthy,
        requires_approval: category.requires_approval,
        connectors: category.connectors,
      }))
    }

    const grouped = new Map<string, {
      id: string
      label: string
      total: number
      enabled: number
      healthy: number
      requires_approval: number
      connectors: string[]
    }>()
    for (const connector of mcpConnectors) {
      const rawCategory = connector.category || 'custom'
      const id = normalizeMcpCategoryId(rawCategory)
      const existing = grouped.get(id) ?? {
        id,
        label: mcpCategoryLabel(rawCategory),
        total: 0,
        enabled: 0,
        healthy: 0,
        requires_approval: 0,
        connectors: [],
      }
      existing.total += 1
      existing.enabled += connector.enabled ? 1 : 0
      existing.healthy += connector.healthy ? 1 : 0
      existing.requires_approval += connector.requires_approval ? 1 : 0
      existing.connectors.push(connector.name)
      grouped.set(id, existing)
    }
    return Array.from(grouped.values()).sort((a, b) => a.label.localeCompare(b.label))
  }, [mcpConfig?.marketplace?.categories, mcpConnectors])
  const visibleMcpConnectors = useMemo(() => {
    if (mcpMarketplaceCategoryId === 'all') return mcpConnectors
    const category = mcpMarketplaceCategories.find((item) => item.id === mcpMarketplaceCategoryId)
    const connectorNames = new Set(category?.connectors ?? [])
    if (connectorNames.size > 0) {
      return mcpConnectors.filter((connector) => connectorNames.has(connector.name))
    }
    return mcpConnectors.filter(
      (connector) => normalizeMcpCategoryId(connector.category || 'custom') === mcpMarketplaceCategoryId,
    )
  }, [mcpConnectors, mcpMarketplaceCategories, mcpMarketplaceCategoryId])

  useEffect(() => {
    if (mcpMarketplaceCategoryId === 'all') return
    if (mcpMarketplaceCategories.some((category) => category.id === mcpMarketplaceCategoryId)) return
    setMcpMarketplaceCategoryId('all')
  }, [mcpMarketplaceCategories, mcpMarketplaceCategoryId])

  const updateConnector = (index: number, patch: Partial<ConnectorDraft>) => {
    setConnectors((current) =>
      current.map((connector, itemIndex) =>
        itemIndex === index ? { ...connector, ...patch } : connector,
      ),
    )
  }

  const updateCredentialField = (field: CredentialInputKey, value: string) => {
    setRotationResult(null)
    setCredentialFormValues((current) => ({
      ...current,
      [field]: value,
    }))
  }

  const selectCredentialTemplate = (templateId: string) => {
    const template = credentialTemplateById(templateId)
    const nextValues = { ...EMPTY_CREDENTIAL_FORM }
    for (const field of template.fields) {
      nextValues[field] = credentialFormValues[field]
    }
    setCredentialTemplateId(template.id)
    setCredentialFormValues(nextValues)
    setRotationResult(null)
  }

  const addConnector = () => {
    setConnectors((current) => {
      const next = [...current, { ...DEFAULT_CONNECTOR, name: `Webhook ${current.length + 1}` }]
      setSelectedIndex(next.length - 1)
      return next
    })
    setNotice(null)
    setError(null)
    setTestResult(null)
  }

  const removeConnector = (index: number) => {
    setConnectors((current) => current.filter((_, itemIndex) => itemIndex !== index))
    setSelectedIndex((current) => Math.max(0, Math.min(current, connectors.length - 2)))
    setNotice(null)
    setTestResult(null)
  }

  const updateSchedule = (index: number, patch: Partial<ScheduleDraft>) => {
    setScheduleError(null)
    setScheduleNotice(null)
    setScheduleTickResult(null)
    setSchedules((current) =>
      current.map((schedule, itemIndex) =>
        itemIndex === index ? { ...schedule, ...patch } : schedule,
      ),
    )
  }

  const addSchedule = () => {
    setSchedules((current) => {
      const next = [
        ...current,
        {
          ...DEFAULT_SCHEDULE,
          name: `Sync schedule ${current.length + 1}`,
          connector_id: connectors[0]?.id ?? connectors[0]?.name ?? '',
        },
      ]
      setSelectedScheduleIndex(next.length - 1)
      return next
    })
    setScheduleError(null)
    setScheduleNotice(null)
    setScheduleTickResult(null)
  }

  const removeSchedule = (index: number) => {
    setSchedules((current) => current.filter((_, itemIndex) => itemIndex !== index))
    setSelectedScheduleIndex((current) => Math.max(0, Math.min(current, schedules.length - 2)))
    setScheduleNotice(null)
    setScheduleTickResult(null)
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const payload = await saveIntegratorConnectors(connectors.map(draftToConnector))
      setConnectors(payload.connectors.map(toDraft))
      setSupportedTypes(payload.supported_types.length > 0 ? payload.supported_types : supportedTypes)
      setPersistence(payload.persistence)
      setSelectedIndex((index) => Math.max(0, Math.min(index, payload.connectors.length - 1)))
      setTestResult(null)
      setNotice('Integration connector configuration saved')
      void loadAuditEvents()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to save integration connectors'))
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!selectedConnector) return
    setTesting(true)
    setError(null)
    setNotice(null)
    setTestResult(null)
    try {
      const payload = await testIntegratorConnector(draftToConnector(selectedConnector))
      setTestResult(payload)
      setNotice(`Connector test ${payload.status}`)
      void loadAuditEvents()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to test integration connector'))
    } finally {
      setTesting(false)
    }
  }

  const handleRotateCredentials = async () => {
    if (!selectedConnector) return
    setRotatingCredentials(true)
    setError(null)
    setNotice(null)
    setRotationResult(null)
    try {
      const settings = credentialMode === 'fields'
        ? buildCredentialPatchFromFields(credentialFormValues, selectedCredentialTemplate.fields)
        : parseCredentialsPatchJson(credentialPatchJson)
      const payload = await rotateIntegratorConnectorCredentials(connectorIdentifier(selectedConnector), { settings })
      setRotationResult(payload)
      setConnectors((current) =>
        current.map((connector, index) => (index === selectedIndex ? toDraft(payload.connector) : connector)),
      )
      setCredentialFormValues({ ...EMPTY_CREDENTIAL_FORM })
      setCredentialPatchJson(DEFAULT_CREDENTIAL_PATCH_JSON)
      setNotice(`Connector credentials ${payload.status}`)
      void loadAuditEvents()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to rotate connector credentials'))
    } finally {
      setRotatingCredentials(false)
    }
  }

  const handleProbeConnector = async () => {
    if (!selectedConnector) return
    setProbingConnector(true)
    setError(null)
    setNotice(null)
    setProbeResult(null)
    try {
      const mode = externalProbeEnabled ? 'external' : 'static'
      const payload = await probeIntegratorConnector(connectorIdentifier(selectedConnector), {
        mode,
        ...(mode === 'external'
          ? { timeout_seconds: clampExternalProbeTimeout(externalProbeTimeoutSeconds) }
          : {}),
      })
      setProbeResult(payload)
      setConnectors((current) =>
        current.map((connector, index) => (index === selectedIndex ? toDraft(payload.connector) : connector)),
      )
      setNotice(`Connector probe ${payload.status}`)
      void loadAuditEvents()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to probe integration connector'))
    } finally {
      setProbingConnector(false)
    }
  }

  const handleSaveSchedules = async () => {
    const validationErrors = scheduleValidationMessages(schedules)
    if (validationErrors.length > 0) {
      setScheduleError(validationErrors[0])
      setScheduleNotice(null)
      return
    }
    setScheduleSaving(true)
    setScheduleError(null)
    setScheduleNotice(null)
    try {
      const payload = await saveIntegratorSchedules(schedules.map(draftToSchedule))
      setSchedules(payload.schedules)
      setSelectedScheduleIndex((index) => Math.max(0, Math.min(index, payload.schedules.length - 1)))
      setScheduleNotice('Integration schedules saved')
    } catch (err) {
      setScheduleError(err instanceof Error ? err.message : String(err || 'Failed to save integration schedules'))
    } finally {
      setScheduleSaving(false)
    }
  }

  const handleTriggerSchedule = async (schedule: ScheduleDraft) => {
    const scheduleId = schedule.schedule_id?.trim()
    if (!scheduleId) {
      setScheduleError('Save the schedule before triggering it manually.')
      return
    }
    setTriggeringScheduleId(scheduleId)
    setScheduleError(null)
    setScheduleNotice(null)
    try {
      const payload = await triggerIntegratorSchedule(scheduleId)
      await loadSchedules()
      setScheduleNotice(`Schedule trigger ${payload.status}`)
    } catch (err) {
      setScheduleError(err instanceof Error ? err.message : String(err || 'Failed to trigger integration schedule'))
    } finally {
      setTriggeringScheduleId(null)
    }
  }

  const handleDryRunScheduleTick = async () => {
    setScheduleTicking(true)
    setScheduleError(null)
    setScheduleNotice(null)
    setScheduleTickResult(null)
    try {
      // The settings UI intentionally scans only in dry-run mode; real dispatch belongs to the scheduler.
      const payload = await triggerIntegratorScheduleTick(true)
      setScheduleTickResult(payload)
      setScheduleNotice(`Dry-run tick scanned ${payload.checked} schedules`)
    } catch (err) {
      setScheduleError(err instanceof Error ? err.message : String(err || 'Failed to scan integration schedules'))
    } finally {
      setScheduleTicking(false)
    }
  }

  const handleMcpRuntimePing = async () => {
    setMcpPinging(true)
    setMcpError(null)
    setMcpNotice(null)
    try {
      const payload = await getMcpRuntimeHealth()
      setMcpRuntimeHealth(payload)
      setMcpNotice(`MCP runtime health ${payload.status}`)
    } catch (err) {
      setMcpError(err instanceof Error ? err.message : String(err || 'Failed to refresh MCP runtime health'))
    } finally {
      setMcpPinging(false)
    }
  }

  const handleMcpHotUpdate = async () => {
    if (!mcpConfig) return
    setMcpHotUpdating(true)
    setMcpError(null)
    setMcpNotice(null)
    try {
      const payload = await saveMcpConfig({ servers: mcpConfig.servers })
      setMcpConfig(payload)
      setMcpNotice('MCP configuration hot update applied')
      void handleMcpRuntimePing()
    } catch (err) {
      setMcpError(err instanceof Error ? err.message : String(err || 'Failed to hot update MCP configuration'))
    } finally {
      setMcpHotUpdating(false)
    }
  }

  return (
    <div className="space-y-4" data-testid="settings-integrators-panel">
      <div
        className="rounded-lg border border-bg-border bg-bg-tertiary/20 p-3"
        data-testid="settings-mcp-productization-panel"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h4 className="flex items-center gap-2 text-sm font-medium text-text-primary">
              <Activity size={14} className="text-accent-blue" />
              MCP connectors
            </h4>
            <p className="mt-1 text-xs text-text-secondary">Marketplace catalog, hot update, and runtime health.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void loadMcpProductization()}
              loading={mcpLoading}
              data-testid="settings-mcp-refresh"
            >
              <RefreshCw size={12} />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleMcpRuntimePing()}
              loading={mcpPinging}
              data-testid="settings-mcp-runtime-ping"
            >
              <Activity size={12} />
              Runtime
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => void handleMcpHotUpdate()}
              loading={mcpHotUpdating}
              disabled={!mcpConfig}
              data-testid="settings-mcp-hot-update"
            >
              <Save size={12} />
              Hot update
            </Button>
          </div>
        </div>

        {mcpNotice && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-xs text-accent-green">
            <CheckCircle size={13} />
            {mcpNotice}
          </div>
        )}

        {mcpError && (
          <div
            className="mt-3 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
            data-testid="settings-mcp-error"
          >
            {mcpError}
          </div>
        )}

        <div className="mt-3 grid gap-2 rounded-lg border border-bg-border bg-bg-secondary/30 px-3 py-2 text-[11px] text-text-secondary sm:grid-cols-4 xl:grid-cols-8">
          <span>Total: <b className="text-text-primary">{mcpMarketplaceSummary.total}</b></span>
          <span>Enabled: <b className="text-text-primary">{mcpMarketplaceSummary.enabled}</b></span>
          <span>Healthy: <b className="text-text-primary">{mcpMarketplaceSummary.healthy}</b></span>
          <span>Approval: <b className="text-text-primary">{mcpMarketplaceSummary.approval}</b></span>
          <span>Builtin: <b className="text-text-primary">{mcpMarketplaceSummary.builtin}</b></span>
          <span>Custom: <b className="text-text-primary">{mcpMarketplaceSummary.custom}</b></span>
          <span>Categories: <b className="text-text-primary">{mcpMarketplaceSummary.categories}</b></span>
          <span>Runtime: <b className="text-text-primary">{mcpRuntimeHealth?.status ?? '-'}</b></span>
        </div>

        {mcpRuntimeHealth?.summary.alert_count ? (
          <div
            className="mt-3 rounded-lg border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs text-amber-200"
            data-testid="settings-mcp-runtime-alert"
          >
            Runtime alerts: {mcpRuntimeHealth.summary.alert_count}. Unhealthy:{' '}
            {mcpRuntimeHealth.summary.unhealthy_connectors.join(', ') || '-'}
          </div>
        ) : null}

        <div
          className="mt-3 flex flex-wrap gap-2"
          data-testid="settings-mcp-marketplace-categories"
        >
          <button
            type="button"
            onClick={() => setMcpMarketplaceCategoryId('all')}
            className={`rounded-md border px-2.5 py-1 text-left text-[11px] transition ${
              mcpMarketplaceCategoryId === 'all'
                ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                : 'border-bg-border bg-bg-secondary/30 text-text-secondary hover:text-text-primary'
            }`}
            data-testid="settings-mcp-marketplace-category-all"
          >
            All {mcpMarketplaceSummary.total}
          </button>
          {mcpMarketplaceCategories.map((category) => (
            <button
              key={category.id}
              type="button"
              onClick={() => setMcpMarketplaceCategoryId(category.id)}
              className={`rounded-md border px-2.5 py-1 text-left text-[11px] transition ${
                mcpMarketplaceCategoryId === category.id
                  ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                  : 'border-bg-border bg-bg-secondary/30 text-text-secondary hover:text-text-primary'
              }`}
              data-testid={`settings-mcp-marketplace-category-${category.id}`}
            >
              {category.label} {category.healthy}/{category.total} healthy
              {category.requires_approval ? `, approval ${category.requires_approval}` : ''}
            </button>
          ))}
        </div>

        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {visibleMcpConnectors.map((connector) => (
            <div
              key={connector.name}
              className="rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2"
              data-testid="settings-mcp-marketplace-row"
              data-connector-name={connector.name}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate text-xs font-medium text-text-primary">
                  {connector.label || connector.name}
                </span>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${mcpConnectorTone(connector)}`}>
                  {mcpConnectorLabel(connector)}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-secondary">
                <span>{connector.category || 'custom'}</span>
                <span>{connector.transport || 'stdio'}</span>
                <span>{connector.risk_level || 'medium'}</span>
                <span>{connector.source || mcpConfig?.source || '-'}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-text-primary">
          <PlugZap size={14} className="text-accent-blue" />
          Integration connectors
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void loadConnectors()}
            loading={loading}
            data-testid="settings-integrators-refresh"
          >
            <RefreshCw size={12} />
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => void handleSave()}
            loading={saving}
            data-testid="settings-integrators-save"
          >
            <Save size={12} />
            Save
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleTest()}
            loading={testing}
            disabled={!selectedConnector}
            data-testid="settings-integrator-test"
          >
            <Zap size={12} />
            Test
          </Button>
        </div>
      </div>

      <div className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-xs text-text-secondary sm:grid-cols-4">
        <span>Total: <b className="text-text-primary">{connectors.length}</b></span>
        <span>Configured: <b className="text-text-primary">{configuredCount}</b></span>
        <span>Approved: <b className="text-text-primary">{approvedCount}</b></span>
        <span>Store: <b className="text-text-primary">{persistence?.enabled ? persistence.config_key : '-'}</b></span>
      </div>

      {notice && (
        <div className="flex items-center gap-2 rounded-lg border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-xs text-accent-green">
          <CheckCircle size={13} />
          {notice}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
          {error}
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.35fr)]">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-secondary">Connectors</span>
            <Button variant="outline" size="sm" onClick={addConnector} data-testid="settings-integrator-add">
              <Plus size={12} />
              Add
            </Button>
          </div>

          {connectors.length === 0 && !loading && (
            <button
              type="button"
              onClick={addConnector}
              className="w-full rounded-lg border border-dashed border-bg-border bg-bg-tertiary/20 px-3 py-6 text-center text-xs text-text-secondary hover:border-accent-blue/40 hover:text-text-primary"
            >
              Add the first webhook connector
            </button>
          )}

          {connectors.map((connector, index) => (
            <button
              key={`${connector.id || connector.name || connector.type}-${index}`}
              type="button"
              onClick={() => setSelectedIndex(index)}
              data-testid="settings-integrator-row"
              className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                selectedIndex === index
                  ? 'border-accent-blue/50 bg-accent-blue/10'
                  : 'border-bg-border bg-bg-tertiary/30 hover:border-accent-blue/30'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate text-sm font-medium text-text-primary">
                  {displayName(connector)}
                </span>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${statusTone(connector)}`}>
                  {statusLabel(connector)}
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-text-secondary">
                <span>{connector.type}</span>
                <span>{hasConfiguredEndpoint(connector) ? 'configured' : 'missing endpoint'}</span>
              </div>
            </button>
          ))}
        </div>

        <div className="rounded-lg border border-bg-border bg-bg-tertiary/20 p-3">
          {selectedConnector ? (
            <div className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h4 className="text-sm font-medium text-text-primary">Connector details</h4>
                  <p className="mt-1 text-xs text-text-secondary">Sensitive values remain redacted after save.</p>
                </div>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => removeConnector(selectedIndex)}
                  data-testid="settings-integrator-remove"
                >
                  <Trash2 size={12} />
                  Remove
                </Button>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1 text-xs text-text-secondary">
                  Name
                  <input
                    className="input-base h-9 w-full"
                    value={selectedConnector.name ?? ''}
                    onChange={(event) => updateConnector(selectedIndex, { name: event.target.value })}
                    data-testid="settings-integrator-name"
                  />
                </label>
                <label className="space-y-1 text-xs text-text-secondary">
                  Type
                  <select
                    className="input-base h-9 w-full"
                    value={selectedConnector.type}
                    onChange={(event) => updateConnector(selectedIndex, { type: event.target.value })}
                    data-testid="settings-integrator-type"
                  >
                    {supportedTypes.map((type) => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="space-y-1 text-xs text-text-secondary">
                Description
                <input
                  className="input-base h-9 w-full"
                  value={selectedConnector.description ?? ''}
                  onChange={(event) => updateConnector(selectedIndex, { description: event.target.value })}
                />
              </label>

              <div className="flex flex-wrap gap-3">
                <label className="inline-flex items-center gap-2 text-xs text-text-secondary">
                  <input
                    type="checkbox"
                    checked={selectedConnector.enabled}
                    onChange={(event) => updateConnector(selectedIndex, { enabled: event.target.checked })}
                    data-testid="settings-integrator-enabled"
                  />
                  Enabled
                </label>
                <label className="inline-flex items-center gap-2 text-xs text-text-secondary">
                  <input
                    type="checkbox"
                    checked={selectedConnector.approved}
                    onChange={(event) => updateConnector(selectedIndex, { approved: event.target.checked })}
                    data-testid="settings-integrator-approved"
                  />
                  Approved for execution
                </label>
              </div>

              <label className="space-y-1 text-xs text-text-secondary">
                Settings JSON
                <textarea
                  className="input-base min-h-[12rem] w-full resize-y font-mono text-xs leading-5"
                  value={selectedConnector.settingsJson}
                  onChange={(event) => updateConnector(selectedIndex, { settingsJson: event.target.value })}
                  spellCheck={false}
                  data-testid="settings-integrator-settings-json"
                />
              </label>

              <div
                className="space-y-3 border-t border-bg-border pt-3"
                data-testid="settings-integrator-credentials-panel"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h5 className="text-sm font-medium text-text-primary">Credentials</h5>
                    <p className="mt-1 text-xs text-text-secondary">
                      Rotate common credential fields directly, or switch to JSON patch for advanced changes.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleProbeConnector()}
                      loading={probingConnector}
                      data-testid="settings-integrator-probe"
                    >
                      <Activity size={12} />
                      {externalProbeEnabled ? 'External probe' : 'Static probe'}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleRotateCredentials()}
                      loading={rotatingCredentials}
                      data-testid="settings-integrator-rotate"
                    >
                      <RotateCcw size={12} />
                      Rotate
                    </Button>
                  </div>
                </div>

                <div
                  className="grid gap-3 rounded-lg border border-bg-border bg-bg-secondary/30 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_8rem]"
                  data-testid="settings-integrator-external-probe-controls"
                >
                  <label className="flex items-start gap-2 text-xs text-text-secondary">
                    <input
                      type="checkbox"
                      className="mt-0.5"
                      checked={externalProbeEnabled}
                      onChange={(event) => {
                        setExternalProbeEnabled(event.target.checked)
                        setProbeResult(null)
                      }}
                      data-testid="settings-integrator-external-probe-enabled"
                    />
                    <span>
                      <span className="block font-medium text-text-primary">External probe opt-in</span>
                      <span className="mt-1 block text-[11px] leading-4">
                        Sends one outbound webhook request. Leave off for the default static dry-run.
                      </span>
                    </span>
                  </label>
                  <label className="space-y-1 text-xs text-text-secondary">
                    Timeout seconds
                    <input
                      type="number"
                      min={MIN_EXTERNAL_PROBE_TIMEOUT_SECONDS}
                      max={MAX_EXTERNAL_PROBE_TIMEOUT_SECONDS}
                      step={0.1}
                      className="input-base h-9 w-full"
                      value={externalProbeTimeoutSeconds}
                      disabled={!externalProbeEnabled}
                      onChange={(event) => {
                        setExternalProbeTimeoutSeconds(Number(event.target.value))
                        setProbeResult(null)
                      }}
                      onBlur={() => setExternalProbeTimeoutSeconds((value) => clampExternalProbeTimeout(value))}
                      data-testid="settings-integrator-external-probe-timeout"
                    />
                  </label>
                </div>

                <div className="flex w-full max-w-sm rounded-lg border border-bg-border bg-bg-secondary/40 p-1">
                  {(['fields', 'json'] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      className={`h-8 flex-1 rounded-md px-3 text-xs transition-colors ${
                        credentialMode === mode
                          ? 'bg-accent-blue/20 text-text-primary'
                          : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                      }`}
                      aria-pressed={credentialMode === mode}
                      onClick={() => {
                        setCredentialMode(mode)
                        setRotationResult(null)
                      }}
                      data-testid={`settings-integrator-credential-mode-${mode}`}
                    >
                      {mode === 'fields' ? 'Fields' : 'JSON patch'}
                    </button>
                  ))}
                </div>

                {credentialMode === 'fields' ? (
                  <div className="space-y-3">
                    <div className="space-y-2">
                      <span className="text-xs font-medium text-text-secondary">Quick template</span>
                      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                        {CREDENTIAL_TEMPLATES.map((template) => (
                          <button
                            key={template.id}
                            type="button"
                            className={`min-h-[4.75rem] rounded-lg border px-3 py-2 text-left transition-colors ${
                              credentialTemplateId === template.id
                                ? 'border-accent-blue/50 bg-accent-blue/10'
                                : 'border-bg-border bg-bg-secondary/30 hover:border-accent-blue/30'
                            }`}
                            onClick={() => selectCredentialTemplate(template.id)}
                            data-testid={`settings-integrator-credential-template-${template.id}`}
                          >
                            <span className="block text-xs font-medium text-text-primary">{template.label}</span>
                            <span className="mt-1 block text-[11px] leading-4 text-text-secondary">
                              {template.description}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      {selectedCredentialTemplate.fields.map((field) => {
                        const definition = credentialFieldDefinition(field)
                        return (
                          <label key={field} className="space-y-1 text-xs text-text-secondary">
                            {definition.label}
                            <input
                              type={definition.sensitive ? 'password' : 'text'}
                              className="input-base h-9 w-full"
                              value={credentialFormValues[field]}
                              onChange={(event) => updateCredentialField(field, event.target.value)}
                              placeholder={definition.placeholder}
                              autoComplete="off"
                              data-testid={`settings-integrator-credential-field-${field}`}
                            />
                          </label>
                        )
                      })}
                    </div>

                    <p className="text-[11px] text-text-secondary">
                      Existing credential values are never prefilled. Submitted fields are cleared after rotation.
                    </p>
                  </div>
                ) : (
                  <label className="space-y-1 text-xs text-text-secondary">
                    Credential patch JSON
                    <textarea
                      className="input-base min-h-[7rem] w-full resize-y font-mono text-xs leading-5"
                      value={credentialPatchJson}
                      onChange={(event) => {
                        setCredentialPatchJson(event.target.value)
                        setRotationResult(null)
                      }}
                      spellCheck={false}
                      data-testid="settings-integrator-credential-patch-json"
                    />
                  </label>
                )}

                {rotationResult && (
                  <div
                    className="bg-bg-secondary/40 px-3 py-2 text-xs text-text-secondary"
                    data-testid="settings-integrator-rotation-result"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-text-primary">Rotation {rotationResult.status}</span>
                      <span>{rotationResult.summary.rotated_count} rotated / {rotationResult.summary.preserved_count} preserved</span>
                    </div>
                    <div className="mt-2 grid gap-1 text-[11px] sm:grid-cols-2">
                      <span>
                        Rotated: <b className="text-text-primary">{formatFieldList(rotationResult.rotated_fields)}</b>
                      </span>
                      <span>
                        Preserved: <b className="text-text-primary">{formatFieldList(rotationResult.preserved_fields)}</b>
                      </span>
                    </div>
                    <p className="mt-2 text-[11px] text-text-secondary">
                      Connector settings returned redacted; sensitive input was cleared.
                    </p>
                  </div>
                )}

                {probeResult && (
                  <div
                    className="bg-bg-secondary/40 px-3 py-2 text-xs text-text-secondary"
                    data-testid="settings-integrator-probe-result"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-text-primary">
                        {probeResult.probe.mode === 'external' ? 'External probe' : 'Static dry-run probe'}
                      </span>
                      <span className={probeResult.ok ? 'text-accent-green' : 'text-accent-red'}>
                        {probeResult.status}
                      </span>
                    </div>
                    <div className="mt-2 grid gap-1 text-[11px] sm:grid-cols-2">
                      <span>Mode: <b className="text-text-primary" data-testid="settings-integrator-probe-mode">{probeResult.probe.mode}</b></span>
                      <span>
                        Outbound request:{' '}
                        <b className="text-text-primary" data-testid="settings-integrator-probe-outbound">
                          {probeResult.probe.outbound_request_sent ? 'sent' : 'not sent'}
                        </b>
                      </span>
                      <span>
                        Timeout:{' '}
                        <b className="text-text-primary" data-testid="settings-integrator-probe-timeout">
                          {probeResult.probe.timeout_seconds ?? '-'}s
                        </b>
                      </span>
                      <span>Checks: <b className="text-text-primary">{probeResult.summary.check_count}</b></span>
                      <span>Failures: <b className="text-text-primary">{probeResult.summary.failed_count}</b></span>
                    </div>
                    {safeProbeEntries(probeResult.probe.endpoint).length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5" data-testid="settings-integrator-probe-endpoint">
                        {safeProbeEntries(probeResult.probe.endpoint).map(([key, value]) => (
                          <span key={key} className="rounded-md bg-bg-hover px-2 py-1 text-[11px] text-text-secondary">
                            {key}: {value}
                          </span>
                        ))}
                      </div>
                    )}
                    {safeProbeEntries(probeResult.probe.response).length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5" data-testid="settings-integrator-probe-response">
                        {safeProbeEntries(probeResult.probe.response).map(([key, value]) => (
                          <span key={key} className="rounded-md bg-bg-hover px-2 py-1 text-[11px] text-text-secondary">
                            {key}: {value}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="mt-2 space-y-1">
                      {probeResult.checks.map((check) => (
                        <div
                          key={check.name}
                          className="flex items-start gap-2 text-[11px] text-text-secondary"
                        >
                          <span className={check.ok ? 'text-accent-green' : 'text-accent-red'}>
                            {check.ok ? 'OK' : 'FAIL'}
                          </span>
                          <span>{check.message}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {testResult && (
                <div
                  className="rounded-lg border border-bg-border bg-bg-secondary/40 p-3"
                  data-testid="settings-integrator-test-result"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-medium text-text-primary">Dry-run test</span>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] ${
                      testResult.ok ? 'bg-accent-green/15 text-accent-green' : 'bg-accent-red/15 text-accent-red'
                    }`}>
                      {testResult.status}
                    </span>
                  </div>
                  <div className="mt-2 space-y-1">
                    {testResult.checks.map((check) => (
                      <div
                        key={check.name}
                        className="flex items-start gap-2 text-xs text-text-secondary"
                      >
                        <span className={check.ok ? 'text-accent-green' : 'text-accent-red'}>
                          {check.ok ? 'OK' : 'FAIL'}
                        </span>
                        <span>{check.message}</span>
                      </div>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] text-text-secondary">
                    No outbound request was sent.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="flex min-h-[16rem] items-center justify-center text-xs text-text-secondary">
              {loading ? 'Loading connectors...' : 'No connector selected'}
            </div>
          )}
        </div>
      </div>

      <div
        className="rounded-lg border border-bg-border bg-bg-tertiary/20 p-3"
        data-testid="settings-integrator-schedules-panel"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h4 className="flex items-center gap-2 text-sm font-medium text-text-primary">
              <CalendarClock size={14} className="text-accent-blue" />
              Sync schedules
            </h4>
            <p className="mt-1 text-xs text-text-secondary">Manage scheduled connector syncs without exposing secret settings.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void loadSchedules()}
              loading={scheduleLoading}
              data-testid="settings-integrator-schedules-refresh"
            >
              <RefreshCw size={12} />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleDryRunScheduleTick()}
              loading={scheduleTicking}
              data-testid="settings-integrator-schedule-tick"
            >
              <Play size={12} />
              Scan due
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={addSchedule}
              data-testid="settings-integrator-schedule-add"
            >
              <Plus size={12} />
              Add
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => void handleSaveSchedules()}
              loading={scheduleSaving}
              disabled={scheduleValidationErrors.length > 0}
              data-testid="settings-integrator-schedule-save"
            >
              <Save size={12} />
              Save schedules
            </Button>
          </div>
        </div>

        {scheduleNotice && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-xs text-accent-green">
            <CheckCircle size={13} />
            {scheduleNotice}
          </div>
        )}

        {scheduleError && (
          <div
            className="mt-3 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
            data-testid="settings-integrator-schedule-error"
          >
            {scheduleError}
          </div>
        )}

        {scheduleValidationErrors.length > 0 && !scheduleError && (
          <div
            className="mt-3 rounded-lg border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs text-amber-200"
            data-testid="settings-integrator-schedule-validation"
          >
            {scheduleValidationErrors[0]}
          </div>
        )}

        <div className="mt-3 grid gap-2 rounded-lg border border-bg-border bg-bg-secondary/30 px-3 py-2 text-[11px] text-text-secondary sm:grid-cols-3">
          <span>Total: <b className="text-text-primary">{schedules.length}</b></span>
          <span>
            Automatic dispatch:{' '}
            <b className="text-text-primary" data-testid="settings-integrator-schedule-auto-dispatch">
              {scheduleRuntime ? (scheduleRuntime.automatic_dispatch ? 'On' : 'Off') : '-'}
            </b>
          </span>
          <span>
            Scheduler:{' '}
            <b className="text-text-primary" data-testid="settings-integrator-schedule-mode">
              {scheduleRuntime?.mode ?? '-'}
            </b>
          </span>
        </div>

        {scheduleTickResult && (
          <div
            className="mt-3 grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-[11px] text-text-secondary sm:grid-cols-3"
            data-testid="settings-integrator-schedule-tick-result"
          >
            <span>
              Due:{' '}
              <b className="text-text-primary" data-testid="settings-integrator-schedule-tick-due-count">
                {scheduleTickResult.due_count}
              </b>
            </span>
            <span>
              Skipped:{' '}
              <b className="text-text-primary" data-testid="settings-integrator-schedule-tick-skipped">
                {scheduleTickResult.skipped.disabled + scheduleTickResult.skipped.not_due}
              </b>
            </span>
            <span>
              Mode:{' '}
              <b className="text-text-primary">
                {scheduleTickResult.dry_run ? 'Dry-run' : 'Run'}
              </b>
            </span>
          </div>
        )}

        <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.35fr)]">
          <div className="space-y-2">
            {!scheduleError && schedules.length === 0 && !scheduleLoading && (
              <button
                type="button"
                onClick={addSchedule}
                className="w-full rounded-lg border border-dashed border-bg-border bg-bg-secondary/30 px-3 py-6 text-center text-xs text-text-secondary hover:border-accent-blue/40 hover:text-text-primary"
                data-testid="settings-integrator-schedule-empty"
              >
                Add the first sync schedule
              </button>
            )}

            {schedules.map((schedule, index) => (
              <button
                key={`${schedule.schedule_id || schedule.name || 'schedule'}-${index}`}
                type="button"
                onClick={() => setSelectedScheduleIndex(index)}
                data-testid="settings-integrator-schedule-row"
                className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                  selectedScheduleIndex === index
                    ? 'border-accent-blue/50 bg-accent-blue/10'
                    : 'border-bg-border bg-bg-secondary/40 hover:border-accent-blue/30'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-sm font-medium text-text-primary">
                    {scheduleDisplayName(schedule)}
                  </span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${scheduleStatusTone(schedule)}`}>
                    {scheduleStatusLabel(schedule)}
                  </span>
                </div>
                <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-text-secondary">
                  <span>{schedule.connector_id || 'No connector'}</span>
                  <span>
                    {schedule.cron} / {schedule.interval_minutes}m / {normalizeScheduleTimezone(schedule.timezone)}
                  </span>
                </div>
              </button>
            ))}
          </div>

          <div className="rounded-lg border border-bg-border bg-bg-secondary/30 p-3">
            {selectedSchedule ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h5 className="text-sm font-medium text-text-primary">Schedule details</h5>
                    <p className="mt-1 text-xs text-text-secondary">
                      Settings are preserved by the API and are not rendered here.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleTriggerSchedule(selectedSchedule)}
                      loading={triggeringScheduleId === selectedSchedule.schedule_id}
                      data-testid="settings-integrator-schedule-trigger"
                    >
                      <Play size={12} />
                      Trigger
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => removeSchedule(selectedScheduleIndex)}
                      data-testid="settings-integrator-schedule-remove"
                    >
                      <Trash2 size={12} />
                      Remove
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="space-y-1 text-xs text-text-secondary">
                    Name
                    <input
                      className="input-base h-9 w-full"
                      value={selectedSchedule.name}
                      onChange={(event) => updateSchedule(selectedScheduleIndex, { name: event.target.value })}
                      data-testid="settings-integrator-schedule-name"
                    />
                  </label>
                  <label className="space-y-1 text-xs text-text-secondary">
                    Connector
                    <select
                      className="input-base h-9 w-full"
                      value={selectedSchedule.connector_id}
                      onChange={(event) => updateSchedule(selectedScheduleIndex, { connector_id: event.target.value })}
                      data-testid="settings-integrator-schedule-connector"
                    >
                      <option value="">Select connector</option>
                      {connectors.map((connector, index) => {
                        const connectorId = connector.id || connector.name || connector.type
                        return (
                          <option key={`${connectorId}-${index}`} value={connectorId}>
                            {displayName(connector)}
                          </option>
                        )
                      })}
                    </select>
                  </label>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="space-y-1 text-xs text-text-secondary">
                    Cron
                    <input
                      className="input-base h-9 w-full font-mono"
                      list="integrator-schedule-cron-presets"
                      value={selectedSchedule.cron}
                      onChange={(event) => updateSchedule(selectedScheduleIndex, { cron: event.target.value })}
                      data-testid="settings-integrator-schedule-cron"
                    />
                    <datalist id="integrator-schedule-cron-presets">
                      {SCHEDULE_CRON_PRESETS.map((preset) => (
                        <option key={preset.value} value={preset.value} label={preset.label} />
                      ))}
                    </datalist>
                    <p className="text-[11px] text-text-secondary" data-testid="settings-integrator-schedule-cron-help">
                      5-field cron, macros, and ? in day/weekday fields are supported.
                    </p>
                  </label>
                  <label className="space-y-1 text-xs text-text-secondary">
                    Interval minutes
                    <input
                      type="number"
                      min={MIN_SCHEDULE_INTERVAL_MINUTES}
                      max={MAX_SCHEDULE_INTERVAL_MINUTES}
                      step={1}
                      className="input-base h-9 w-full"
                      value={selectedSchedule.interval_minutes}
                      onChange={(event) => updateSchedule(selectedScheduleIndex, {
                        interval_minutes: Number(event.target.value),
                      })}
                      data-testid="settings-integrator-schedule-interval"
                    />
                  </label>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="space-y-1 text-xs text-text-secondary">
                    Timezone
                    <input
                      className="input-base h-9 w-full"
                      list="integrator-schedule-timezones"
                      value={selectedSchedule.timezone ?? ''}
                      onChange={(event) => updateSchedule(selectedScheduleIndex, { timezone: event.target.value })}
                      data-testid="settings-integrator-schedule-timezone"
                    />
                    <datalist id="integrator-schedule-timezones">
                      {COMMON_TIMEZONES.map((timezone) => (
                        <option key={timezone} value={timezone} />
                      ))}
                    </datalist>
                  </label>
                  <div className="rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-[11px] text-text-secondary">
                    Manual trigger: <b className="text-text-primary">
                      {scheduleRuntime?.manual_trigger_supported === false ? 'Unsupported' : 'Supported'}
                    </b>
                  </div>
                </div>

                <label className="inline-flex items-center gap-2 text-xs text-text-secondary">
                  <input
                    type="checkbox"
                    checked={selectedSchedule.enabled}
                    onChange={(event) => updateSchedule(selectedScheduleIndex, { enabled: event.target.checked })}
                    data-testid="settings-integrator-schedule-enabled"
                  />
                  Enabled
                </label>

                <div className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-[11px] text-text-secondary sm:grid-cols-2">
                  <span>Last run: <b className="text-text-primary">{formatAuditTime(selectedSchedule.last_run_at ?? 0)}</b></span>
                  <span>Next run: <b className="text-text-primary">{formatAuditTime(selectedSchedule.next_run_at ?? 0)}</b></span>
                  <span>
                    Timezone:{' '}
                    <b className="text-text-primary" data-testid="settings-integrator-schedule-timezone-display">
                      {normalizeScheduleTimezone(selectedSchedule.timezone)}
                    </b>
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex min-h-[12rem] items-center justify-center text-xs text-text-secondary">
                {scheduleLoading ? 'Loading schedules...' : 'No schedule selected'}
              </div>
            )}
          </div>
        </div>
      </div>

      <div
        className="rounded-lg border border-bg-border bg-bg-tertiary/20 p-3"
        data-testid="settings-integrator-audit-panel"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h4 className="flex items-center gap-2 text-sm font-medium text-text-primary">
              <History size={14} className="text-accent-blue" />
              Recent audit
            </h4>
            <p className="mt-1 text-xs text-text-secondary">Redacted connector activity from the audit log.</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void loadAuditEvents()}
            loading={auditLoading}
            data-testid="settings-integrator-audit-refresh"
          >
            <RefreshCw size={12} />
            Refresh audit
          </Button>
        </div>

        {auditError && (
          <div
            className="mt-3 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
            data-testid="settings-integrator-audit-error"
          >
            {auditError}
          </div>
        )}

        {!auditError && auditEvents.length === 0 && !auditLoading && (
          <div
            className="mt-3 rounded-lg border border-dashed border-bg-border px-3 py-6 text-center text-xs text-text-secondary"
            data-testid="settings-integrator-audit-empty"
          >
            No audit records yet.
          </div>
        )}

        {!auditError && auditEvents.length > 0 && (
          <div className="mt-3 space-y-2" data-testid="settings-integrator-audit-list">
            {auditEvents.map((event, index) => {
              const details = safeAuditDetails(event.details)
              return (
                <div
                  key={`${event.request_id || event.action}-${event.timestamp}-${index}`}
                  className="rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2"
                  data-testid="settings-integrator-audit-row"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-medium text-text-primary">{event.action || 'integration_event'}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[11px] ${
                          event.result === 'success' || event.result === 'allowed'
                            ? 'bg-accent-green/15 text-accent-green'
                            : event.result === 'failed' || event.result === 'denied'
                              ? 'bg-accent-red/15 text-accent-red'
                              : 'bg-bg-hover text-text-secondary'
                        }`}>
                          {event.result || 'unknown'}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-secondary">
                        <span>{formatAuditTime(event.timestamp)}</span>
                        {event.connector_id && <span>connector: {event.connector_id}</span>}
                        {event.connector_type && <span>type: {event.connector_type}</span>}
                        {event.actor && <span>actor: {event.actor}</span>}
                      </div>
                    </div>
                    {event.request_id && (
                      <span className="shrink-0 text-[11px] text-text-secondary">{event.request_id}</span>
                    )}
                  </div>
                  {details.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {details.map(([key, value]) => (
                        <span
                          key={key}
                          className="rounded-md bg-bg-hover px-2 py-1 text-[11px] text-text-secondary"
                        >
                          {key}: {value}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
