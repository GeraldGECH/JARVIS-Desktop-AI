@echo off
title JARVIS v2 - Instalador (gratis/local)
color 0B
echo.
echo  ============================================
echo      J.A.R.V.I.S v2 - Instalador
echo      100%% gratis, IA local con Ollama
echo  ============================================
echo.
echo [1/5] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python no encontrado. Instala desde https://python.org
    pause & exit
)
python --version
echo Python OK.
echo.
echo [2/5] Instalando librerias (voz, sonido, grafica)...
pip install -r requirements.txt
echo Librerias OK.
echo.
echo [3/5] IA LOCAL GRATIS - Ollama (opcional pero recomendado)...
echo  Ollama corre la IA en TU PC. Sin pagar, sin nube, sin limites.
echo  1. Descarga e instala: https://ollama.com/download
echo  2. Despues abre PowerShell y ejecuta:
echo       ollama pull qwen2.5:1.5b
echo       ollama pull qwen3.5:9b
echo  qwen2.5:1.5b = conversacion rapida (~3 s). qwen3.5:9b = respaldo de calidad.
echo  Sin Ollama igual funciona en modo offline + acciones.
echo.
echo [4/5] Verificando microfono...
python -c "import speech_recognition as sr; mics=sr.Microphone.list_microphone_names(); [print(f'  [{i}] {m}') for i,m in enumerate(mics)]"
echo.
echo  JARVIS desmutea el microfono oficial al arrancar (pycaw).
echo  Si Windows lo tiene muteado, lo corrige solo.
echo.
echo [5/5] Preparando memoria de JARVIS...
if not exist "%USERPROFILE%\JarvisMemory" mkdir "%USERPROFILE%\JarvisMemory"
echo.
echo  ============================================
echo   Listo! Ejecuta INICIAR_JARVIS.bat
echo  ============================================
pause
