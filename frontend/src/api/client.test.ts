import { afterEach, describe, expect, it, vi } from 'vitest'

function jsonResponse(payload: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

async function importClientWithFetch(fetchMock: typeof globalThis.fetch) {
  vi.resetModules()
  vi.stubGlobal('fetch', fetchMock)
  return import('./client')
}

describe('api client security endpoints', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
    window.sessionStorage.clear()
    window.localStorage.clear()
  })

  it('normalizes security status payloads and sends stored API token headers', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        allow_remote_clients: true,
        local_only_mode: false,
        remote_auth_ready: true,
        admin_token_configured: true,
        remote_admin_ready: true,
        auth_token_count: '2',
        configured_roles: ['admin', 404, 'viewer'],
        auth_token_hygiene_healthy: true,
        weak_auth_token_count: '1',
        legacy_auth_token_count: null,
        share_link_secret_healthy: false,
        share_link_secret_uses_default: true,
        share_link_secret_min_length: '16',
        remote_share_ready: false,
        remote_management_rate_limit_enabled: true,
        remote_management_rate_limit_window_seconds: '60',
        remote_management_rate_limit_window_seconds_source: 'default',
        remote_management_rate_limit_max_requests: '120',
        remote_management_rate_limit_max_requests_source: 'env',
        remote_management_rate_limit_scope: 'remote-management',
        remote_management_rate_limit_storage: 'memory',
        remote_management_rate_limit_path_prefixes: ['/api/security/', 404, '/api/auth/'],
        remote_management_rate_limit_response_headers: [
          'X-RateLimit-Limit',
          7,
          'Retry-After',
        ],
        remote_management_rate_limit_tracked_principal_count: '3',
        remote_management_rate_limit_active_request_count: '9',
        remote_management_rate_limit_blocked_count: '2',
        remote_management_rate_limit_last_blocked_at: '1715000123.5',
        remote_management_rate_limit_next_reset_after_seconds: '45',
        share_link_ttl_seconds: '604800',
        share_link_ttl_hours: '168',
        cors_allow_credentials: false,
        cors_allowed_origins: ['https://app.example.com', 7],
        request_id_header: 'X-Request-ID',
        process_time_header: 'X-Process-Time-Ms',
        security_audit_storage: 'sqlite',
        security_audit_history_limit: '1000',
        security_audit_history_limit_source: 'default',
        security_audit_persisted_count: '9',
        security_audit_memory_window_limit: '500',
        chat_file_limits: {
          max_count: '6',
          max_bytes: '10485760',
        },
        document_upload_limits: {
          max_count: '12',
          max_file_bytes: '52428800',
        },
      }),
    ) as unknown as typeof globalThis.fetch

    const client = await importClientWithFetch(fetchMock)
    client.saveApiToken(' test-token ')

    await expect(client.getSecurityStatus()).resolves.toMatchObject({
      allow_remote_clients: true,
      auth_token_count: 2,
      configured_roles: ['admin', 'viewer'],
      weak_auth_token_count: 1,
      legacy_auth_token_count: 0,
      share_link_secret_healthy: false,
      share_link_secret_uses_default: true,
      share_link_secret_min_length: 16,
      remote_management_rate_limit_window_seconds: 60,
      remote_management_rate_limit_max_requests: 120,
      remote_management_rate_limit_scope: 'remote-management',
      remote_management_rate_limit_storage: 'memory',
      remote_management_rate_limit_path_prefixes: ['/api/security/', '/api/auth/'],
      remote_management_rate_limit_response_headers: [
        'X-RateLimit-Limit',
        'Retry-After',
      ],
      remote_management_rate_limit_tracked_principal_count: 3,
      remote_management_rate_limit_active_request_count: 9,
      remote_management_rate_limit_blocked_count: 2,
      remote_management_rate_limit_last_blocked_at: 1715000123.5,
      remote_management_rate_limit_next_reset_after_seconds: 45,
      cors_allowed_origins: ['https://app.example.com'],
      chat_file_limits: {
        max_count: 6,
        max_bytes: 10485760,
      },
      document_upload_limits: {
        max_count: 12,
        max_file_bytes: 52428800,
      },
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = vi.mocked(fetchMock).mock.calls[0]
    expect(url).toBe('/api/security/status')
    const headers = init?.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer test-token')
    expect(headers.get('X-API-Token')).toBe('test-token')
  })

  it('uses backend error detail when security status fails', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ detail: 'Security status unavailable' }, { status: 503 }),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)

    await expect(client.getSecurityStatus()).rejects.toThrow('Security status unavailable')
  })

  it('loads provider catalog without requiring an API token header', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        providers: [
          {
            id: 'ollama',
            connection_type: 'ollama',
            aliases: ['local', 'ollama'],
            capabilities: ['chat'],
            default_base_url: 'http://localhost:11434',
            default_model: 'qwen3.5-2B:latest',
            base_url_env_keys: ['OLLAMA_BASE_URL'],
            model_env_keys: ['OLLAMA_MODEL'],
          },
        ],
        default_provider: 'ollama',
        total: 1,
      }),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)

    await expect(client.getProviderCatalog()).resolves.toMatchObject({
      default_provider: 'ollama',
      total: 1,
      providers: [
        {
          id: 'ollama',
          connection_type: 'ollama',
          capabilities: ['chat'],
        },
      ],
    })

    const [url, init] = vi.mocked(fetchMock).mock.calls[0]
    expect(url).toBe('/api/providers')
    expect(init?.headers).toBeUndefined()
  })

  it('loads agent catalog with API token headers for remote mode', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        agents: [
          {
            name: 'research',
            description: 'Research agent',
            capabilities: ['research'],
            metadata: {},
          },
          {
            name: 'support_triage',
            description: 'Support plugin',
            capabilities: ['support_triage'],
            metadata: { plugin: true, source: 'plugin_manifest' },
          },
        ],
        summary: { total: 2, builtin: 1, plugin: 1 },
        plugin_manifests: {
          enabled: true,
          directory_count: 1,
          scanned_count: 2,
          loaded_count: 1,
          issue_count: 1,
          issues: [
            {
              file: 'config/agent_plugins/bad.json',
              code: 'invalid_manifest',
              message: 'bad manifest',
            },
          ],
        },
        marketplace: {
          templates: [
            {
              name: 'support_triage',
              description: 'Support template',
              capabilities: ['support_triage'],
              category: 'operations',
              risk_level: 'high',
              requires_approval: true,
              approval_reason: 'Can inspect support context.',
              source: 'builtin',
              installed: true,
              template: true,
              manifest: {
                enabled: true,
                name: 'support_triage',
                description: 'Support template',
                capabilities: ['support_triage'],
                risk_level: 'high',
              },
            },
          ],
          summary: { total: 1, installed: 1, available: 0, categories: 1, issue_count: 0 },
          issues: [],
        },
      }),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)
    client.saveApiToken('agent-token')

    await expect(client.getAgentCatalog()).resolves.toMatchObject({
      summary: { total: 2, builtin: 1, plugin: 1 },
      plugin_manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 2,
        loaded_count: 1,
        issue_count: 1,
      },
      agents: [
        { name: 'research', capabilities: ['research'] },
        { name: 'support_triage', metadata: { plugin: true } },
      ],
      marketplace: {
        summary: { total: 1, installed: 1 },
        templates: [
          {
            name: 'support_triage',
            installed: true,
            manifest: { name: 'support_triage', risk_level: 'high' },
          },
        ],
      },
    })

    const [url, init] = vi.mocked(fetchMock).mock.calls[0]
    expect(url).toBe('/api/agents/catalog')
    const headers = init?.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer agent-token')
    expect(headers.get('X-API-Token')).toBe('agent-token')
  })

  it('installs Agent plugin manifests through the admin endpoint without executing entrypoints', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        agents: [
          {
            name: 'support_triage',
            description: 'Support triage plugin',
            capabilities: ['support_triage'],
            metadata: {
              plugin: true,
              source: 'plugin_manifest',
              risk_level: 'high',
              requires_approval: true,
            },
          },
        ],
        summary: { total: 1, builtin: 0, plugin: 1 },
        plugin_manifests: {
          enabled: true,
          directory_count: 1,
          scanned_count: 1,
          loaded_count: 1,
          issue_count: 0,
          issues: [],
        },
        installed: {
          name: 'support_triage',
          agent: {
            name: 'support_triage',
            description: 'Support triage plugin',
            capabilities: ['support_triage'],
            metadata: {
              plugin: true,
              source: 'plugin_manifest',
            },
          },
          manifest_path: 'config/agent_plugins/support_triage.json',
          executed_entrypoint: false,
        },
      }),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)
    client.saveApiToken('agent-admin-token')

    await expect(
      client.installAgentPluginManifest({
        manifest: {
          name: 'support_triage',
          version: '1.0.0',
          description: 'Support triage plugin',
          capabilities: ['support_triage'],
          output_prefix: 'Support triage completed',
          risk_level: 'high',
          requires_approval: true,
          approval_reason: 'Can classify customer support queues.',
          metadata: { owner: 'ops', entrypoint: 'should-not-run' },
        },
      }),
    ).resolves.toMatchObject({
      summary: { total: 1, plugin: 1 },
      installed: {
        name: 'support_triage',
        manifest_path: 'config/agent_plugins/support_triage.json',
        executed_entrypoint: false,
        agent: {
          name: 'support_triage',
          capabilities: ['support_triage'],
        },
      },
    })

    const [url, init] = vi.mocked(fetchMock).mock.calls[0]
    expect(url).toBe('/api/agents/plugins/install')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(JSON.stringify({
      manifest: {
        name: 'support_triage',
        version: '1.0.0',
        description: 'Support triage plugin',
        capabilities: ['support_triage'],
        output_prefix: 'Support triage completed',
        risk_level: 'high',
        requires_approval: true,
        approval_reason: 'Can classify customer support queues.',
        metadata: { owner: 'ops', entrypoint: 'should-not-run' },
      },
    }))
    const headers = init?.headers as Headers
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Authorization')).toBe('Bearer agent-admin-token')
    expect(headers.get('X-API-Token')).toBe('agent-admin-token')
  })

  it('uninstalls Agent plugin manifests through the admin endpoint and normalizes the response', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        agents: [],
        summary: { total: 0, builtin: 0, plugin: 0 },
        plugin_manifests: {
          enabled: true,
          directory_count: 1,
          scanned_count: 1,
          loaded_count: 0,
          issue_count: 0,
          issues: [],
        },
        uninstalled: {
          name: 'support_triage',
          manifest_path: 'config/agent_plugins/support_triage.json',
          deleted_manifest: true,
          existed: true,
        },
      }),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)
    client.saveApiToken('agent-admin-token')

    await expect(client.uninstallAgentPluginManifest('support_triage')).resolves.toMatchObject({
      summary: { total: 0, plugin: 0 },
      uninstalled: {
        name: 'support_triage',
        manifest_path: 'config/agent_plugins/support_triage.json',
        deleted_manifest: true,
        existed: true,
      },
    })

    const [url, init] = vi.mocked(fetchMock).mock.calls[0]
    expect(url).toBe('/api/agents/plugins/support_triage')
    expect(init?.method).toBe('DELETE')
    const headers = init?.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer agent-admin-token')
    expect(headers.get('X-API-Token')).toBe('agent-admin-token')
  })

  it('loads delivery template catalog and normalizes manifest diagnostics', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        templates: [
          {
            id: 'board_deck',
            name: 'Board Deck',
            description: 'Board-ready presentation.',
            artifact_type: 'deck',
            category: 'presentation',
            tags: ['deck', 'pptx'],
            target_format: 'pptx',
            preview: 'Cover → Insights',
            suggested_options: { target_slide_count: 8 },
            metadata: { source: 'builtin' },
          },
        ],
        summary: { total: 1, builtin: 1, manifest: 0, report: 0, deck: 1 },
        manifests: {
          enabled: true,
          directory_count: 1,
          scanned_count: 1,
          loaded_count: 0,
          issue_count: 1,
          issues: [
            {
              file: 'config/delivery_templates/bad.json',
              code: 'invalid_manifest',
              message: 'bad template',
            },
          ],
        },
      }),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)

    await expect(client.getDeliveryTemplateCatalog()).resolves.toMatchObject({
      summary: { total: 1, deck: 1 },
      manifests: { scanned_count: 1, issue_count: 1 },
      templates: [{ id: 'board_deck', artifact_type: 'deck' }],
    })

    const [url] = vi.mocked(fetchMock).mock.calls[0]
    expect(url).toBe('/api/delivery-templates/catalog')
  })

  it('installs and uninstalls delivery template manifests through admin endpoints', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          templates: [
            {
              id: 'sales_readout',
              name: 'Sales Readout',
              description: 'Sales team readout deck.',
              artifact_type: 'deck',
              category: 'sales',
              tags: ['sales', 'deck'],
              target_format: 'pptx',
              preview: 'Pipeline -> Risks',
              suggested_options: { target_slide_count: 6 },
              metadata: { manifest: true, source: 'template_manifest' },
            },
          ],
          summary: { total: 1, builtin: 0, manifest: 1, report: 0, deck: 1 },
          manifests: { enabled: true, directory_count: 1, scanned_count: 1, loaded_count: 1, issue_count: 0, issues: [] },
          installed: {
            id: 'sales_readout',
            manifest_path: 'config/delivery_templates/sales_readout.json',
            executed_template_code: false,
          },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          templates: [],
          summary: { total: 0, builtin: 0, manifest: 0, report: 0, deck: 0 },
          manifests: { enabled: true, directory_count: 1, scanned_count: 0, loaded_count: 0, issue_count: 0, issues: [] },
          uninstalled: {
            id: 'sales_readout',
            manifest_path: 'config/delivery_templates/sales_readout.json',
            deleted_manifest: true,
            existed: true,
          },
        }),
      ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)
    client.saveApiToken('template-admin-token')

    await expect(
      client.installDeliveryTemplateManifest({
        manifest: {
          id: 'sales_readout',
          name: 'Sales Readout',
          description: 'Sales team readout deck.',
          artifact_type: 'deck',
          tags: ['sales', 'deck'],
          target_format: 'pptx',
        },
      }),
    ).resolves.toMatchObject({
      installed: {
        id: 'sales_readout',
        executed_template_code: false,
      },
    })
    await expect(client.uninstallDeliveryTemplateManifest('sales_readout')).resolves.toMatchObject({
      uninstalled: {
        id: 'sales_readout',
        deleted_manifest: true,
      },
    })

    const [installUrl, installInit] = vi.mocked(fetchMock).mock.calls[0]
    expect(installUrl).toBe('/api/delivery-templates/install')
    expect(installInit?.method).toBe('POST')
    expect(installInit?.body).toBe(JSON.stringify({
      manifest: {
        id: 'sales_readout',
        name: 'Sales Readout',
        description: 'Sales team readout deck.',
        artifact_type: 'deck',
        tags: ['sales', 'deck'],
        target_format: 'pptx',
      },
    }))
    const installHeaders = installInit?.headers as Headers
    expect(installHeaders.get('Authorization')).toBe('Bearer template-admin-token')

    const [deleteUrl, deleteInit] = vi.mocked(fetchMock).mock.calls[1]
    expect(deleteUrl).toBe('/api/delivery-templates/sales_readout')
    expect(deleteInit?.method).toBe('DELETE')
  })

  it('sends stored API token headers for report generation requests', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        markdown: '# Report',
        title: 'Report',
        artifact_id: 'artifact-report-1',
      }),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)
    client.saveApiToken('report-token')

    await expect(
      client.generateSessionReport('session-1', {
        answer_group_id: 'answer-group-1',
        panel_id: 'panel-1',
      }),
    ).resolves.toMatchObject({
      markdown: '# Report',
      title: 'Report',
      artifact_id: 'artifact-report-1',
    })

    const [reportUrl, reportInit] = vi.mocked(fetchMock).mock.calls[0]
    expect(reportUrl).toBe('/api/reports/generate')
    expect(reportInit?.method).toBe('POST')
    expect(reportInit?.body).toBe(JSON.stringify({
      session_id: 'session-1',
      answer_group_id: 'answer-group-1',
      panel_id: 'panel-1',
    }))
    const headers = reportInit?.headers as Headers
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Authorization')).toBe('Bearer report-token')
    expect(headers.get('X-API-Token')).toBe('report-token')
  })

  it('installs MCP marketplace manifests through the admin endpoint without executing commands', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        connectors: [
          {
            name: 'fetch',
            label: 'Fetch',
            description: 'HTTP fetch connector',
            category: 'web',
            builtin: false,
            transport: 'stdio',
            source: 'config',
          },
        ],
        config: {
          servers: {
            fetch: {
              transport: 'stdio',
              command: 'npx',
              args: ['-y', '@modelcontextprotocol/server-fetch'],
            },
          },
        },
        servers: {
          fetch: {
            transport: 'stdio',
            command: 'npx',
            args: ['-y', '@modelcontextprotocol/server-fetch'],
          },
        },
        default_enabled: [],
        persistence: {
          enabled: true,
          config_key: 'mcp_servers.json',
        },
        sensitive_fields_redacted: true,
        installed: {
          name: 'fetch',
          connector: {
            name: 'fetch',
            label: 'Fetch',
            description: 'HTTP fetch connector',
            category: 'web',
            builtin: false,
            transport: 'stdio',
            source: 'config',
          },
          executed_install_command: false,
        },
      }),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)
    client.saveApiToken('admin-token')

    await expect(
      client.installMcpConnectorManifest({
        manifest: {
          name: 'fetch',
          version: '1.0.0',
          transport: 'stdio',
          install_command: 'npx -y @modelcontextprotocol/server-fetch',
          scopes: ['network:read'],
          risk_level: 'medium',
        },
      }),
    ).resolves.toMatchObject({
      default_enabled: [],
      sensitive_fields_redacted: true,
      installed: {
        name: 'fetch',
        executed_install_command: false,
        connector: {
          name: 'fetch',
          transport: 'stdio',
        },
      },
    })

    const [url, init] = vi.mocked(fetchMock).mock.calls[0]
    expect(url).toBe('/api/connectors/mcp/marketplace/install')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(JSON.stringify({
      manifest: {
        name: 'fetch',
        version: '1.0.0',
        transport: 'stdio',
        install_command: 'npx -y @modelcontextprotocol/server-fetch',
        scopes: ['network:read'],
        risk_level: 'medium',
      },
    }))
    const headers = init?.headers as Headers
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Authorization')).toBe('Bearer admin-token')
    expect(headers.get('X-API-Token')).toBe('admin-token')
  })

  it('surfaces structured MCP manifest errors from the install endpoint', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(
        {
          detail: {
            code: 'invalid_name',
            field: 'name',
            message: 'MCP connector manifest name must be 1-64 characters and use only letters, numbers, dots, underscores, or hyphens',
          },
        },
        { status: 400 },
      ),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)

    await expect(
      client.installMcpConnectorManifest({
        manifest: {
          name: 'bad connector',
          transport: 'stdio',
          command: 'npx',
        },
      }),
    ).rejects.toThrow(
      'name: MCP connector manifest name must be 1-64 characters and use only letters, numbers, dots, underscores, or hyphens (invalid_name)',
    )
  })

  it('normalizes first-party provider aliases and defaults', async () => {
    const client = await importClientWithFetch(
      vi.fn(async () => jsonResponse({})) as unknown as typeof globalThis.fetch,
    )

    expect(client.normalizeConnectionType('claude')).toBe('anthropic')
    expect(client.normalizeConnectionType('gemini')).toBe('google')
    expect(client.normalizeConnectionType(undefined, 'https://api.deepseek.com')).toBe('deepseek')
    expect(client.defaultModelForConnectionType('deepseek')).toBe('deepseek-chat')
    expect(client.defaultBaseUrlForConnectionType('anthropic')).toBe('')
  })

  it('clamps security audit summary requests and filters unsupported categories', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        category: 'unknown',
        categories: ['auth', 'invalid', 'audit'],
        total: '5',
        recent_count: '3',
        window_limit: '500',
        action_counts: { remote_auth_guard: '2' },
        result_counts: { blocked: '1' },
        category_counts: { auth: '2' },
        unknown_action_count: '1',
      }),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)

    await expect(client.getSecurityAuditSummary('all', 9999)).resolves.toMatchObject({
      category: '',
      categories: ['auth', 'audit'],
      total: 5,
      recent_count: 3,
      window_limit: 500,
      action_counts: { remote_auth_guard: 2 },
      result_counts: { blocked: 1 },
      category_counts: { auth: 2 },
      unknown_action_count: 1,
    })

    const [url] = vi.mocked(fetchMock).mock.calls[0]
    expect(url).toBe('/api/security/audit-summary?limit=500')
  })

  it('normalizes security audit event filters and keeps the request bounded', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        events: [],
        total: '0',
        limit: '50',
      }),
    ) as unknown as typeof globalThis.fetch
    const client = await importClientWithFetch(fetchMock)

    await expect(
      client.getSecurityAuditEvents(999, {
        action: ' remote_auth_guard ',
        result: ' blocked ',
        category: ' auth ',
        user_id: ' user-1 ',
        since: 1_715_000_001.9,
        until: 1_715_000_099.4,
      }),
    ).resolves.toEqual({
      events: [],
      total: '0',
      limit: '50',
    })

    const [url] = vi.mocked(fetchMock).mock.calls[0]
    expect(url).toBe(
      '/api/security/audit-events?limit=500&action=remote_auth_guard&result=blocked&category=auth&user_id=user-1&since=1715000001&until=1715000099',
    )
  })

  it('sends cleaned cleanup payloads and surfaces backend cleanup errors', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          keep_latest: 200,
          deleted_count: 3,
          remaining_count: 17,
          dry_run: false,
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ detail: 'Cleanup failed' }, { status: 500 })) as unknown as typeof globalThis.fetch

    const client = await importClientWithFetch(fetchMock)

    await expect(
      client.cleanupSecurityAuditEvents({
        keep_latest: 12.7,
        dry_run: true,
      }),
    ).resolves.toEqual({
      keep_latest: 200,
      deleted_count: 3,
      remaining_count: 17,
      dry_run: false,
    })

    const [url, init] = vi.mocked(fetchMock).mock.calls[0]
    expect(url).toBe('/api/security/audit-events/cleanup?keep_latest=12&dry_run=true')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(JSON.stringify({ keep_latest: 12, dry_run: true }))

    await expect(
      client.cleanupSecurityAuditEvents({
        keep_latest: Number.NaN,
        dry_run: false,
      }),
    ).rejects.toThrow('Cleanup failed')
  })
})
