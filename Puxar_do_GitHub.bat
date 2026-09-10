@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title Puxar Track Scanner do GitHub

set "PROJECT_DIR=T:\Track Scanner"
set "PARENT_DIR=T:\"
set "REPO_URL=https://github.com/TruePabloEscobar/Analisador-de-Metadata-Musical.git"
set "BRANCH=main"

echo.
echo ==============================================
echo  Track Metadata Scanner - Puxar do GitHub
echo ==============================================
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo ERRO: Git nao foi encontrado no PATH.
    echo Instale o Git for Windows e tente novamente.
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%\" (
    echo Pasta local nao existe. Clonando repositorio...
    if not exist "%PARENT_DIR%" (
        echo ERRO: unidade/pasta pai nao encontrada: %PARENT_DIR%
        pause
        exit /b 1
    )

    git clone --branch "%BRANCH%" "%REPO_URL%" "%PROJECT_DIR%"
    if errorlevel 1 goto :git_error

    echo.
    echo Repositorio clonado em:
    echo %PROJECT_DIR%
    pause
    exit /b 0
)

cd /d "%PROJECT_DIR%"
if errorlevel 1 goto :git_error

if not exist ".git\" (
    dir /b /a "%PROJECT_DIR%" 2>nul | findstr . >nul
    if not errorlevel 1 (
        echo ERRO: a pasta existe e contem arquivos, mas nao e um repositorio Git.
        echo Para evitar sobrescrever seu projeto, o pull foi cancelado.
        echo Use primeiro Enviar_para_GitHub.bat ou renomeie a pasta local.
        pause
        exit /b 1
    )

    git clone --branch "%BRANCH%" "%REPO_URL%" "%PROJECT_DIR%"
    if errorlevel 1 goto :git_error
    pause
    exit /b 0
)

echo Verificando alteracoes locais...
set "DIRTY="
for /f "delims=" %%A in ('git status --porcelain') do set "DIRTY=1"
if defined DIRTY (
    echo.
    echo PULL CANCELADO.
    echo Existem alteracoes locais ainda nao commitadas:
    git status --short
    echo.
    echo Envie/commite ou descarte conscientemente essas alteracoes antes de puxar.
    pause
    exit /b 1
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    git remote add origin "%REPO_URL%"
    if errorlevel 1 goto :git_error
) else (
    git remote set-url origin "%REPO_URL%"
    if errorlevel 1 goto :git_error
)

echo.
echo Buscando atualizacoes...
git fetch origin "%BRANCH%"
if errorlevel 1 goto :git_error

for /f "delims=" %%B in ('git branch --show-current') do set "CURRENT_BRANCH=%%B"
if /I not "!CURRENT_BRANCH!"=="%BRANCH%" (
    git checkout "%BRANCH%"
    if errorlevel 1 goto :git_error
)

echo.
echo Aplicando somente fast-forward...
git pull --ff-only origin "%BRANCH%"
if errorlevel 1 (
    echo.
    echo ERRO: o pull nao pode ser feito por fast-forward.
    echo Isso evita criar merge automatico ou sobrescrever historico.
    pause
    exit /b 1
)

echo.
echo ==============================================
echo  PROJETO ATUALIZADO
echo ==============================================
echo %PROJECT_DIR%
echo.
pause
exit /b 0

:git_error
echo.
echo ERRO: algum comando Git falhou.
echo Leia a mensagem acima para identificar o problema.
pause
exit /b 1
