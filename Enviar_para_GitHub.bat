@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title Enviar Track Scanner para GitHub

REM ==================================================
REM CONFIGURACAO
REM ==================================================

REM %~dp0 retorna a pasta onde este BAT esta.
REM Como ele termina com "\", removemos a barra final.
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

set "REPO_URL=https://github.com/TruePabloEscobar/Analisador-de-Metadata-Musical.git"
set "BRANCH=main"
set "SAFE_USER=TruePabloEscobar"
set "SAFE_EMAIL=161873772+TruePabloEscobar@users.noreply.github.com"


echo.
echo ==============================================
echo  Track Metadata Scanner - Enviar para GitHub
echo ==============================================
echo.
echo Projeto:
echo %PROJECT_DIR%
echo.


REM ==================================================
REM VERIFICAR PASTA
REM ==================================================

if not exist "%PROJECT_DIR%\" (
    echo ERRO: pasta nao encontrada:
    echo %PROJECT_DIR%
    pause
    exit /b 1
)


REM ==================================================
REM VERIFICAR GIT
REM ==================================================

where git >nul 2>&1

if errorlevel 1 (
    echo ERRO: Git nao foi encontrado no PATH.
    echo Instale o Git for Windows e tente novamente.
    pause
    exit /b 1
)


REM ==================================================
REM ENTRAR NO PROJETO
REM ==================================================

cd /d "%PROJECT_DIR%"

if errorlevel 1 (
    echo ERRO: nao foi possivel abrir a pasta do projeto.
    pause
    exit /b 1
)


REM ==================================================
REM VERIFICAR ARQUIVOS DE SEGURANCA
REM ==================================================

if not exist ".gitignore" (
    echo ERRO: .gitignore nao encontrado.
    echo O envio foi cancelado.
    pause
    exit /b 1
)

if not exist "Verificar_Open_Source.ps1" (
    echo ERRO: Verificar_Open_Source.ps1 nao encontrado.
    echo O envio foi bloqueado por seguranca.
    pause
    exit /b 1
)


REM ==================================================
REM 1/7 - VERIFICACAO OPEN SOURCE
REM ==================================================

echo.
echo [1/7] Verificando dados pessoais, segredos e arquivos locais...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%\Verificar_Open_Source.ps1" -ProjectRoot "%PROJECT_DIR%"

if errorlevel 1 (
    echo.
    echo ==============================================
    echo  ENVIO CANCELADO POR SEGURANCA
    echo ==============================================
    echo.
    echo Revise os itens mostrados acima.
    echo Nenhum arquivo foi enviado.
    echo.
    pause
    exit /b 1
)


REM ==================================================
REM 2/7 - PREPARAR REPOSITORIO
REM ==================================================

echo.
echo [2/7] Preparando repositorio local...
echo.

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
        echo.
        echo Isso pode ocorrer se algum arquivo local entrar
        echo em conflito com um arquivo ja existente no GitHub.
        echo.
        echo Nenhum arquivo local foi apagado.
        echo.
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


    set "CURRENT_BRANCH="

    for /f "delims=" %%B in ('git branch --show-current') do (
        set "CURRENT_BRANCH=%%B"
    )


    if /I not "!CURRENT_BRANCH!"=="%BRANCH%" (

        git checkout "%BRANCH%" >nul 2>&1

        if errorlevel 1 (

            git checkout -b "%BRANCH%" --track "origin/%BRANCH%"

            if errorlevel 1 goto :git_error
        )
    )
)


REM ==================================================
REM 3/7 - IDENTIDADE GIT
REM ==================================================

echo.
echo [3/7] Configurando identidade Git publica/noreply...
echo.

set "LOCAL_NAME="
set "LOCAL_EMAIL="

for /f "delims=" %%A in ('git config --local user.name 2^>nul') do (
    set "LOCAL_NAME=%%A"
)

if not defined LOCAL_NAME (
    git config --local user.name "%SAFE_USER%"
)


