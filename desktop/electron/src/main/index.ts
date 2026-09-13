/**
 * InsightDesk desktop shell main process (TypeScript).
 *
 * Shell patterns adopted from CherryStudio (AGPL-3.0, referenced only):
 * - Windows minimize-to-tray via setOpacity(0)+setSkipTaskbar(true)+minimize()
 * - tray click shows the window; right-click pops the context menu
 * - tray / close-to-tray configurable via INSIGHTDESK_TRAY env flags
 * - electron-updater skeleton guarded by app.isPackaged
 *
 * Spawns the packaged backend (PyInstaller onedir under resources/backend),
 * waits for /api/health, then loads the single-port UI. Falls back to a dev
 * backend (venv312 python) when the packaged backend is absent.
 */
import { spawn } from 'node:child_process'
import http from 'node:http'
import net from 'node:net'
import path from 'node:path'
import fs from 'node:fs'
import { app, BrowserWindow, Tray, Menu, dialog, nativeImage, shell } from 'electron'

// electron-updater only ships in packaged builds; keep the import lazy.
type AutoUpdater = { autoDownload: boolean; autoInstallOnAppQuit: boolean; on: (event: string, handler: (info: { version?: string }) => void) => void; checkForUpdates: () => Promise<unknown> }

let mainWindow: BrowserWindow | null = null
let backendProcess: ReturnType<typeof spawn> | null = null
let tray: Tray | null = null
let quitting = false

const TRAY_ENABLED = process.env.INSIGHTDESK_TRAY !== '0'
const TRAY_ON_CLOSE = process.env.INSIGHTDESK_TRAY_ON_CLOSE !== '0'

if (!app.requestSingleInstanceLock()) {
  app.quit()
}

app.setAppUserModelId('com.insightdesk.desktop')

function resolveIcon(): string | undefined {
  const icoPath = path.join(__dirname, '../build/icon.ico')
  const pngPath = path.join(__dirname, '../build/icon.png')
  if (fs.existsSync(icoPath)) return icoPath
  if (fs.existsSync(pngPath)) return pngPath
  return undefined
}

function findFreePort(start: number): Promise<number> {
  return new Promise((resolve, reject) => {
    const tryPort = (port: number, attemptsLeft: number): void => {
      if (attemptsLeft <= 0) {
        reject(new Error('no free port'))
        return
      }
      const server = net.createServer()
      server.once('error', () => tryPort(port + 1, attemptsLeft - 1))
      server.once('listening', () => server.close(() => resolve(port)))
      server.listen(port, '127.0.0.1')
    }
    tryPort(start, 20)
  })
}

function waitForHealth(port: number, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs
  return new Promise((resolve) => {
    const retry = (): void => {
      if (Date.now() > deadline) {
        resolve(false)
        return
      }
      setTimeout(probe, 500)
    }
    const probe = (): void => {
      const req = http.get({ host: '127.0.0.1', port, path: '/api/health', timeout: 2000 }, (res) => {
        res.resume()
        if (res.statusCode === 200) {
          resolve(true)
          return
        }
        retry()
      })
      req.on('error', retry)
      req.on('timeout', () => {
        req.destroy()
        retry()
      })
    }
    probe()
  })
}

function resolveBackendCommand(): { command: string; args: string[] } | null {
  const packaged = path.join(process.resourcesPath || '', 'backend', 'insightdesk-backend.exe')
  if (fs.existsSync(packaged)) {
    return { command: packaged, args: [] }
  }
  const repoRoot = path.join(__dirname, '../../..')
  const venvPython = path.join(repoRoot, 'venv312', 'Scripts', 'python.exe')
  if (fs.existsSync(venvPython)) {
    return { command: venvPython, args: ['-m', 'uvicorn', 'backend.api_server:app'] }
  }
  return null
}

