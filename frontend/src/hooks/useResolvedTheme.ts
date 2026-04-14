import { useEffect, useState } from 'react'
import { useChatStore, type ThemeMode } from '../stores/chatStore'

export function resolveThemeMode(
  theme: ThemeMode,
  prefersDark: boolean,
): 'dark' | 'light' {
  if (theme === 'system') {
    return prefersDark ? 'dark' : 'light'
  }
  return theme
}

export function useResolvedTheme(): {
  theme: ThemeMode
  resolvedTheme: 'dark' | 'light'
  prefersDark: boolean
} {
  const theme = useChatStore((s) => s.theme)
  const [prefersDark, setPrefersDark] = useState(() => {
    if (typeof window === 'undefined') return true
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    if (typeof window === 'undefined') return

    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (event: MediaQueryListEvent) => {
      setPrefersDark(event.matches)
    }

    setPrefersDark(media.matches)
    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [])

  return {
    theme,
    resolvedTheme: resolveThemeMode(theme, prefersDark),
    prefersDark,
  }
}
