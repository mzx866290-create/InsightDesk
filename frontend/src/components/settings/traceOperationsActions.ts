import {
  clearTraceEvents,
  getTraceEvents,
  type TraceEventsResponse,
  type TraceFilters,
} from '../../api/client'
import { compactTraceFilters } from './traceOperationsModel'

export async function loadTraceEventsState(
  limit: number,
  filters: TraceFilters,
): Promise<TraceEventsResponse> {
  return getTraceEvents(limit, compactTraceFilters(filters))
}

export async function clearTraceEventsState(): Promise<void> {
  await clearTraceEvents()
}
