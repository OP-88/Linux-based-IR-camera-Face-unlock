const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

function createWindow () {
  const win = new BrowserWindow({
    width: 600,
    height: 750,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    autoHideMenuBar: true,
    icon: path.join(__dirname, '../logo.jpg')
  });
  win.loadFile('index.html');
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

ipcMain.on('run-command', (event, arg) => {
  const { command, useSudo } = arg;
  
  let child;
  if (useSudo) {
    // pkexec spawns the native Linux graphical password prompt!
    child = spawn('pkexec', ['/usr/local/bin/infralock', command]);
  } else {
    child = spawn('/usr/local/bin/infralock', [command]);
  }

  child.stdout.on('data', (data) => {
    event.reply('command-output', data.toString());
  });
  
  child.stderr.on('data', (data) => {
    event.reply('command-output', data.toString());
  });
  
  child.on('close', (code) => {
    event.reply('command-output', `\n[Process Finished]\n`);
    event.reply('command-done');
  });
});
