import type { IntegratorAuditPanelProps } from './IntegratorAuditPanel'
import type { IntegratorSchedulesPanelProps } from './IntegratorSchedulesPanel'
import type { ConnectorDraft } from './integratorConnectorModel'
import type { UseIntegratorAuditResult } from './useIntegratorAudit'
import type { UseIntegratorSchedulesResult } from './useIntegratorSchedules'

type SchedulesPanelState = Pick<
  UseIntegratorSchedulesResult,
  | 'schedules'
  | 'selectedScheduleIndex'
  | 'selectedSchedule'
  | 'scheduleRuntime'
  | 'scheduleTickResult'
  | 'scheduleValidationErrors'
  | 'scheduleNotice'
  | 'scheduleError'
  | 'scheduleLoading'
  | 'scheduleSaving'
  | 'scheduleTicking'
  | 'triggeringScheduleId'
  | 'addSchedule'
  | 'setSelectedScheduleIndex'
  | 'removeSchedule'
  | 'updateSchedule'
>

type AuditPanelState = Pick<
  UseIntegratorAuditResult,
  | 'auditEvents'
  | 'auditError'
  | 'auditLoading'
>

export interface BuildSchedulesPanelPropsParams {
  connectors: ConnectorDraft[]
  scheduleController: SchedulesPanelState
  onRefreshSchedules: () => void
  onDryRunScheduleTick: () => void
  onSaveSchedules: () => void
  onTriggerSchedule: IntegratorSchedulesPanelProps['onTriggerSchedule']
}

export function buildSchedulesPanelProps({
  connectors,
  scheduleController,
  onRefreshSchedules,
  onDryRunScheduleTick,
  onSaveSchedules,
  onTriggerSchedule,
}: BuildSchedulesPanelPropsParams): IntegratorSchedulesPanelProps {
  return {
    schedules: scheduleController.schedules,
    selectedScheduleIndex: scheduleController.selectedScheduleIndex,
    selectedSchedule: scheduleController.selectedSchedule,
    connectors,
    scheduleRuntime: scheduleController.scheduleRuntime,
    scheduleTickResult: scheduleController.scheduleTickResult,
    scheduleValidationErrors: scheduleController.scheduleValidationErrors,
    scheduleNotice: scheduleController.scheduleNotice,
    scheduleError: scheduleController.scheduleError,
    scheduleLoading: scheduleController.scheduleLoading,
    scheduleSaving: scheduleController.scheduleSaving,
    scheduleTicking: scheduleController.scheduleTicking,
    triggeringScheduleId: scheduleController.triggeringScheduleId,
    onRefreshSchedules,
    onDryRunScheduleTick,
    onAddSchedule: scheduleController.addSchedule,
    onSaveSchedules,
    onSelectSchedule: scheduleController.setSelectedScheduleIndex,
    onRemoveSchedule: scheduleController.removeSchedule,
    onUpdateSchedule: scheduleController.updateSchedule,
    onTriggerSchedule,
  }
}

export interface BuildAuditPanelPropsParams {
  auditController: AuditPanelState
  onRefreshAudit: () => void
}

export function buildAuditPanelProps({
  auditController,
  onRefreshAudit,
}: BuildAuditPanelPropsParams): IntegratorAuditPanelProps {
  return {
    auditEvents: auditController.auditEvents,
    auditError: auditController.auditError,
    auditLoading: auditController.auditLoading,
    onRefreshAudit,
  }
}
