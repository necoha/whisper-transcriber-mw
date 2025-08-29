// electron/src/main.js
import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import { spawnBackend } from './util/bootstrap.js';

let backendProc;

// Get the directory path of the current module
const __dirname = path.dirname(fileURLToPath(import.meta.url));

function createWindow() {
  const win = new BrowserWindow({
    width: 1000,
    height: 720,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.whenReady().then(() => {
  backendProc = spawnBackend(app.isPackaged);
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (backendProc && !backendProc.killed) {
    try { backendProc.kill(); } catch {}
  }
});

// IPC handlers for file operations
ipcMain.handle('select-audio-file', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openFile'],
    filters: [
      {
        name: 'Audio Files',
        extensions: ['mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg', 'webm', 'mp4', 'mov', 'avi', 'mkv']
      }
    ]
  });
  
  if (!result.canceled && result.filePaths.length > 0) {
    const filePath = result.filePaths[0];
    return {
      path: filePath,
      directory: path.dirname(filePath),
      name: path.basename(filePath)
    };
  }
  return null;
});

// Read file content as buffer
ipcMain.handle('read-file', async (event, filePath) => {
  try {
    const buffer = await readFile(filePath);
    return buffer;
  } catch (error) {
    throw error;
  }
});