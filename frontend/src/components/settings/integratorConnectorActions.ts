import {
  getIntegratorConnectors,
  saveIntegratorConnectors,
  testIntegratorConnector,
} from '../../api/client'
import type {
  IntegratorConnectorTestResult,
  IntegratorConnectorsResponse,
} from '../../api/client'
import { draftToConnector } from './integratorConnectorModel'
import type { ConnectorDraft } from './integratorConnectorModel'

export async function loadIntegratorConnectorCatalog(): Promise<IntegratorConnectorsResponse> {
  return getIntegratorConnectors()
}

export async function saveIntegratorConnectorDrafts(
  connectors: ConnectorDraft[],
): Promise<IntegratorConnectorsResponse> {
  return saveIntegratorConnectors(connectors.map(draftToConnector))
}

export async function testIntegratorConnectorDraft(
  connector: ConnectorDraft,
): Promise<IntegratorConnectorTestResult> {
  return testIntegratorConnector(draftToConnector(connector))
}
