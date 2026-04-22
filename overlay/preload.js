const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  closeWindow:    () => ipcRenderer.send('close-window'),
  minimizeWindow: () => ipcRenderer.send('minimize-window'),
  setHeight:      (height) => ipcRenderer.send('set-height', height),
  getToken:       () => ipcRenderer.invoke('get-token'),
  saveToken:      (token) => ipcRenderer.invoke('save-token', token),
  clearToken:     () => ipcRenderer.invoke('clear-token'),
});
