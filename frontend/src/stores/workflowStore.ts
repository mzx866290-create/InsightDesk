import { create } from 'zustand'

export interface WorkflowNode {
  id: string
  name: string
  displayName: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  startTime?: number
  endTime?: number
  duration?: number
  toolName?: string
  toolParams?: Record<string, any>
  toolResult?: string
  error?: string
}

export interface WorkflowState {
  panelId: string
  nodes: WorkflowNode[]
  currentNodeId: string | null
  isVisible: boolean
}

interface WorkflowStoreState {
  workflows: Map<string, WorkflowState>
  
  initWorkflow: (panelId: string) => void
  hydrateWorkflow: (panelId: string, nodes: WorkflowNode[], visible?: boolean) => void
  resetWorkflow: (panelId: string) => void
  updateNodeStatus: (panelId: string, nodeId: string, status: WorkflowNode['status'], meta?: Partial<WorkflowNode>) => void
  setCurrentNode: (panelId: string, nodeId: string | null) => void
  setWorkflowVisible: (panelId: string, visible: boolean) => void
  getWorkflow: (panelId: string) => WorkflowState | undefined
  clearWorkflow: (panelId: string) => void
}

function createWorkflow(panelId: string, isVisible = true): WorkflowState {
  return {
    panelId,
    nodes: [
      {
        id: 'classify_intent',
        name: 'classify_intent',
        displayName: '意图分类',
        status: 'pending',
      },
      {
        id: 'execute_tool',
        name: 'execute_tool',
        displayName: '工具执行',
        status: 'pending',
      },
      {
        id: 'generate_answer',
        name: 'generate_answer',
        displayName: '答案生成',
        status: 'pending',
      },
    ],
    currentNodeId: null,
    isVisible,
  }
}

function normalizeHydratedNodes(panelId: string, nodes: WorkflowNode[]): WorkflowNode[] {
  const defaults = createWorkflow(panelId).nodes
  const providedById = new Map<string, WorkflowNode>()

  for (const node of nodes) {
    const nodeId = (node.id || node.name || '').trim()
    if (!nodeId) continue
    providedById.set(nodeId, {
      ...node,
      id: nodeId,
      name: node.name || nodeId,
      displayName: node.displayName || node.name || nodeId,
    })
  }

  const mergedDefaults = defaults.map((node) => ({
    ...node,
    ...(providedById.get(node.id) ?? {}),
  }))

  const extraNodes = [...providedById.entries()]
    .filter(([nodeId]) => !defaults.some((node) => node.id === nodeId))
    .map(([, node]) => node)

  return [...mergedDefaults, ...extraNodes]
}

export const useWorkflowStore = create<WorkflowStoreState>((set, get) => ({
  workflows: new Map(),

  initWorkflow: (panelId: string) => {
    set((state) => {
      const newWorkflows = new Map(state.workflows)
      if (!newWorkflows.has(panelId)) {
        newWorkflows.set(panelId, createWorkflow(panelId))
      }
      return { workflows: newWorkflows }
    })
  },

  hydrateWorkflow: (panelId, nodes, visible = true) => {
    set((state) => {
      const newWorkflows = new Map(state.workflows)
      const normalizedNodes = normalizeHydratedNodes(panelId, nodes)
      const currentNode = normalizedNodes.find((node) => node.status === 'running')

      newWorkflows.set(panelId, {
        panelId,
        nodes: normalizedNodes,
        currentNodeId: currentNode?.id ?? null,
        isVisible: visible,
      })

      return { workflows: newWorkflows }
    })
  },

  resetWorkflow: (panelId) => {
    set((state) => {
      const newWorkflows = new Map(state.workflows)
      const existing = newWorkflows.get(panelId)
      newWorkflows.set(panelId, createWorkflow(panelId, existing?.isVisible ?? true))
      return { workflows: newWorkflows }
    })
  },

  updateNodeStatus: (panelId, nodeId, status, meta = {}) => {
    set((state) => {
      const newWorkflows = new Map(state.workflows)
      const workflow = newWorkflows.get(panelId) ?? createWorkflow(panelId)
      
      const now = Date.now()
      const updatedNodes = workflow.nodes.map((node) => {
        if (node.id === nodeId) {
          const startTime = node.startTime || (status === 'running' ? now : undefined)
          const endTime = status === 'completed' || status === 'failed' ? now : undefined
          const duration = startTime && endTime ? endTime - startTime : undefined
          
          return {
            ...node,
            status,
            startTime,
            endTime,
            duration,
            ...meta,
          }
        }
        return node
      })
      
      newWorkflows.set(panelId, {
        ...workflow,
        nodes: updatedNodes,
        currentNodeId:
          status === 'running'
            ? nodeId
            : workflow.currentNodeId === nodeId
              ? null
              : workflow.currentNodeId,
      })
      
      return { workflows: newWorkflows }
    })
  },

  setCurrentNode: (panelId, nodeId) => {
    set((state) => {
      const newWorkflows = new Map(state.workflows)
      const workflow = newWorkflows.get(panelId)
      
      if (workflow) {
        newWorkflows.set(panelId, {
          ...workflow,
          currentNodeId: nodeId,
        })
      }
      
      return { workflows: newWorkflows }
    })
  },

  setWorkflowVisible: (panelId, visible) => {
    set((state) => {
      const newWorkflows = new Map(state.workflows)
      const workflow = newWorkflows.get(panelId)
      
      if (workflow) {
        newWorkflows.set(panelId, {
          ...workflow,
          isVisible: visible,
        })
      }
      
      return { workflows: newWorkflows }
    })
  },

  getWorkflow: (panelId) => {
    return get().workflows.get(panelId)
  },

  clearWorkflow: (panelId) => {
    set((state) => {
      const newWorkflows = new Map(state.workflows)
      newWorkflows.delete(panelId)
      return { workflows: newWorkflows }
    })
  },
}))
