@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM deploy_to_siteground.bat
REM Deploys the OpenGenealogyAI static site (docs\) to SiteGround.
REM Windows version — uses WinSCP (preferred) or falls back to scp.
REM
REM BEFORE FIRST RUN:
REM   1. Fill in SITEGROUND_HOST below (find it in SiteGround Site Tools →
REM      SSH/SFTP → SSH Hostname, looks like "access1234.siteground.biz"
REM      or a bare IP like "185.93.x.x").
REM   2. Install WinSCP: https://winscp.net/eng/download.php
REM      (If WinSCP is not found, this script falls back to built-in scp.)
REM   3. Run from project root: scripts\deploy_to_siteground.bat
REM ─────────────────────────────────────────────────────────────────────────────

REM ── Config ──────────────────────────────────────────────────────────────────
SET SITEGROUND_HOST=
REM ↑ FILL THIS IN (e.g. SET SITEGROUND_HOST=access1234.siteground.biz)
SET SITEGROUND_USER=diamon69
SET SITEGROUND_PASS=#@*74Bd1$6HV
SET SITEGROUND_PORT=18765
SET REMOTE_DIR=public_html

REM ── Resolve paths ────────────────────────────────────────────────────────────
SET SCRIPT_DIR=%~dp0
SET LOCAL_DOCS=%SCRIPT_DIR%..\docs

REM ── Validation ───────────────────────────────────────────────────────────────
IF "%SITEGROUND_HOST%"=="" (
    echo ERROR: SITEGROUND_HOST is not set.
    echo Open this script and fill in the SITEGROUND_HOST variable.
    echo Find it in: SiteGround Site Tools ^> SSH/SFTP ^> SSH Hostname
    exit /b 1
)

IF NOT EXIST "%LOCAL_DOCS%" (
    echo ERROR: docs\ directory not found at: %LOCAL_DOCS%
    exit /b 1
)

REM ── Try WinSCP first ─────────────────────────────────────────────────────────
WHERE winscp.com >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo Deploying with WinSCP...
    echo Uploading docs\ to %SITEGROUND_USER%@%SITEGROUND_HOST%:/%REMOTE_DIR%/
    echo.

    REM Write a temporary WinSCP script
    SET WINSCP_SCRIPT=%TEMP%\winscp_deploy.txt
    (
        echo option batch abort
        echo option confirm off
        echo open sftp://%SITEGROUND_USER%:%SITEGROUND_PASS%@%SITEGROUND_HOST%:%SITEGROUND_PORT%/ -hostkey=*
        echo synchronize remote "%LOCAL_DOCS%" "/%REMOTE_DIR%"
        echo exit
    ) > "%WINSCP_SCRIPT%"

    winscp.com /script="%WINSCP_SCRIPT%"
    SET DEPLOY_EXIT=%ERRORLEVEL%
    DEL "%WINSCP_SCRIPT%" 2>nul

    IF %DEPLOY_EXIT% EQU 0 (
        echo.
        echo Deployment successful.
        echo Site should be live at: https://opengenealogyai.org
    ) ELSE (
        echo.
        echo Deployment FAILED via WinSCP ^(exit code: %DEPLOY_EXIT%^).
        echo Check the WinSCP log for details.
    )
    exit /b %DEPLOY_EXIT%
)

REM ── Fallback: built-in scp (Windows 10/11 OpenSSH) ───────────────────────────
WHERE scp >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo WinSCP not found. Falling back to scp...
    echo NOTE: scp will prompt for password. Enter: %SITEGROUND_PASS%
    echo.
    echo Uploading HTML files...
    scp -P %SITEGROUND_PORT% -r "%LOCAL_DOCS%\*.html" %SITEGROUND_USER%@%SITEGROUND_HOST%:~/%REMOTE_DIR%/
    echo Uploading css\...
    scp -P %SITEGROUND_PORT% -r "%LOCAL_DOCS%\css" %SITEGROUND_USER%@%SITEGROUND_HOST%:~/%REMOTE_DIR%/
    echo Uploading images\...
    scp -P %SITEGROUND_PORT% -r "%LOCAL_DOCS%\images" %SITEGROUND_USER%@%SITEGROUND_HOST%:~/%REMOTE_DIR%/

    IF %ERRORLEVEL% EQU 0 (
        echo.
        echo Deployment via scp complete.
        echo Site should be live at: https://opengenealogyai.org
    ) ELSE (
        echo.
        echo Deployment via scp FAILED.
        echo Try installing WinSCP for a more reliable transfer.
    )
    exit /b %ERRORLEVEL%
)

REM ── Neither tool found ────────────────────────────────────────────────────────
echo ERROR: Neither WinSCP nor scp found on this machine.
echo.
echo Options:
echo   1. Install WinSCP: https://winscp.net/eng/download.php
echo   2. Enable OpenSSH client: Settings ^> Optional Features ^> OpenSSH Client
echo   3. Use FileZilla (SFTP, port %SITEGROUND_PORT%) to upload docs\ manually
echo      Host: %SITEGROUND_HOST%
echo      User: %SITEGROUND_USER%
echo      Remote path: /%REMOTE_DIR%/
exit /b 1
