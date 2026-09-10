param(
    [string]$ProjectRoot = "T:\Track Scanner"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    Write-Host "ERRO: pasta do projeto nao encontrada: $ProjectRoot" -ForegroundColor Red
    exit 2
}

$excludedDirectoryNames = @(
    ".git", ".venv", "venv", "env", "ENV", "build", "dist",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode", "Relatorio", "Relatorios", "reports",
    "report", "output", "outputs", "exports", "cache", ".cache"
)

$textExtensions = @(
    ".py", ".bat", ".cmd", ".ps1", ".md", ".txt", ".toml",
    ".ini", ".cfg", ".json", ".yaml", ".yml", ".spec",
    ".html", ".css", ".js", ".ts", ".tsx", ".jsx", ".xml"
)

$patterns = [ordered]@{
    "Token/API key conhecido" = '(?i)\b(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b'
    "Chave privada" = '-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'
    "Segredo hardcoded" = '(?i)\b(api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|password)\b\s*[:=]\s*["''][^"'']{6,}["'']'
    "Caminho de usuario Windows" = '(?i)[A-Z]:\\Users\\[^\\\r\n]+'
    "Caminho da biblioteca musical pessoal" = '(?i)M:\\IA HERE\\Pablo Escobar Music 2027'
    "CPF em formato comum" = '\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'
}

$findings = New-Object System.Collections.Generic.List[object]

$files = Get-ChildItem -LiteralPath $ProjectRoot -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object {
        $full = $_.FullName
        $relative = $full.Substring($ProjectRoot.Length).TrimStart('\')
        $parts = $relative -split '\\'
        $hasExcludedDir = $false

        foreach ($part in $parts) {
            if ($excludedDirectoryNames -contains $part) {
                $hasExcludedDir = $true
                break
            }
        }

        (-not $hasExcludedDir) -and
        ($textExtensions -contains $_.Extension.ToLowerInvariant()) -and
        ($_.Name -ne "Verificar_Open_Source.ps1")
    }

foreach ($file in $files) {
    try {
        $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction Stop
    }
    catch {
        continue
    }

    foreach ($entry in $patterns.GetEnumerator()) {
        $matches = [regex]::Matches($content, $entry.Value)
        if ($matches.Count -gt 0) {
            $relative = $file.FullName.Substring($ProjectRoot.Length).TrimStart('\')
            $findings.Add([pscustomobject]@{
                File = $relative
                Type = $entry.Key
                Count = $matches.Count
            })
        }
    }
}

if (Test-Path -LiteralPath (Join-Path $ProjectRoot ".git")) {
    $tracked = @(& git -C $ProjectRoot ls-files 2>$null)

    $forbiddenExtensions = @(
        ".xlsx", ".xls", ".mp3", ".wav", ".flac", ".aif", ".aiff",
        ".m4a", ".aac", ".ogg", ".opus", ".wma", ".pem", ".pfx", ".p12"
    )

    foreach ($item in $tracked) {
        $ext = [System.IO.Path]::GetExtension($item).ToLowerInvariant()
        $normalized = $item.Replace('\','/')

        $forbiddenPath =
            $normalized -match '(^|/)(build|dist|\.venv|venv|__pycache__|reports?|outputs?|exports?)/' -or
            $normalized -match '(^|/)\.env($|\.)' -or
            $normalized -match '(?i)(credentials?|secrets?).*\.json$'

        if (($forbiddenExtensions -contains $ext) -or $forbiddenPath) {
            $findings.Add([pscustomobject]@{
                File = $item
                Type = "Arquivo local/sensivel rastreado pelo Git"
                Count = 1
            })
        }
    }
}

if ($findings.Count -gt 0) {
    Write-Host ""
    Write-Host "BLOQUEADO: foram encontrados itens que precisam de revisao antes de publicar." -ForegroundColor Red
    Write-Host ""
    $findings |
        Sort-Object File, Type -Unique |
        Format-Table -AutoSize |
        Out-Host

    Write-Host ""
    Write-Host "Nada sera enviado. Remova/substitua dados pessoais, segredos ou arquivos locais e rode novamente." -ForegroundColor Yellow
    exit 1
}

Write-Host "Verificacao open-source concluida: nenhum dado obvio de alto risco encontrado." -ForegroundColor Green
exit 0
