# J.A.R.V.I.S. v2 — Cerebro 3D Cibernético (100% gratis)

> Cerebro neuronal 3D animado · Ventana pequeña y redimensionable · IA LOCAL sin pagar

---

## ¿Qué cambió respecto a v1?

| Antes (v1) | Ahora (v2) |
|---|---|
| Solo escuchaba y respondía | **Crea, edita, abre y conecta** apps de uso diario |
| 600×600, fijo, muy grande | **380×380 por defecto** (pequeño y cómodo), ajustable a mano |
| Esfera genérica | **Cerebro humano cibernético**: 2 hemisferios + cerebelo, sinapsis e impulsos eléctricos viajando |
| Necesitaba Groq con tarjeta/key | **Cadena 100% gratis**: Ollama local → Groq (opcional) → cerebro offline |

---

## Tamaño manual (4 formas, se guarda solo)

1. **Arrastra la esquina inferior derecha** (◢) — el más fácil.
2. **Ctrl + rueda del ratón** sobre la ventana.
3. **Botones − / ＋** arriba a la derecha.
4. **Teclas Alt + ＋ / Alt + −** (Alt + 0 vuelve a 380).

Rango: 220 – 720 px. La posición y el tamaño quedan guardados en `jarvis_config.json`.

El botón **–** lo pone en modo mini (220 px).

---

## Instalación — 100% gratis

### 1. Librerías
```bat
INSTALAR.bat
```
(verifica Python, instala voz/sonido/gráfica, prepara `~/JarvisMemory`)

### 2. Cerebro local — Ollama vía API compatible con OpenAI
JARVIS usa tu modelo local como cerebro principal, **sin nube ni pagos**:

1. Descarga e instala Ollama desde <https://ollama.com/download>
2. Descarga los modelos:
```powershell
ollama pull qwen2.5:1.5b
ollama pull qwen3.5:9b
```
3. Comprueba que Ollama está arriba:
```powershell
ollama list
```

Conexión configurada en `jarvis_config.json`:
```json
{
  "openai_base_url": "http://localhost:11434/v1",
  "openai_api_key": "ollama",
  "openai_model": "qwen3.5:9b",
  "openai_disable_thinking": true,
  "fast_model": "qwen2.5:1.5b",
  "prefer_fast_model": true,
  "fast_timeout": 45,
  "fast_max_tokens": 320,
  "openai_max_tokens": 700
}
```

> JARVIS usa `/v1/chat/completions` con `Authorization: Bearer ollama`.
> Para conversación rápida responde primero con `fast_model` (`qwen2.5:1.5b`,
> ~3 s) y deja `qwen3.5:9b` como respaldo de más calidad si el rápido falla.
> `qwen3.5:9b` razona antes de responder; JARVIS envía `reasoning_effort: "none"`
> y `/no_think` para que conteste directo (sin eso el texto llega vacío y tarda ~1 minuto).
> Al arrancar se precarga el modelo rápido (`warmup_model`) para que la primera
> respuesta no espere la carga.
> Si una respuesta se corta por límite de tokens, JARVIS pide la continuación
> automáticamente y une las partes: **nunca entrega una respuesta a medias**.
>
> ### Micrófono (importante)
> JARVIS elige solo el micrófono de entrada real y descarta "Asignador de sonido",
> "Mezcla estéreo", altavoces y auriculares. En este equipo usa
> **"Varios micrófonos (2- Realtek(R) Audio)"**.
>
> Al arrancar, `pycaw` **desmutea el micrófono a nivel de Windows** y sube su
> volumen si estaba bajo. Ese era el motivo de que PyAudio capturara silencio
> (RMS 0) aunque el micrófono pareciera conectado. Además, JARVIS prueba cada
> candidato con una captura real y descarta los que devuelven silencio digital.
> Si el micrófono se ocupa o se desconecta, reintenta la conexión solo (hasta 6 veces).
>
> Si aun así no le escucha, pon el índice o el nombre exacto en `jarvis_config.json`:
> ```json
> { "mic_device_index": 1, "mic_device_name": "", "mic_auto_unmute": true }
> ```
> (mira la lista en `jarvis_log.txt` o ejecuta
> `python -c "import speech_recognition as sr; [print(i,n) for i,n in enumerate(sr.Microphone.list_microphone_names())]"`).
>
> ### Voz
> La voz es **Microsoft Helena (es-ES)** con `rate` 172 y volumen 1.0
> (`tts_rate` / `tts_volume` en `jarvis_config.json`). El watchdog del TTS es
> proporcional al largo del texto, así que las respuestas largas no se cortan.
>
> ### Clima y hora
> La hora, la fecha y el clima se resuelven en el router local, **antes** de
> llamar al modelo, para que JARVIS nunca diga "no puedo".
> El clima usa **Open-Meteo** (gratis, sin API key) y responde la temperatura
> real por voz; si no dices una ciudad, la ubica aproximadamente por IP
> (`weather_use_ip`). Puedes fijar tu ciudad en `jarvis_config.json`:
> ```json
> { "weather_city": "San José", "weather_use_ip": true }
> ```
>
> **Sin Ollama igual funciona**: las acciones directas (abrir, crear, buscar…)
> son instantáneas y gratuitas, y la conversación cae al cerebro offline. Con
> Wi-Fi, el reconocimiento de voz usa el servicio gratuito de Google (sin costo).

