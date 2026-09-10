@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title Enviar Track Scanner para GitHub

set "PROJECT_DIR=T:\Track Scanner"
set "REPO_URL=https://github.com/TruePabloEscobar/Analisador-de-Metadata-Musical.git"
set "BRANCH=main"
set "SAFE_USER=TruePabloEscobar"
set "SAFE_EMAIL=161873772+TruePabloEscobar@users.noreply.github.com"

echo.
echo ==============================================
echo  Track Metadata Scanner - Enviar para GitHub
echo ==============================================
echo.

if not exist "%PROJECT_DIR%\" (
    echo ERRO: pasta nao encontrada:
    echo %PROJECT_DIR%
    pause
    exit /b 1
)

where git >nul 2>&1
if errorlevel 1 (
    echo ERRO: Git nao foi encontrado no PATH.
    echo Instale o Git for Windows e tente novamente.
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"
if errorlevel 1 (
    echo ERRO: nao foi possivel abrir a pasta do projeto.
    pause
    exit /b 1
)

if not exist ".gitignore" (
    echo ERRO: .gitignore nao encontrado.
    echo Copie o .gitignore fornecido para a raiz do projeto.
    pause
    exit /b 1
)

if not exist "Verificar_Open_Source.ps1" (
    echo ERRO: Verificar_Open_Source.ps1 nao encontrado.
    echo O envio foi bloqueado por seguranca.
    pause
    exit /b 1
)

echo [1/7] Verificando dados pessoais, segredos e arquivos locais...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%\Verificar_Open_Source.ps1" -ProjectRoot "%PROJECT_DIR%"
if errorlevel 1 (
    echo.
    echo ENVIO CANCELADO. Revise os itens mostrados acima.
    pause
    exit /b 1
)

echo.
echo [2/7] Preparando repositorio local...

if not exist ".git\" (
    git init
    if errorlevel 1 goto :git_error

    git remote add origin "%REPO_URL%"
    if errorlevel 1 goto :git_error

    git fetch origin "%BRANCH%"
    if errorlevel 1 goto :git_error

    git checkout -b "%BRANCH%" --track "origin/%BRANCH%"
    if errorlevel 1 (
        echo.
        echo Nao foi possivel vincular a branch remota automaticamente.
        echo Isso pode ocorrer se um arquivo local conflitar com o LICENSE do GitHub.
        echo Nenhum arquivo local foi apagado.
        pause
        exit /b 1
    )
) else (
    git remote get-url origin >nul 2>&1
    if errorlevel 1 (
        git remote add origin "%REPO_URL%"
        if errorlevel 1 goto :git_error
    ) else (
        git remote set-url origin "%REPO_URL%"
        if errorlevel 1 goto :git_error
    )

    git fetch origin "%BRANCH%"
    if errorlevel 1 goto :git_error

    for /f "delims=" %%B in ('git branch --show-current') do set "CURRENT_BRANCH=%%B"
    if /I not "!CURRENT_BRANCH!"=="%BRANCH%" (
        git checkout "%BRANCH%" >nul 2>&1
        if errorlevel 1 (
            git checkout -b "%BRANCH%" --track "origin/%BRANCH%"
            if errorlevel 1 goto :git_error
        )
    )
)

echo.
echo [3/7] Configurando identidade Git publica/noreply apenas neste repositorio...
for /f "delims=" %%A in ('git config --local user.name 2^>nul') do set "LOCAL_NAME=%%A"
if not defined LOCAL_NAME git config --local user.name "%SAFE_USER%"

for /f "delims=" %%A in ('git config --local user.email 2^>nul') do set "LOCAL_EMAIL=%%A"
if not defined LOCAL_EMAIL git config --local user.email "%SAFE_EMAIL%"

echo.
echo [4/7] Sincronizando com o GitHub antes do envio...
git pull --rebase --autostash origin "%BRANCH%"
if errorlevel 1 (
    echo.
    echo ERRO: nao foi possivel sincronizar com o GitHub.
    echo Resolva o conflito antes de tentar novamente.
    pause
    exit /b 1
)

echo.
echo [5/7] Adicionando somente arquivos permitidos pelo .gitignore...
git add -A
if errorlevel 1 goto :git_error

echo.
echo Verificando novamente o que ficou rastreado...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%\Verificar_Open_Source.ps1" -ProjectRoot "%PROJECT_DIR%"
if errorlevel 1 (
    git reset >nul 2>&1
    echo.
    echo ENVIO CANCELADO e o stage foi limpo.
    pause
    exit /b 1
)

git diff --cached --quiet
if not errorlevel 1 (
    echo.
    echo Nenhuma alteracao nova para enviar.
    pause
    exit /b 0
)

echo.
echo Arquivos que serao publicados:
git status --short
echo.

set "COMMIT_MSG="
set /p "COMMIT_MSG=Mensagem do commit [Enter = Atualiza codigo-fonte]: "
if not defined COMMIT_MSG set "COMMIT_MSG=Atualiza codigo-fonte"

echo.
echo [6/7] Criando commit...
git commit -m "%COMMIT_MSG%"
if errorlevel 1 goto :git_error

echo.
echo [7/7] Enviando para GitHub...
git push -u origin "%BRANCH%"
if errorlevel 1 goto :git_error

echo.
echo ==============================================
echo  ENVIO CONCLUIDO
echo ==============================================
echo https://github.com/TruePabloEscobar/Analisador-de-Metadata-Musical
echo.
pause
exit /b 0

:git_error
echo.
echo ERRO: algum comando Git falhou.
echo Leia a mensagem acima para identificar o problema.
pause
exit /b 1
