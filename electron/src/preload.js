// electron/src/preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('WHISPER_APP', {
  apiBase: 'http://127.0.0.1:8765',
  selectAudioFile: () => ipcRenderer.invoke('select-audio-file'),
  readFile: (filePath) => ipcRenderer.invoke('read-file', filePath)
});