const { app, BrowserWindow, ipcMain, dialog, shell, globalShortcut, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');

let mainWindow;
let pythonProcess;
let flaskPort = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    fullscreenable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      devTools: true
    }
  });
  mainWindow.loadFile('index.html');
}

function buildMenu() {
  const outputPath = path.join(__dirname, 'output');
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Open Output Folder',
          click: () => shell.openPath(outputPath)
        },
        { type: 'separator' },
        {
          label: 'Exit',
          accelerator: 'Alt+F4',
          click: () => app.quit()
        }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About Abako Competition Suite',
              message: 'Abako Competition Suite',
              detail: `Version ${app.getVersion()}\n\nDesigned for Abako Tech (Pakistan).`
            });
          }
        }
      ]
    }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// Sends a single POST /ping to Flask; resolves true if it gets a 2xx back.
function pingFlask(port) {
  return new Promise((resolve) => {
    const body = '{}';
    const req = http.request(
      {
        host: '127.0.0.1',
        port,
        path: '/ping',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body)
        }
      },
      (res) => { resolve(res.statusCode >= 200 && res.statusCode < 300); }
    );
    req.on('error', () => resolve(false));
    req.write(body);
    req.end();
  });
}

// Polls /ping every 500 ms until Flask responds or maxMs elapses.
async function waitForBackend(port, maxMs = 10000) {
  const interval = 500;
  let elapsed = 0;
  while (elapsed < maxMs) {
    if (await pingFlask(port)) return;
    await new Promise(r => setTimeout(r, interval));
    elapsed += interval;
  }
  throw new Error(`Backend on port ${port} did not respond within ${maxMs} ms`);
}

// Spawns a process, resolves with the Flask port from its first stdout line.
// If the spawn errors and a fallback is provided, retries with the fallback.
function spawnBackend(command, args, fallback) {
  console.log(`[spawnBackend] running: ${command} ${args.join(' ')}`);
  return new Promise((resolve, reject) => {
    const proc = spawn(command, args, { cwd: __dirname });
    let buf = '';
    let settled = false;

    proc.stdout.on('data', (data) => {
      const text = data.toString();
      console.log(`[backend stdout] ${text.trim()}`);
      if (settled) return;
      buf += text;
      const nl = buf.indexOf('\n');
      if (nl === -1) return;
      settled = true;
      pythonProcess = proc;
      try {
        const parsed = JSON.parse(buf.substring(0, nl).trim());
        flaskPort = parsed.port;
        resolve(flaskPort);
      } catch (e) {
        reject(new Error('Bad startup line: ' + buf.substring(0, nl)));
      }
    });

    proc.stderr.on('data', (data) => {
      console.error('[backend stderr]', data.toString().trimEnd());
    });

    proc.on('error', (err) => {
      console.error('[spawnBackend] spawn error:', err.message);
      if (settled) return;
      settled = true;
      if (fallback) {
        console.log(`[main] ${command} failed (${err.message}), falling back to ${fallback.command}`);
        spawnBackend(fallback.command, fallback.args, null).then(resolve).catch(reject);
      } else {
        reject(err);
      }
    });

    proc.on('exit', (code) => {
      console.log(`[spawnBackend] process exited with code ${code}`);
      if (!settled) {
        settled = true;
        reject(new Error(`Backend exited before sending startup line (code ${code})`));
      }
    });
  });
}

function startPythonProcess() {
  if (app.isPackaged) {
    const sidecar = path.join(process.resourcesPath, 'resources', 'abako_sidecar', 'abako_sidecar.exe');
    return spawnBackend(sidecar, [], null);
  }

  const backendScript = path.join(__dirname, 'backend', 'main.py');
  const venvCandidates = [
    path.join(__dirname, '.venv', 'Scripts', 'python.exe'),
    path.join(__dirname, 'venv', 'Scripts', 'python.exe')
  ];
  const venvPython = venvCandidates.find(fs.existsSync);
  const sidecarDev = path.join(__dirname, 'resources', 'abako_sidecar', 'abako_sidecar.exe');
  const fallback = fs.existsSync(sidecarDev) ? { command: sidecarDev, args: [] } : null;

  // Prefer the project venv so Flask and all deps are guaranteed available
  const pythonCmd = venvPython || 'python';
  console.log(`[main] startPythonProcess: using Python at "${pythonCmd}"`);
  console.log(`[main] startPythonProcess: backend script at "${backendScript}"`);

  return spawnBackend(pythonCmd, [backendScript], fallback);
}

app.whenReady().then(async () => {
  try {
    await startPythonProcess();
    console.log(`[main] Python spawned, flask port ${flaskPort} — waiting for /ping...`);
    await waitForBackend(flaskPort);
    console.log(`[main] Flask backend confirmed ready on port ${flaskPort}`);
  } catch (err) {
    console.error('[main] Failed to start backend:', err.message);
  }

  buildMenu();
  createWindow();

  // Push the confirmed port to the renderer once the page has loaded.
  // This is the authoritative signal that Flask is ready; the renderer
  // waits for this event before making any API calls.
  mainWindow.webContents.once('did-finish-load', () => {
    if (flaskPort !== null) {
      mainWindow.webContents.send('backend-port', flaskPort);
    }
  });

  // F11 toggles fullscreen; Escape exits it
  globalShortcut.register('F11', () => {
    if (!mainWindow) return;
    mainWindow.setFullScreen(!mainWindow.isFullScreen());
  });
  globalShortcut.register('Escape', () => {
    if (mainWindow && mainWindow.isFullScreen()) {
      mainWindow.setFullScreen(false);
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (pythonProcess) pythonProcess.kill();
});

ipcMain.handle('get-port', () => flaskPort);

ipcMain.handle('get-version', () => app.getVersion());

ipcMain.handle('shell-open-path', (event, filePath) => {
  console.log('[shell-open-path] opening:', filePath);
  return shell.openPath(filePath);
});

ipcMain.handle('open-file-dialog', async (event, filters) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: filters || [{ name: 'Excel Files', extensions: ['xlsx', 'xls'] }]
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('open-folder-dialog', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  return result.canceled ? null : result.filePaths[0];
});
