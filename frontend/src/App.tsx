import React, { useState } from 'react'
import { Sidebar } from './components/layout/Sidebar'
import { Header } from './components/layout/Header'
import { ChatArea } from './components/chat/ChatArea'
import { SettingsModal } from './components/settings/SettingsModal'

const App: React.FC = () => {
  const [settingsOpen, setSettingsOpen] = useState(false)

  return (
    <div className="flex h-screen bg-bg-primary overflow-hidden">
      {/* Sidebar */}
      <Sidebar onOpenSettings={() => setSettingsOpen(true)} />

      {/* Main content */}
      <div className="flex flex-col flex-1 min-w-0">
        <Header onOpenSettings={() => setSettingsOpen(true)} />
        <ChatArea />
      </div>

      {/* Settings modal */}
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

export default App
