/**
 * InsightDesk desktop shell (Electron).
 *
 * Spawns the packaged backend (PyInstaller onedir under resources/backend),
 * waits for /api/health, then loads the single-port UI. Falls back to a
 * dev backend (venv312 python + desktop/app.py semantics) when the packaged
 * backend is absent, so `npm start` works from a source checkout.
 */
const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const http = require('http');
const net = require('net');
const path = require('path');
const fs = require('fs');

let mainWindow = null;
let backendProcess = null;

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

async function createWindow() {
  const port = await startBackend();
  if (port === null) return;

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'InsightDesk',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.setMenuBarVisibility(false);
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
  await mainWindow.loadURL(`http://127.0.0.1:${port}`);
}

app.on('window-all-closed', () => {
  app.quit();
});

app.on('before-quit', () => {
  if (backendProcess !== null) {
    backendProcess.removeAllListeners('exit');
    backendProcess.kill();
    backendProcess = null;
  }
});

app.whenReady().then(createWindow);
