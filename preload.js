const { contextBridge, ipcRenderer } = require('electron');

// Port is pushed from main.js via 'backend-port' once Flask is confirmed ready.
// Using a push model (not invoke-per-call) so the renderer never races against startup.
let flaskPort = null;

ipcRenderer.on('backend-port', (event, port) => {
  flaskPort = port;
  // Dispatch to the renderer so it can start its init sequence (ping + check-bank).
  window.dispatchEvent(new CustomEvent('backend-ready'));
});

contextBridge.exposeInMainWorld('api', {
  appVersion: () => ipcRenderer.invoke('get-version'),
  isDev: process.env.NODE_ENV !== 'production',

  call: async (endpoint, body = {}) => {
    if (flaskPort === null) throw new Error('Backend not ready yet');
    const res = await fetch(`http://localhost:${flaskPort}/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    return res.json();
  },

  openFile: (filters) => ipcRenderer.invoke('open-file-dialog', filters),
  openFolder: () => ipcRenderer.invoke('open-folder-dialog'),
  openPath: (filePath) => ipcRenderer.invoke('shell-open-path', filePath)
});
