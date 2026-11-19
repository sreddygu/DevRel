@echo off
setlocal EnableExtensions

REM Start CPU model server (llama.cpp) on Windows.
REM This does NOT use the NPU.
REM
REM Override defaults with env vars:
REM   LLAMA_SERVER_EXE, GGUF_MODEL, LLAMA_HOST, LLAMA_PORT, LLAMA_CTX, LLAMA_THREADS

set "LLAMA_SERVER_EXE_DEFAULT=%~dp0..\LLM\llama.cpp-win-arm64\llama-server.exe"
set "GGUF_MODEL_DEFAULT=%~dp0..\LLM\models\gemma-4-E4B-it-Q4_K_M.gguf"

if not defined LLAMA_SERVER_EXE set "LLAMA_SERVER_EXE=%LLAMA_SERVER_EXE_DEFAULT%"
if not defined GGUF_MODEL set "GGUF_MODEL=%GGUF_MODEL_DEFAULT%"
if not defined LLAMA_HOST set "LLAMA_HOST=0.0.0.0"
if not defined LLAMA_PORT set "LLAMA_PORT=8080"
if not defined LLAMA_CTX set "LLAMA_CTX=2048"
if not defined LLAMA_THREADS set "LLAMA_THREADS=8"

echo [cpu] llama-server: %LLAMA_SERVER_EXE%
echo [cpu] model:       %GGUF_MODEL%
echo [cpu] listen:      http://%LLAMA_HOST%:%LLAMA_PORT%
echo [cpu] ctx/threads: %LLAMA_CTX% / %LLAMA_THREADS%
echo.

if not exist "%LLAMA_SERVER_EXE%" (
  echo ERROR: missing llama-server.exe: %LLAMA_SERVER_EXE%
  exit /b 1
)
if not exist "%GGUF_MODEL%" (
  echo ERROR: missing GGUF model: %GGUF_MODEL%
  exit /b 1
)

"%LLAMA_SERVER_EXE%" ^
  -m "%GGUF_MODEL%" ^
  --host %LLAMA_HOST% --port %LLAMA_PORT% ^
  --ctx-size %LLAMA_CTX% --threads %LLAMA_THREADS%
