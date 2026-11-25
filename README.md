# J.A.R.V.I.S. v2 — Asistente de escritorio con IA local

> Un asistente tipo JARVIS para Windows: habla, escucha, abre apps, consulta el clima/hora y conversa con modelos locales de Ollama. **Gratis, local y abierto a mejoras.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D6?logo=windows&logoColor=white)](#requisitos)
[![Ollama](https://img.shields.io/badge/IA-Ollama%20local-000000)](https://ollama.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Qué hace

- **Escucha por micrófono** y responde por voz (wake word: *"Jarvis"*).
- **Conversación natural** con personalidad cálida, humor sutil y respuestas sin cortarse.
- **IA local** con Ollama (OpenAI-compatible): `qwen2.5:1.5b` para rapidez y `qwen3.5:9b` como respaldo de calidad.
- **Acciones reales**: abre apps, busca en web, crea/edita archivos, controla volumen, toma capturas, recordatorios.
- **Clima y hora reales** desde el router local (Open-Meteo, sin API key) para que nunca responda "no puedo".
- **Interfaz cerebro 3D** en Tkinter: pequeña, transparente, siempre visible y redimensionable.
- **Sin costo obligatorio**: funciona sin pagar APIs; Groq es opcional.

## Demo rápida

```text
Jarvis, qué hora es
Jarvis, cómo está el clima en Medellín
Jarvis, abre la calculadora
Jarvis, abre Word
Jarvis, abre configuración
Jarvis, busca en google qué es la fotosíntesis
Jarvis, reproduce en youtube lofi
Jarvis, crea una nota compras con texto leche huevos y pan
Jarvis, recuérdame en 5 minutos tomar agua
```

## Requisitos

- Windows 10/11
- Python 3.10+ (recomendado 3.11/3.13)
- Micrófono funcional
- [Ollama](https://ollama.com/download) instalado para el modo IA local

## Instalación

### 1. Clonar el repo

```bash
git clone https://github.com/GeraldGECH/stark-python.git
cd stark-python
```

### 2. Instalar dependencias

```bat
INSTALAR.bat
```

O manualmente:

```bash
pip install -r requirements.txt
```

### 3. Instalar modelos de Ollama

```bash
ollama pull qwen2.5:1.5b
ollama pull qwen3.5:9b
```

### 4. Configurar (opcional)

Copia el ejemplo y ajusta tu micrófono, ciudad o voz:

```bat
copy jarvis_config.example.json jarvis_config.json
```

Campos útiles:

| Campo | Qué hace |
|---|---|
| `mic_device_index` | Índice del micrófono; `null` = autodetección |
| `mic_auto_unmute` | Desmutea el micrófono de Windows al iniciar |
| `weather_city` | Ciudad fija para clima, ej. `"San José"` |
| `tts_rate` | Velocidad de voz (172 recomendado) |
| `openai_model` | Modelo grande local (respaldo) |
| `fast_model` | Modelo rápido local (primera respuesta) |

### 5. Iniciar

```bat
INICIAR_JARVIS.bat
```

Di **"Jarvis"** para activar. Di **"hasta luego"** para ponerlo en espera. También puedes escribir en la caja de texto.

## Cómo funciona

```text
Voz/Texto
  -> Router local (hora, clima, abrir apps, archivos, volumen...)
      -> si no es acción clara: Ollama rápido (qwen2.5:1.5b)
          -> si falla: Ollama grande (qwen3.5:9b)
              -> si hay key: Groq opcional
                  -> fallback offline
  -> Respuesta por texto + TTS (proceso separado, sin cortar respuestas largas)
```

## Estructura del proyecto

```text
.
├── stark.py                     # App principal: UI 3D, voz, router, cerebro, automatización
├── tts_child.py                 # TTS en proceso separado (SAPI/pyttsx3)
├── requirements.txt             # Dependencias Python
├── jarvis_config.example.json   # Configuración de ejemplo
├── connected_apps.json          # Apps/sitios personalizados
├── INICIAR_JARVIS.bat           # Arranque en Windows
├── INSTALAR.bat                 # Instalador de dependencias
├── LEEME.md                     # Guía detallada en español
├── CONTRIBUTING.md              # Cómo contribuir
└── LICENSE                      # MIT
```

## Archivos generados en tu PC (no se suben al repo)

- `jarvis_config.json` — tu configuración local.
- `jarvis_log.txt` — logs de ejecución.
- `info_ciudad_mcp.txt` — historial de consultas de clima/ciudad.
- `~/JarvisMemory/` — notas, capturas e historial de voz.

## Problemas comunes

### JARVIS no me escucha
- Verifica que el micrófono correcto esté seleccionado por Windows.
- JARVIS intenta desmutear automáticamente el micrófono Realtek con `pycaw`.
- Revisa `jarvis_log.txt`; busca líneas `Mic:` y `Micro ... verificado`.
- Fija el micrófono en `jarvis_config.json` con `mic_device_index`.

### Responde lento
- El primer arranque puede tardar por el warmup del modelo.
- `qwen2.5:1.5b` es el modelo rápido; asegúrate de tenerlo instalado.
- Si usas CPU, el modelo grande puede tardar más: es normal.

### No abre una app
- Agrega la app en `connected_apps.json` con el nombre que dices y el ejecutable/ruta.
- También puedes pedirle que busque en web si no está instalada.

## Contribuir

Las mejoras son bienvenidas. Lee [CONTRIBUTING.md](CONTRIBUTING.md).

Ideas: Whisper offline, Piper TTS, más automatizaciones, mejor UI, soporte multiidioma, skills/rutinas.

## Licencia

[MIT](LICENSE). Puedes usarlo, modificarlo, compartirlo y mejorarlo libremente. Solo mantén el aviso de copyright.

## Autor

Creado por **[GeraldGECH](https://github.com/GeraldGECH)** como proyecto abierto para aprender, compartir y construir en comunidad.
