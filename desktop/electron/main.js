/**
 * InsightDesk desktop shell (Electron).
 *
 * CherryStudio-style desktop behavior: single instance, system tray with
 * close-to-tray, native app icon. Spawns the packaged backend (PyInstaller
 * onedir under resources/backend), waits for /api/health, then loads the
 * single-port UI. Falls back to a dev backend (venv312 python) when the
 * packaged backend is absent, so `npm start` works from a source checkout.
 */
const { app, BrowserWindow, Tray, Menu, dialog, nativeImage } = require('electron');
const { spawn } = require('child_process');
const http = require('http');
const net = require('net');
const path = require('path');
const fs = require('fs');

let mainWindow = null;
let backendProcess = null;
let tray = null;
let quitting = false;

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

app.setAppUserModelId('com.insightdesk.desktop');

function resolveIcon() {
  const icoPath = path.join(__dirname, 'build', 'icon.ico');
  const pngPath = path.join(__dirname, 'build', 'icon.png');
  if (fs.existsSync(icoPath)) return icoPath;
  if (fs.existsSync(pngPath)) return pngPath;
  return undefined;
}

function findFreePort(start) {
  return new Promise((resolve, reject) => {
    const tryPort = (port, attemptsLeft) => {
      if (attemptsLeft <= 0) {
        reject(new Error('no free port'));
        return;
      }
      const server = net.createServer();
      server.once('error', () => tryPort(port + 1, attemptsLeft - 1));
      server.once('listening', () => server.close(() => resolve(port)));
      server.listen(port, '127.0.0.1');
    };
    tryPort(start, 20);
  });
}

function waitForHealth(port, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve) => {
    const probe = () => {
      const req = http.get({ host: '127.0.0.1', port, path: '/api/health', timeout: 2000 }, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          resolve(true);
          return;
        }
        retry();
      });
      req.on('error', retry);
      req.on('timeout', () => {
        req.destroy();
        retry();
      });
    };
    const retry = () => {
      if (Date.now() > deadline) {
        resolve(false);
        return;
      }
      setTimeout(probe, 500);
    };
    probe();
  });
}

function resolveBackendCommand() {
  const packaged = path.join(
    process.resourcesPath || '',
    'backend',
    'insightdesk-backend.exe',
  );
  if (fs.existsSync(packaged)) {
    return { command: packaged, args: [] };
  }
  const repoRoot = path.join(__dirname, '..', '..');
  const venvPython = path.join(repoRoot, 'venv312', 'Scripts', 'python.exe');
  if (fs.existsSync(venvPython)) {
    return { command: venvPython, args: ['-m', 'uvicorn', 'backend.api_server:app'] };
  }
  return null;
}

async function startBackend() {
  const resolved = resolveBackendCommand();
  if (!resolved) {
    dialog.showErrorBox(
      'InsightDesk',
      '未找到后端程序。请先运行 scripts/build_backend_exe.ps1 或 setup.bat。',
    );
    app.quit();
    return null;
  }

  const port = await findFreePort(8000);
  const userDataDir = app.getPath('userData');
  backendProcess = spawn(resolved.command, resolved.args, {
    cwd: userDataDir,
    env: {
      ...process.env,
      SERVER_PORT: String(port),
      SERVER_HOST: '127.0.0.1',
    },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  backendProcess.stdout.on('data', () => {});
  backendProcess.stderr.on('data', (data) => {
    console.error(`[backend] ${data}`);
  });
  backendProcess.on('exit', (code) => {
    console.error(`backend exited with ${code}`);
  });

  const ready = await waitForHealth(port, 180000);
  if (!ready) {
    dialog.showErrorBox('InsightDesk', '后端启动超时（/api/health 未就绪）。');
    app.quit();
    return null;
  }
  return port;
}

function createTray() {
  const iconPath = path.join(__dirname, 'build', 'icon.png');
  const image = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
    : nativeImage.createEmpty();
  tray = new Tray(image);
  tray.setToolTip('InsightDesk');
  tray.setContextMenu(
    Menu.buildFromTemplate([
      {
        label: '显示 InsightDesk',
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
          }
        },
      },
      { type: 'separator' },
      {
        label: '退出',
        click: () => {
          quitting = true;
          app.quit();
        },
      },
    ]),
  );
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

async function createWindow() {
  const port = await startBackend();
  if (port === null) return;

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
  });
  mainWindow.setMenuBarVisibility(false);
  mainWindow.once('ready-to-show', () => mainWindow.show());
  // CherryStudio behavior: closing the window hides it to the tray; the
  // backend keeps running so reopening is instant. Quit via tray menu.
  mainWindow.on('close', (event) => {
    if (!quitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
  createTray();
  await mainWindow.loadURL(`http://127.0.0.1:${port}`);
}

app.on('second-instance', () => {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
  }
});

app.on('before-quit', () => {
  quitting = true;
  if (tray) {
    tray.destroy();
    tray = null;
  }
  if (backendProcess !== null) {
    backendProcess.removeAllListeners('exit');
    backendProcess.kill();
    backendProcess = null;
  }
});

app.on('window-all-closed', () => {
  // keep running in the tray; quit happens through the tray menu
});

app.whenReady().then(createWindow);