async function startBackend(): Promise<number | null> {
  const resolved = resolveBackendCommand()
  if (!resolved) {
    dialog.showErrorBox(
      'InsightDesk',
      '未找到后端程序。请先运行 scripts/build_backend_exe.ps1 或 setup.bat。',
    )
    app.quit()
    return null
  }

  const port = await findFreePort(8000)
  const userDataDir = app.getPath('userData')
  backendProcess = spawn(resolved.command, resolved.args, {
    cwd: userDataDir,
    env: {
      ...process.env,
      SERVER_PORT: String(port),
      SERVER_HOST: '127.0.0.1',
    },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  backendProcess.stdout?.on('data', () => {})
  backendProcess.stderr?.on('data', (data) => {
    console.error(`[backend] ${String(data)}`)
  })
  backendProcess.on('exit', (code) => {
    console.error(`backend exited with ${code}`)
  })

  const ready = await waitForHealth(port, 180000)
  if (!ready) {
    dialog.showErrorBox('InsightDesk', '后端启动超时（/api/health 未就绪）。')
    app.quit()
    return null
  }
  return port
}

function showMainWindow(): void {
  if (!mainWindow) return
  mainWindow.setOpacity(1)
  mainWindow.setSkipTaskbar(false)
  if (mainWindow.isMinimized()) mainWindow.restore()
  mainWindow.show()
  mainWindow.focus()
}

function createTray(): void {
  if (!TRAY_ENABLED) return
  const iconPath = path.join(__dirname, '../build/tray_icon.png')
  const image = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath)
    : nativeImage.createFromPath(path.join(__dirname, '../build/icon.png'))
  tray = new Tray(image)
  tray.setToolTip('InsightDesk')
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示 InsightDesk', click: showMainWindow },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        quitting = true
        app.quit()
      },
    },
  ])
  // CherryStudio pattern: click shows the window, right-click pops the menu.
  const activeTray = tray
  activeTray.on('click', showMainWindow)
  activeTray.on('right-click', () => activeTray.popUpContextMenu(contextMenu))
  activeTray.on('double-click', showMainWindow)
  activeTray.setContextMenu(contextMenu)
}

function minimizeToTrayOnWindows(): void {
  if (!mainWindow) return
  mainWindow.setOpacity(0)
  mainWindow.setSkipTaskbar(true)
  mainWindow.minimize()
}

function setupAutoUpdater(): void {
  if (!app.isPackaged) return
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { autoUpdater } = require('electron-updater') as { autoUpdater: AutoUpdater }
    autoUpdater.autoDownload = false
    autoUpdater.autoInstallOnAppQuit = false
    autoUpdater.on('update-available', (info) => {
      dialog
        .showMessageBox({
          type: 'info',
          title: 'InsightDesk 更新',
          message: `发现新版本 ${info.version ?? ''}`,
          detail: '可前往 GitHub Releases 页面下载。',
          buttons: ['打开下载页', '以后再说'],
          defaultId: 0,
        })
        .then(({ response }) => {
          if (response === 0) {
            void shell.openExternal('https://github.com/mzx866290-create/InsightDesk/releases')
          }
        })
    })
    autoUpdater.checkForUpdates().catch(() => {
      // no published release yet; silently skip
    })
  } catch {
    // updater unavailable; ignore
  }
}

async function createWindow(): Promise<void> {
  const port = await startBackend()
  if (port === null) return

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'InsightDesk',
    icon: resolveIcon(),
    backgroundColor: '#101319',
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  const win = mainWindow
  win.setMenuBarVisibility(false)
  win.once('ready-to-show', () => win.show())
  win.on('close', (event) => {
    if (quitting || !TRAY_ENABLED || !TRAY_ON_CLOSE) return // real quit
    event.preventDefault()
    minimizeToTrayOnWindows()
  })
  win.on('closed', () => {
    mainWindow = null
  })
  createTray()
  setupAutoUpdater()
  await mainWindow.loadURL(`http://127.0.0.1:${port}`)
}

app.on('second-instance', showMainWindow)

app.on('before-quit', () => {
  quitting = true
  if (tray) {
    tray.destroy()
    tray = null
  }
  if (backendProcess !== null) {
    backendProcess.removeAllListeners('exit')
    backendProcess.kill()
    backendProcess = null
  }
})

app.on('window-all-closed', () => {
  // tray-resident: quit goes through the tray menu
})

void app.whenReady().then(createWindow)
