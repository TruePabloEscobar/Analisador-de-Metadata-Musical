"""Versioned GitHub release updates; the running executable is never overwritten."""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

VERSION = "1.1.0"
PROJECT_URL = "https://github.com/TruePabloEscobar/Analisador-de-Metadata-Musical"
API_URL = "https://api.github.com/repos/TruePabloEscobar/Analisador-de-Metadata-Musical/releases/latest"
ASSET_NAME = "Track.Metadata.Scanner.exe"


def version_tuple(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError(f"Versão inválida: {value}")
    return tuple(map(int, match.groups()))


def check_update():
    request = urllib.request.Request(API_URL, headers={"User-Agent": "TrackMetadataScanner/" + VERSION, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            release = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError("Não há release pública disponível ou o repositório está privado.") from exc
        raise
    if release.get("draft") or release.get("prerelease") or version_tuple(release["tag_name"]) <= version_tuple(VERSION):
        return None
    assets = [a for a in release.get("assets", []) if a["name"] in (ASSET_NAME, "Track Metadata Scanner.exe")]
    if len(assets) != 1:
        raise ValueError("A release não contém um executável Windows compatível.")
    release["scanner_asset"] = assets[0]
    return release


def download_update(release, executable):
    asset = release["scanner_asset"]
    url = asset["browser_download_url"]
    if not url.startswith(PROJECT_URL + "/releases/download/"):
        raise ValueError("Origem de atualização inválida.")
    digest = asset.get("digest", "")
    if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        raise ValueError("Release sem checksum SHA-256. Publique novamente o executável no GitHub Releases.")
    size = asset.get("size", 0)
    if not 0 < size <= 300 * 1024 * 1024:
        raise ValueError("Tamanho do executável inválido.")
    stage_dir = Path(tempfile.mkdtemp(prefix="scanner-update-", dir=executable.parent))
    staged = stage_dir / "update.exe"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "TrackMetadataScanner/" + VERSION})
        sha = hashlib.sha256(); total = 0
        with urllib.request.urlopen(request, timeout=30) as source, staged.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > size:
                    raise ValueError("Download excedeu o tamanho publicado.")
                target.write(chunk); sha.update(chunk)
        with staged.open("rb") as source:
            magic = source.read(2)
        if total != size or sha.hexdigest() != digest.split(":")[1].lower() or magic != b"MZ":
            raise ValueError("O executável baixado falhou na verificação de integridade.")
        return staged
    except Exception:
        staged.unlink(missing_ok=True); stage_dir.rmdir()
        raise


def launch_installer(staged, executable):
    # Literal paths are transported in JSON, never interpolated into shell code.
    config = staged.parent / "update.json"
    config.write_text(json.dumps({"pid": os.getpid(), "target": str(executable.resolve()), "staged": str(staged.resolve())}), encoding="utf-8")
    script = staged.parent / "install.ps1"
    script.write_text(r'''$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'update.json') -Raw | ConvertFrom-Json
$backup = $config.target + '.previous'
$log = Join-Path $PSScriptRoot 'update.log'
try {
    Wait-Process -Id $config.pid -Timeout 120 -ErrorAction SilentlyContinue
    if (Get-Process -Id $config.pid -ErrorAction SilentlyContinue) { throw 'Aplicativo ainda aberto.' }
    # The onefile bootloader can keep the EXE open briefly after Python exits.
    $replaced = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            [System.IO.File]::Replace($config.staged, $config.target, $backup, $true)
            $replaced = $true
            break
        } catch [System.IO.IOException] { Start-Sleep -Milliseconds 500 }
    }
    if (-not $replaced) { throw 'Executável bloqueado. Versão anterior preservada.' }
    try { Start-Process -FilePath $config.target -WindowStyle Hidden -ErrorAction Stop }
    catch { [System.IO.File]::Copy($backup, $config.target, $true); throw }
    'Atualização instalada. Backup: ' + $backup | Out-File -LiteralPath $log
} catch {
    $_ | Out-File -LiteralPath $log
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show('Falha na atualização. Consulte: ' + $log)
}
''', encoding="utf-8-sig")
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
