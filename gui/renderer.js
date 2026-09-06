const { ipcRenderer } = require('electron');

const terminal = document.getElementById('terminal');
const buttons = document.querySelectorAll('button');

function setButtonsState(disabled) {
    buttons.forEach(btn => btn.disabled = disabled);
}

function logToTerminal(text) {
    terminal.style.display = 'block';
    terminal.textContent += text;
    terminal.scrollTop = terminal.scrollHeight;
}

function runCommand(command, useSudo) {
    setButtonsState(true);
    terminal.textContent = `> infralock ${command}\n`;
    terminal.style.display = 'block';
    ipcRenderer.send('run-command', { command, useSudo });
}

ipcRenderer.on('command-output', (event, text) => {
    logToTerminal(text);
});

ipcRenderer.on('command-done', () => {
    setButtonsState(false);
});

document.getElementById('btn-enroll').addEventListener('click', () => {
    runCommand('enroll', true);
});

document.getElementById('btn-test').addEventListener('click', () => {
    runCommand('test', false);
});

document.getElementById('btn-install').addEventListener('click', () => {
    runCommand('install-pam', true);
});

document.getElementById('btn-uninstall').addEventListener('click', () => {
    runCommand('uninstall-pam', true);
});
