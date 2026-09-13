export {}

declare global {
  interface Window {
    insightdeskDesktop?: { version: string }
  }
}

// Reserved for future IPC (settings bridge, native notifications).
// The UI currently talks to the backend over loopback HTTP only.
window.insightdeskDesktop = { version: '2.0.0' }
