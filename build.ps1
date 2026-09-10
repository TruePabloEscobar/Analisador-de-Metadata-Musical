$ErrorActionPreference = 'Stop'
$python = (Get-Command python).Source
& $python -m PyInstaller --clean --noconfirm 'Track Metadata Scanner.spec'
