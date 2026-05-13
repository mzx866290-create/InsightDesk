import {
  MAX_SCHEDULE_INTERVAL_MINUTES,
  MIN_SCHEDULE_INTERVAL_MINUTES,
  type ScheduleDraft,
} from './integratorScheduleSharedModel'
import { scheduleDisplayName } from './integratorScheduleDisplayModel'
import { normalizeScheduleTimezone } from './integratorScheduleNormalizationModel'

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

export function validateScheduleCron(cron: string): string | null {
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

export function validateScheduleInterval(intervalMinutes: number): string | null {
  if (!Number.isInteger(intervalMinutes)) return 'Interval must be a whole number of minutes.'
  if (intervalMinutes < MIN_SCHEDULE_INTERVAL_MINUTES) {
    return `Interval must be at least ${MIN_SCHEDULE_INTERVAL_MINUTES} minutes.`
  }
  if (intervalMinutes > MAX_SCHEDULE_INTERVAL_MINUTES) {
    return `Interval must be no more than ${MAX_SCHEDULE_INTERVAL_MINUTES} minutes.`
  }
  return null
}

export function validateScheduleTimezone(timezone: string | undefined): string | null {
  const value = normalizeScheduleTimezone(timezone)
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: value })
    return null
  } catch {
    return 'Timezone must be a valid IANA timezone such as UTC, Asia/Shanghai, or America/New_York.'
  }
}

export function scheduleValidationMessages(schedules: ScheduleDraft[]): string[] {
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