### 3. Arrancar
```bat
INICIAR_JARVIS.bat
```
Di **"Jarvis"** para activar y **"hasta luego"** para entrar en espera. También puedes escribir en la caja de texto de abajo.

---

## Ejemplos de lo que ya puede hacer

```
Jarvis, abre notepad
Jarvis, abre la calculadora
Jarvis, abre configuración
Jarvis, abre la cámara
Jarvis, abre Word
Jarvis, conecta spotify
Jarvis, crea una nota compras con texto leche huevos y pan
Jarvis, crea una carpeta mis proyectos en escritorio
Jarvis, abre notepad y luego abre calculadora
Jarvis, pon hola mundo en archivo compras
Jarvis, lee archivo compras
Jarvis, busca en google que es la fotosintesis
Jarvis, reproduce en youtube lofi
Jarvis, qué hora es
Jarvis, qué día es hoy
Jarvis, cómo está el clima
Jarvis, qué temperatura hace en Bogotá
Jarvis, sube el volumen
Jarvis, hazme una captura
Jarvis, recuérdame en 5 minutos tomar agua
Jarvis, lista mis archivos en escritorio
Jarvis, busca archivo factura
```

### Conectar tus propias apps sin tocar código
Edita `connected_apps.json`: clave = lo que dices, valor = ejecutable o URL.

```json
{
  "apps": { "mi app": "ruta\\a\\MiApp.exe" },
  "websites": { "mi plataforma": "https://..." }
}
```

### Archivos que crea
Todo lo que JARVIS crea va a `~/JarvisMemory` (o a Escritorio / Documentos / Descargas si lo pides). Luego puede editarlos y leerlos por voz.

---

## Arquitectura (en simple)

- `stark.py` — interfaz cerebro 3D + voz + automatización.
- `jarvis_config.json` — tamaño/posición/modelo (se auto-guardado).
- `connected_apps.json` — tus apps y sitios conectados.
- `requirements.txt` — librerías gratuitas.

Flujo: **orden → router local (¿acción clara? ejecutar ya) → si no, modelo rápido local (`qwen2.5:1.5b`) → si no, modelo grande (`qwen3.5:9b`) → si no, Groq (solo si hay key) → si no, offline**. Así nunca se queda en silencio y nunca gasta dinero.

Registros:
- `jarvis_log.txt` — todo lo que hace/escucha/falla JARVIS.
- `info_ciudad_mcp.txt` — consultas de ciudad/clima (se conserva y se amplía solo).
- `~/JarvisMemory/historial_voz.txt` — lo que se escuchó por micrófono.

---

## Qué sigue (si quieres v3)

- Voz 100% offline con Whisper local (`faster-whisper`) para no depender del Wi-Fi.
- Voz de clonación libre (Piper TTS) en lugar de pyttsx3.
- Atajos tipo "al decir X, haz Y" y rutinas de mañana.
- Panel de "aplicaciones conectadas" dentro del propio JARVIS.
