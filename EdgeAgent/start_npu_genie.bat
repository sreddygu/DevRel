@echo off
setlocal EnableExtensions

REM ===========================================================================
REM start_npu_genie.bat -- NPU (Genie/QAIRT) helper for Windows. Two modes:
REM
REM   start_npu_genie.bat          Start the OpenAI shim (genie_server.py) so the
REM                                agent/container can reach the NPU on :8081.
REM   start_npu_genie.bat test     Direct NPU sanity check -- run genie-t2t-run
REM                                against the bundle (NO HTTP, NO agent). Answers
REM                                "does the NPU stack itself work?" -- the first
REM                                thing to try when the server path misbehaves.
REM
REM Override any default with an env var:
REM   QAIRT_HOME, BUNDLE_DIR, GENIE_T2T_RUN, GENIE_HOST, GENIE_PORT,
REM   CHAT_TEMPLATE, MODEL_NAME
REM
REM NOTE: the bundle must live on a PLAIN local disk, NOT under C:\Dropbox.
REM Dropbox's filter driver blocks memory-mapping (genie_config.json has
REM "use-mmap":true), so loading from a synced path fails with "empty file /
REM nothing to deserialize" even though the .bin files are fully present. This
REM script refuses a C:\Dropbox bundle. See usage.md.
REM ===========================================================================

set "MODE=%~1"

set "QAIRT_HOME_DEFAULT=C:\Qualcomm\AIStack\QAIRT\2.51.40.260930"
set "BUNDLE_DIR_DEFAULT=C:\genie_bundle\qwen3_4b_instruct_2507-genie-w4a16-qualcomm_snapdragon_x_elite"

if not defined QAIRT_HOME set "QAIRT_HOME=%QAIRT_HOME_DEFAULT%"
if not defined BUNDLE_DIR set "BUNDLE_DIR=%BUNDLE_DIR_DEFAULT%"
if not defined GENIE_T2T_RUN set "GENIE_T2T_RUN=%QAIRT_HOME%\bin\aarch64-windows-msvc\genie-t2t-run.exe"
if not defined GENIE_HOST set "GENIE_HOST=127.0.0.1"
if not defined GENIE_PORT set "GENIE_PORT=8081"
if not defined CHAT_TEMPLATE set "CHAT_TEMPLATE=qwen"
if not defined MODEL_NAME set "MODEL_NAME=qwen3-4b-genie"

set "GENIE_SERVER_PY=%~dp0genie_server.py"
set "CONFIG_JSON=%BUNDLE_DIR%\genie_config.json"

REM --- Environment Genie/QNN needs to load the Hexagon skels -----------------
set "PATH=%QAIRT_HOME%\bin\aarch64-windows-msvc;%QAIRT_HOME%\lib\aarch64-windows-msvc;%PATH%"
set "ADSP_LIBRARY_PATH=%QAIRT_HOME%\lib\hexagon-v73\unsigned"

REM --- Shared checks: paths exist, and bundle is not under Dropbox -----------
if not exist "%GENIE_T2T_RUN%" (
  echo ERROR: missing genie-t2t-run.exe: %GENIE_T2T_RUN%
  echo        Check QAIRT_HOME matches an installed version.
  goto :fail
)
if not exist "%CONFIG_JSON%" (
  echo ERROR: bundle not found ^(no genie_config.json^): %BUNDLE_DIR%
  goto :fail
)
echo %BUNDLE_DIR% | findstr /I "\\Dropbox\\" >nul
if %errorlevel%==0 (
  echo ERROR: BUNDLE_DIR is under Dropbox -- Genie's mmap will fail there.
  echo        Copy the bundle to a plain path and re-run, e.g.:
  echo          robocopy "^<dropbox bundle^>" "C:\genie_bundle\^<name^>" /E
  goto :fail
)

if /I "%MODE%"=="test" goto :sanity_test
goto :start_server

REM ===========================================================================
:sanity_test
echo === Genie NPU sanity test (direct, no HTTP) ===
echo QAIRT_HOME : %QAIRT_HOME%
echo BUNDLE_DIR : %BUNDLE_DIR%
echo.
pushd "%BUNDLE_DIR%" || goto :fail
echo Running genie-t2t-run against sample_prompt.txt ...
echo.
"%GENIE_T2T_RUN%" -c genie_config.json --prompt_file sample_prompt.txt --log info
popd
echo.
echo === done ===
goto :end

REM ===========================================================================
:start_server
echo === Start Genie NPU shim (Terminal 1) ===
echo [npu] genie_server.py: %GENIE_SERVER_PY%
echo [npu] config:          %CONFIG_JSON%
echo [npu] binary:          %GENIE_T2T_RUN%
echo [npu] listen:          http://%GENIE_HOST%:%GENIE_PORT%   (model: %MODEL_NAME%, template: %CHAT_TEMPLATE%)
echo.
if not exist "%GENIE_SERVER_PY%" (
  echo ERROR: missing genie_server.py: %GENIE_SERVER_PY%
  goto :fail
)
REM IMPORTANT: run with CWD=bundle dir so relative ctx-bins/tokenizer paths resolve.
pushd "%BUNDLE_DIR%" || goto :fail
REM Use the active venv python if present; otherwise fall back to "python" on PATH.
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%GENIE_SERVER_PY%" ^
    --config ".\genie_config.json" ^
    --binary "%GENIE_T2T_RUN%" ^
    --chat-template "%CHAT_TEMPLATE%" ^
    --model-name "%MODEL_NAME%" ^
    --host "%GENIE_HOST%" --port %GENIE_PORT% ^
    --timeout 300
) else (
  python "%GENIE_SERVER_PY%" ^
    --config ".\genie_config.json" ^
    --binary "%GENIE_T2T_RUN%" ^
    --chat-template "%CHAT_TEMPLATE%" ^
    --model-name "%MODEL_NAME%" ^
    --host "%GENIE_HOST%" --port %GENIE_PORT% ^
    --timeout 300
)
popd
goto :end

:fail
endlocal
exit /b 1

:end
endlocal