for /f "delims=" %%A in ('git config --local user.email 2^>nul') do (
    set "LOCAL_EMAIL=%%A"
)

if not defined LOCAL_EMAIL (
    git config --local user.email "%SAFE_EMAIL%"
)


REM ==================================================
REM 4/7 - SINCRONIZAR
REM ==================================================

echo.
echo [4/7] Sincronizando com o GitHub antes do envio...
echo.

git pull --rebase --autostash origin "%BRANCH%"

if errorlevel 1 (
    echo.
    echo ==============================================
    echo  ERRO DE SINCRONIZACAO
    echo ==============================================
    echo.
    echo Nao foi possivel sincronizar com o GitHub.
    echo Resolva qualquer conflito antes de tentar novamente.
    echo.
    echo Nenhum push foi realizado.
    echo.
    pause
    exit /b 1
)


REM ==================================================
REM 5/7 - ADICIONAR ARQUIVOS
REM ==================================================

echo.
echo [5/7] Adicionando arquivos permitidos pelo .gitignore...
echo.

git add -A

if errorlevel 1 goto :git_error


REM ==================================================
REM SEGUNDA VERIFICACAO DE SEGURANCA
REM ==================================================

echo.
echo Verificando novamente o conteudo antes do commit...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%\Verificar_Open_Source.ps1" -ProjectRoot "%PROJECT_DIR%"

if errorlevel 1 (

    git reset >nul 2>&1

    echo.
    echo ==============================================
    echo  ENVIO CANCELADO POR SEGURANCA
    echo ==============================================
    echo.
    echo O stage foi limpo.
    echo Nenhum commit ou push foi realizado.
    echo.
    pause
    exit /b 1
)


REM ==================================================
REM VERIFICAR SE EXISTEM MUDANCAS
REM ==================================================

git diff --cached --quiet

if not errorlevel 1 (
    echo.
    echo ==============================================
    echo  NENHUMA ALTERACAO PARA ENVIAR
    echo ==============================================
    echo.
    echo O repositorio ja esta atualizado.
    echo.
    pause
    exit /b 0
)


REM ==================================================
REM MOSTRAR O QUE SERA PUBLICADO
REM ==================================================

echo.
echo ==============================================
echo  ARQUIVOS QUE SERAO PUBLICADOS
echo ==============================================
echo.

git status --short

echo.
echo ==============================================
echo.


REM ==================================================
REM MENSAGEM DO COMMIT
REM ==================================================

set "COMMIT_MSG="

set /p "COMMIT_MSG=Mensagem do commit [Enter = Atualiza codigo-fonte]: "

if not defined COMMIT_MSG (
    set "COMMIT_MSG=Atualiza codigo-fonte"
)


REM ==================================================
REM 6/7 - COMMIT
REM ==================================================

echo.
echo [6/7] Criando commit...
echo.

git commit -m "%COMMIT_MSG%"

if errorlevel 1 goto :git_error


REM ==================================================
REM 7/7 - PUSH
REM ==================================================

echo.
echo [7/7] Enviando para GitHub...
echo.

git push -u origin "%BRANCH%"

if errorlevel 1 goto :git_error


REM ==================================================
REM SUCESSO
REM ==================================================

echo.
echo ==============================================
echo  ENVIO CONCLUIDO
echo ==============================================
echo.
echo Repositorio:
echo https://github.com/TruePabloEscobar/Analisador-de-Metadata-Musical
echo.
echo Branch:
echo %BRANCH%
echo.
echo O codigo foi enviado com sucesso.
echo.

pause
exit /b 0


REM ==================================================
REM ERRO GENERICO DO GIT
REM ==================================================

:git_error

echo.
echo ==============================================
echo  ERRO NO PROCESSO GIT
echo ==============================================
echo.
echo Algum comando Git falhou.
echo Leia a mensagem imediatamente acima para
echo identificar o problema.
echo.
echo Nenhum arquivo de audio foi alterado por este BAT.
echo.

pause
exit /b 1