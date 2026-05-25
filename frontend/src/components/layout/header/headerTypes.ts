export interface HeaderActionFeedback {
  tone: 'error' | 'success'
  message: string
}

export type HeaderActionFeedbackSetter = (feedback: HeaderActionFeedback | null) => void

export type HeaderDeckTheme = 'default' | 'midnight' | 'sunrise'
