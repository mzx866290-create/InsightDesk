import { useEffect, useState } from 'react'

export function useSidebarViewport(setSidebarOpen: (open: boolean) => void) {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)

  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px)')

    const applyViewport = (matches: boolean) => {
      setIsMobile(matches)
      if (matches) {
        setSidebarOpen(false)
      }
    }

    applyViewport(media.matches)

    const handleChange = (event: MediaQueryListEvent) => {
      applyViewport(event.matches)
    }

    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [setSidebarOpen])

  return isMobile
}
