// electron/src/preload.js
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('WHISPER_APP', {
  apiBase: 'http://127.0.0.1:8765'
});