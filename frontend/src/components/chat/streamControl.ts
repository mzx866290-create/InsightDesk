export interface ActiveStreamControl {
  mode: 'parallel' | 'single_rerun' | 'single_continue'
  panelId?: string
  stop: () => void
}
