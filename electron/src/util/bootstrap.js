// electron/src/util/bootstrap.js
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export function backendPaths(isPackaged) {
  const base = isPackaged
    ? path.join(process.resourcesPath, 'backend')
    : path.resolve(__dirname, '../../..', 'backend');

  const pythonBin = process.platform === 'win32'
    ? path.join(base, '.venv', 'Scripts', 'python.exe')
    : path.join(base, '.venv', 'bin', 'python');

  const serverPy = path.join(base, 'server.py');
  return { base, pythonBin, serverPy };
}

export function pickPythonFallback() {
  if (process.platform === 'win32') return 'py';
  return 'python3';
}

export function spawnBackend(isPackaged) {
  const { base, pythonBin, serverPy } = backendPaths(isPackaged);

  const env = {
    ...process.env,
    PORT: '8765',
    // 自動/OS別バックエンド選択。必要なら ASR_BACKEND=mlx|ctranslate2 を指定
  };

  let cmd = pythonBin;
  let args = [serverPy];

  const proc = spawn(cmd, args, { cwd: base, env, stdio: 'pipe' });

  proc.on('error', () => {
    // venv 未作成時などはシステム Python で起動を試みる
    const fallback = pickPythonFallback();
    const p = spawn(fallback, [serverPy], { cwd: base, env, stdio: 'pipe' });
    p.on('error', (e) => console.error('backend spawn failed:', e));
  });

  proc.stdout?.on('data', (d) => console.log('[backend]', d.toString()));
  proc.stderr?.on('data', (d) => console.error('[backend]', d.toString()));

  return proc;
}