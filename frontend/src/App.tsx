import React from 'react'
import { Sidebar } from './components/layout/Sidebar'
import { Header } from './components/layout/Header'
import { ChatArea } from './components/chat/ChatArea'
import { SettingsModal } from './components/settings/SettingsModal'
import { useChatStore } from './stores/chatStore'

const App: React.FC = () => {
  const settingsOpen = useChatStore((s) => s.settingsOpen)
  const setSettingsOpen = useChatStore((s) => s.setSettingsOpen)

  return (
    <div className="flex min-h-screen min-h-[100svh] bg-bg-primary md:h-screen md:overflow-hidden">
      {/* Sidebar */}
      <Sidebar />

      {/* Main content */}
      <div className="flex min-w-0 flex-1 flex-col min-h-screen min-h-[100svh] md:min-h-0">
        <Header />
        <ChatArea />
      </div>

      {/* Settings modal */}
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

export default App
