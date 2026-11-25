# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S. v2 - "Cerebro 3D Cibernetico"
================================================
- Cerebro neuronal 3D (hemisferios + sinapsis + impulsos electricos) animado.
- Ventana pequena (380px por defecto), transparente, siempre visible.
- TAMANO MANUAL: arrastra la esquina inferior derecha, Ctrl+rueda,
  botones -/+ , teclas Alt++ / Alt+- / Alt+0 . El tamano se guarda solo.
- 100% GRATIS y local. Cerebro principal = Ollama via API OpenAI:
    1) http://localhost:11434/v1 | key "ollama" | modelo qwen3.5:9b
    2) Groq (opcional) solo si hay API key configurada.
    3) Cerebro offline (reglas locales) si Ollama no responde.
- Automatizacion real: crea/edita archivos, abre apps, conecta web/apps,
  busca, volumen, capturas, recordatorios, etc.
"""
import tkinter as tk
import math, random, time, threading, requests, sys, os, re, json, unicodedata, shutil
import subprocess, webbrowser, queue, logging, traceback
from urllib.parse import quote_plus
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "jarvis_config.json"
APPS_PATH = BASE_DIR / "connected_apps.json"
LOG_PATH = BASE_DIR / "jarvis_log.txt"
CITY_INFO_PATH = BASE_DIR / "info_ciudad_mcp.txt"
MEMORY_DIR = Path.home() / "JarvisMemory"
DESKTOP_DIR = Path.home() / "Desktop"
DOCS_DIR = Path.home() / "Documents"
DOWNLOADS_DIR = Path.home() / "Downloads"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# ==================== LOG (si algo falla se queda apuntado, no desaparece) ====================
class FlushFileHandler(logging.FileHandler):
    """Cada linea se escribe al instante (si el proceso se cae, no se pierde)."""
    def emit(self, record):
        super().emit(record)
        try:
            self.flush()
        except Exception:
            pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[FlushFileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("jarvis")

# ==================== CONFIG ====================
DEFAULT_CONFIG = {
    "window_size": 380,          # <- tamano inicial (px). Cambiable a mano.
    "window_x": None,
    "window_y": None,
    # --- Cerebro principal: Ollama con API compatible OpenAI (100% local) ---
    "openai_base_url": "http://localhost:11434/v1",
    "openai_api_key": "ollama",
    "openai_model": "qwen3.5:9b",
    "openai_timeout": 75,        # limite del modelo grande (CPU)
    "openai_max_tokens": 700,    # margen amplio: nunca cortar la respuesta
    # qwen3.5 razona antes de responder; sin esto devuelve content vacio y tarda ~1 min
    "openai_disable_thinking": True,
    # --- Modelo rapido para conversacion en tiempo real ---
    "fast_model": "qwen2.5:1.5b",
    "prefer_fast_model": True,
    "fast_timeout": 45,
    "fast_max_tokens": 320,      # margen amplio: nunca cortar la respuesta
    "warmup_model": True,        # carga el modelo al iniciar (primera respuesta rapida)
    # --- Microfono: null = autodeteccion; o pon el indice/nombre exacto ---
    "mic_device_index": None,
    "mic_device_name": "",
    "mic_auto_unmute": True,     # desmutea el microfono oficial al arrancar (pycaw)
    # --- Voz (SAPI, local y gratis) ---
    "tts_rate": 172,             # 150 lento, 172 conversacional, 190 rapido
    "tts_volume": 1.0,
    "tts_voice_hint": "helena",  # 'helena' = Microsoft Helena (es-ES)
    # --- Clima real (Open-Meteo, gratis y sin API key) ---
    "weather_city": "",          # ej. "Bogota". Vacio = ubicacion por IP
    "weather_use_ip": True,
    # --- Respaldo opcional (no se usa si la key esta vacia) ---
    "groq_api_key": "",
    "groq_model": "llama-3.3-70b-versatile",
    "brain_enabled": True,
}
CONFIG = dict(DEFAULT_CONFIG)
_config_lock = threading.Lock()
if CONFIG_PATH.exists():
    try:
        CONFIG.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception as e:
        print(f"[CONFIG] {e}")
# Compatibilidad con configs viejas (ollama_url / ollama_model)
if CONFIG.get("openai_base_url") in (None, "") and CONFIG.get("ollama_url"):
    CONFIG["openai_base_url"] = str(CONFIG["ollama_url"]).rstrip("/") + "/v1"
if CONFIG.get("openai_model") in (None, "") and CONFIG.get("ollama_model"):
    CONFIG["openai_model"] = CONFIG["ollama_model"]
if not str(CONFIG.get("openai_api_key") or "").strip():
    CONFIG["openai_api_key"] = "ollama"
CONFIG["openai_base_url"] = str(CONFIG["openai_base_url"]).rstrip("/")

def save_config():
    try:
        with _config_lock:
            CONFIG_PATH.write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[CONFIG save] {e}")

WAKE_WORDS = ["jarvis", "oye jarvis", "hola jarvis", "hey jarvis"]
# Google en espanol transcribe "Jarvis" de muchas formas. Aceptamos variantes.
WAKE_RE = re.compile(
    r"\b(?:oye|hola|hey)?\s*(?:jarvis|yarvis|jarbis|jarbi|jervis|jarvi|harvis|javis)\b",
    re.IGNORECASE)
STOP_WORDS = ["hasta luego", "apagate", "apagate jarvis", "goodbye jarvis", "desactivate", "apagar jarvis"]
# Solo se entra en espera si la frase ES el comando de apagado, no si aparece
# dentro de una busquedad o de un video ("busca en google como apagar...").
STOP_EXACT = {
    "hasta luego", "apagate", "apagate jarvis", "goodbye jarvis",
    "desactivate", "apagar jarvis",
    "adios", "adios jarvis", "cerrate", "cerrate jarvis", "apaga jarvis",
}

def strip_wake(t):
    tt = norm(t)
    for w in sorted(WAKE_WORDS, key=len, reverse=True):
        tt = re.sub(r"\b" + re.escape(w) + r"\b", " ", tt)
    # Variantes que Google transcribe ("yarvis", "jarbis", "javis"...)
    tt = WAKE_RE.sub(" ", tt)
    return re.sub(r"\s+", " ", tt).strip(" .,-")

def is_stop_command(t):
    """True solo si la frase completa (sin 'jarvis') es de espera/apagado."""
    tt = strip_wake(t).strip(" .,-")
    return tt in STOP_EXACT

def has_wake_word(t):
    return bool(WAKE_RE.search(norm(t)))
SYSTEM_PROMPT = (
    "Eres JARVIS, el asistente personal de Iron Man: elegante, calido y con un humor seco muy sutil. "
    "Hablas en espanol latinoamericano, como una persona real en una conversacion: natural, cercana, "
    "con personalidad y sin sonar a manual. Llamas 'senor' al usuario con carino, no en cada frase. "
    "Respondes en 1 a 3 frases salvo que el usuario pida detalle. Nada de listas, vinetas, markdown ni emojis. "
    "Tienes control real del equipo: SI puedes abrir aplicaciones, consultar la hora, la fecha y el clima, "
    "buscar en internet, crear archivos y ajustar el volumen. Nunca digas que no puedes hacerlo. "
    "Si el usuario pide una accion (abrir, crear, editar, conectar, buscar), "
    "responde SOLO con JSON: {\"accion\":\"...\",\"params\":{...}} "
    "Acciones: abrir_app|crear_archivo|crear_carpeta|editar_archivo|abrir_web|buscar_web|"
    "volumen|lista_archivos|leer_archivo|captura|recordatorio|apagar_pc"
)

conversation_history = []
_tts_lock = threading.Lock()
_tts_engine = None
_pending_confirm = None  # (accion, params) esperando confirmacion
_speak_fn = None         # la app registra su funcion de hablar/mostrar

def say(text):
    if _speak_fn:
        _speak_fn(text)

# ==================== REGISTRO DE APPS CONECTABLES ====================
DEFAULT_APPS = {
    "apps": {
        "bloc de notas": "notepad.exe", "notepad": "notepad.exe",
        "calculadora": "calc.exe", "explorador": "explorer.exe",
        "explorador de archivos": "explorer.exe",
        "paint": "mspaint.exe", "terminal": "cmd.exe", "consola": "cmd.exe",
        "powershell": "powershell.exe", "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE", "powerpoint": "POWERPNT.EXE",
        "chrome": "chrome.exe", "edge": "msedge.exe", "firefox": "firefox.exe",
        "spotify": "Spotify.exe", "whatsapp": "WhatsApp.exe",
        "discord": "Discord.exe", "telegram": "Telegram.exe",
        "vlc": "vlc.exe", "netflix": "Netflix.exe",
        "administrador de tareas": "taskmgr.exe",
        "panel de control": "control.exe",
        "simbolo del sistema": "cmd.exe",
        "wordpad": "write.exe",
        "recortes": "snippingtool.exe",
        "camara": "microsoft.windows.camera:",
        "configuracion": "ms-settings:",
        "ajustes": "ms-settings:",
        "clima": "bingweather:",
        "mapas": "bingmaps:",
        "correo": "mailto:",
        "calendario": "outlookcal:",
    },
    "websites": {
        "youtube": "https://youtube.com", "google": "https://google.com",
        "gmail": "https://mail.google.com", "drive": "https://drive.google.com",
        "docs": "https://docs.google.com", "sheets": "https://sheets.google.com",
        "spotify web": "https://open.spotify.com", "whatsapp web": "https://web.whatsapp.com",
        "facebook": "https://facebook.com", "instagram": "https://instagram.com",
        "twitter": "https://x.com", "github": "https://github.com",
        "wikipedia": "https://es.wikipedia.org", "clima": "https://www.meteoblue.com",
        "noticias": "https://www.google.com/search?tbm=news&q=noticias",
    },
}
APP_REGISTRY = dict(DEFAULT_APPS)
if APPS_PATH.exists():
    try:
        user = json.loads(APPS_PATH.read_text(encoding="utf-8"))
        APP_REGISTRY["apps"].update(user.get("apps", {}))
        APP_REGISTRY["websites"].update(user.get("websites", {}))
    except Exception as e:
        print(f"[APPS] {e}")

# ==================== TTS (local, gratis) ====================
try:
    import pyttsx3
    HAS_TTS = True
except Exception:
    HAS_TTS = False
    print("[TTS] pyttsx3 no disponible")

def _tts_rate():
    try:
        return int(CONFIG.get("tts_rate", 172))
    except Exception:
        return 172

def _tts_volume():
    try:
        return float(CONFIG.get("tts_volume", 1.0))
    except Exception:
        return 1.0

def get_tts():
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = pyttsx3.init()
        voices = _tts_engine.getProperty('voices')
        hint = str(CONFIG.get("tts_voice_hint", "helena")).lower()
        spanish = next((v for v in voices if hint and hint in v.name.lower()), None)
        if not spanish:
            spanish = next((v for v in voices if any(x in v.name.lower()
                                                     for x in ['spanish', 'helena', 'sabina', 'es_'])), None)
        if spanish:
            _tts_engine.setProperty('voice', spanish.id)
        _tts_engine.setProperty('rate', _tts_rate())
        _tts_engine.setProperty('volume', _tts_volume())
    return _tts_engine

# Caracteres que no deben leerse en voz alta (emojis, simbolos decorativos)
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\uFE0F\u200D\u2190-\u21FF]"
)

def clean_for_speech(text):
    """Deja el texto listo para hablar: sin markdown, emojis ni JSON."""
    t = str(text or "")
    t = re.sub(r"```.*?```", " ", t, flags=re.DOTALL)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"!\[(.*?)\]\(.*?\)", r"\1", t)
    t = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", t)
    t = re.sub(r"(?m)^\s*#{1,6}\s*", "", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"__(.+?)__", r"\1", t)
    t = re.sub(r"(?<!\w)[*_](.+?)[*_](?!\w)", r"\1", t)
    t = re.sub(r"(?m)^\s*[-*•]\s+", "", t)
    t = _EMOJI_RE.sub("", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", " ", t)
    return t.strip()

def tts_timeout_for(text):
    """Watchdog proporcional al texto: una respuesta larga NUNCA se corta."""
    n = len(str(text or ""))
    return max(30.0, min(300.0, 15.0 + n * 0.17))

# Un solo audio a la vez: evita que SAPI (voz) y PortAudio (efectos) peleen
# y cuelguen el proceso tras abrir el navegador.
_audio_lock = threading.Lock()

def speak_threaded(text, on_done=None):
    """Habla en un PROCESO APARTE: si la voz se cae o se cuelga, JARVIS sigue vivo."""
    spoken = clean_for_speech(text)
    if not spoken:
        if on_done:
            on_done()
        return
    limit = tts_timeout_for(spoken)
    def _run():
        with _audio_lock:
            try:
                proc = subprocess.Popen(
                    [sys.executable, str(BASE_DIR / "tts_child.py"), spoken,
                     str(_tts_rate()), str(_tts_volume())],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    proc.wait(timeout=limit)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    log.warning("TTS se colgo (>%.0fs): proceso terminado, JARVIS sigue vivo", limit)
            except Exception:
                log.exception("TTS proceso fallo, respaldo en-proceso")
                try:
                    e = get_tts()
                    e.say(spoken)
                    e.runAndWait()
                except Exception:
                    log.exception("TTS respaldo fallo")
        if on_done:
            on_done()
    threading.Thread(target=_run, daemon=True).start()

# ==================== SONIDOS (sintetizados, gratis) ====================
try:
    import numpy as np
    import sounddevice as sd
    HAS_AUDIO = True
except Exception:
    HAS_AUDIO = False

def play_sound(kind):
    if not HAS_AUDIO:
        return
    def _play():
        if not _audio_lock.acquire(blocking=False):
            return  # la voz esta hablando: no interrumpir ni pelear audio
        try:
            r = 44100
            if kind == 'activate':
                t = np.linspace(0, 1.1, int(r * 1.1))
                wave = 0.16*np.sin(2*np.pi*(180+500*t)*t)*np.exp(-t*0.5) + 0.10*np.sin(2*np.pi*1200*t)*np.exp(-t*1.4)*(t > 0.4)
            elif kind == 'deactivate':
                t = np.linspace(0, 1.0, int(r))
                f = 1800 - 1600*t
                wave = 0.16*np.sin(2*np.pi*f*t)*(1-t*0.8)
            elif kind == 'listen':
                t = np.linspace(0, 0.35, int(r*0.35))
                wave = 0.13*np.sin(2*np.pi*900*t)*np.exp(-t*6) + 0.09*np.sin(2*np.pi*1500*t)*np.exp(-t*8)
            elif kind == 'ready':
                t = np.linspace(0, 0.4, int(r*0.4))
                wave = 0.11*np.sin(2*np.pi*1000*t)*np.exp(-t*5) + 0.09*np.sin(2*np.pi*1400*t)*np.exp(-t*6)
            elif kind == 'think':
                t = np.linspace(0, 0.8, int(r*0.8))
                wave = 0.07*np.sin(2*np.pi*(400+200*np.sin(2*np.pi*3*t))*t)
            elif kind == 'action':
                t = np.linspace(0, 0.25, int(r*0.25))
                wave = 0.14*np.sin(2*np.pi*2200*t)*np.exp(-t*12)
            else:
                return
            sd.play(np.clip(wave, -1, 1).astype(np.float32), r); sd.wait()
        except Exception as e:
            log.exception("Sound")
        finally:
            _audio_lock.release()
    threading.Thread(target=_play, daemon=True).start()

# ==================== UTILIDADES ====================
def norm(s):
    s = (s or "").lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.strip()

# ==================== REGISTRO info_ciudad_mcp.txt (se conserva) ====================
CITY_KEYWORDS = ("ciudad", "clima", "tiempo", "temperatura", "pronostico",
                 "lluvia", "municipio", "pais", "region", "humedad")
_city_lock = threading.Lock()

def save_city_info(query, reply):
    """Guarda consultas de ciudad/clima en info_ciudad_mcp.txt (ademas del log)."""
    try:
        if not query or not reply:
            return
        t = norm(query)
        if not any(k in t for k in CITY_KEYWORDS):
            return
        with _city_lock:
            new_file = not CITY_INFO_PATH.exists()
            with open(CITY_INFO_PATH, "a", encoding="utf-8") as fh:
                if new_file:
                    fh.write("=== INFO CIUDAD / MCP (JARVIS) ===\n")
                fh.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n")
                fh.write(f"Consulta: {query}\n")
                fh.write(f"Respuesta: {reply}\n")
    except Exception:
        log.exception("No se pudo escribir info_ciudad_mcp.txt")

def pick_dir(text):
    t = norm(text)
    if "escritorio" in t: return DESKTOP_DIR
    if "documento" in t: return DOCS_DIR
    if "descarga" in t: return DOWNLOADS_DIR
    return MEMORY_DIR

def safe_name(name, ext=""):
    name = (name or "jarvis_archivo").strip() or "jarvis_archivo"
    name = re.sub(r'[\\/:*?"<>|]', "_", name)[:60].strip() or "jarvis_archivo"
    p = Path(name)
    if ext and not p.suffix:
        p = p.with_suffix(ext)
    return p

# ==================== AUTOMATIZACION (crear / editar / conectar) ====================
def _app_key_matches(key, candidate):
    key, candidate = norm(key), norm(candidate)
    if not key or not candidate:
        return False
    if key == candidate:
        return True
    if len(candidate) >= 4 and candidate in key:
        return True
    if len(key) >= 4 and key in candidate:
        return True
    return False

def _find_app_paths(name):
    """Busca 'Nombre.exe' en App Paths del registro (Word, Excel, Chrome...)."""
    try:
        import winreg
    except Exception:
        return None
    wanted = norm(name)
    if not wanted.endswith(".exe"):
        wanted_exe = wanted + ".exe"
    else:
        wanted_exe = wanted
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        # 1) Coincidencia directa: App Paths\<nombre>.exe
        for sub in (wanted_exe, wanted):
            try:
                with winreg.OpenKey(root, base + "\\" + sub) as k:
                    path, _ = winreg.QueryValueEx(k, "")
                    if path and Path(path).exists():
                        return path
            except Exception:
                pass
        # 2) Recorrer todas las entradas y comparar por nombre
        try:
            with winreg.OpenKey(root, base) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    try:
                        sub = winreg.EnumKey(k, i)
                        subn = norm(sub)
                        if _app_key_matches(wanted, subn) or wanted in subn:
                            with winreg.OpenKey(k, sub) as sk:
                                path, _ = winreg.QueryValueEx(sk, "")
                                if path and Path(path).exists():
                                    return path
                    except Exception:
                        continue
        except Exception:
            pass
    return None

def find_app_exe(name):
    """Busca ejecutable por nombre en registro, PATH y Menu Inicio."""
    key = norm(name)
    if not key:
        return None
    # 1) Registro interno de apps conectadas (primero coincidencia exacta)
    for k, exe in APP_REGISTRY["apps"].items():
        if key == norm(k):
            return exe
    for k, exe in APP_REGISTRY["apps"].items():
        if _app_key_matches(key, k):
            return exe
    # 2) PATH del sistema
    for cand in (name, name + ".exe"):
        try:
            found = shutil.which(cand)
            if found:
                return found
        except Exception:
            pass
    # 3) App Paths (Word, Excel, Chrome, etc. instalados fuera del PATH)
    found = _find_app_paths(name)
    if found:
        return found
    # 4) Menu Inicio (accesos directos .lnk)
    start_dirs = [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
                  Path("C:/ProgramData/Microsoft/Windows/Start Menu/Programs")]
    # 4a) Coincidencia exacta / por palabras
    for root in start_dirs:
        if not root.exists():
            continue
        for lnk in root.rglob("*.lnk"):
            try:
                if _app_key_matches(key, lnk.stem):
                    return str(lnk)
            except Exception:
                continue
    # 4b) Coincidencia laxa (contiene)
    for root in start_dirs:
        if not root.exists():
            continue
        for lnk in root.rglob("*.lnk"):
            try:
                if key in norm(lnk.stem):
                    return str(lnk)
            except Exception:
                continue
    return None

def _launch_target(target):
    """Abre exe, .lnk, protocolo (ms-settings:) o shell:AppsFolder."""
    target = str(target or "").strip()
    if not target:
        return False
    try:
        os.startfile(target)
        return True
    except Exception as e:
        log.warning("os.startfile(%s) fallo: %s", target, e)
    try:
        subprocess.Popen([target], shell=False)
        return True
    except Exception as e:
        log.warning("Popen(%s) fallo: %s", target, e)
    try:
        subprocess.Popen(target, shell=True)
        return True
    except Exception:
        log.exception("No se pudo lanzar %s", target)
        return False

def open_in_browser(url):
    """Abre la URL en una pestana NUEVA sin cerrar otras ventanas/ventana JARVIS."""
    if not url or not str(url).strip():
        return False
    url = str(url).strip()
    if not url.startswith("http"):
        url = "https://" + url
    # 1) Navegador por defecto, en pestana nueva
    try:
        if webbrowser.open(url, new=1):
            log.info("Browser OK: %s", url[:120])
            return True
    except Exception:
        log.exception("webbrowser.open fallo")
    # 2) Respaldo: Chrome/Edge directos
    for name in ("chrome", "edge"):
        exe = find_app_exe(name)
        if exe:
            try:
                subprocess.Popen([exe, url])
                log.info("Browser directo OK (%s)", exe)
                return True
            except Exception:
                log.exception("browser directo fallo")
    return False

def do_open_app(name):
    raw = (name or "").strip(" .!¿?")
    raw = re.sub(r"^(el|la|los|las|mi|mis|un|una)\s+", "", raw, flags=re.IGNORECASE).strip()
    if not raw:
        return "¿Qué aplicación quiere que abra, señor?"
    exe = find_app_exe(raw)
    if not exe:
        # No esta instalado: conecta por web si existe, si no abre busqueda
        web = None
        for k, url in APP_REGISTRY["websites"].items():
            if norm(raw) in norm(k) or norm(k) in norm(raw):
                web = url; break
        if web:
            if not open_in_browser(web):
                return f"Señor, no pude abrir el navegador para {raw}."
            return f"Conectado señor, abriendo {raw} en el navegador."
        open_in_browser("https://www.google.com/search?q=" + quote_plus(raw))
        return f"Señor, {raw} no lo tengo instalado, le dejé la búsqueda abierta."
    if _launch_target(exe):
        log.info("App abierta: %s -> %s", raw, exe)
        return f"A sus órdenes señor, abriendo {raw}."
    return f"Disculpe señor, no pude abrir {raw}."

def clean_name(raw):
    """Quita 'en escritorio', 'en documentos', etc. del nombre."""
    n = norm(raw)
    n = re.sub(r"\s+en\s+(mi\s+|el\s+)?(escritorio|documentos?|descargas?|carpeta jarvis|carpeta de jarvis)\s*$", "", n)
    n = re.sub(r"^(una|un|la|el)\s+", "", n).strip(" .!¿?")
    return n or "jarvis_archivo"

def do_create(kind, name, content="", dest_text=""):
    folder = pick_dir(dest_text or name)
    folder.mkdir(parents=True, exist_ok=True)
    name = clean_name(name)
    if kind == "carpeta":
        p = folder / safe_name(name)
        p.mkdir(parents=True, exist_ok=True)
        return f"Carpeta creada señor: {p.name}."
    p = folder / safe_name(name, ".txt")
    p.write_text(content or "", encoding="utf-8")
    return f"Archivo creado señor: {p.name}."

def find_file_by_name(name):
    key = safe_name(name).stem.lower()
    for root in [MEMORY_DIR, DESKTOP_DIR, DOCS_DIR, DOWNLOADS_DIR]:
        if root.exists():
            for f in root.rglob("*"):
                if f.is_file() and f.stem.lower() == key:
                    return f
    for root in [MEMORY_DIR, DESKTOP_DIR]:
        if root.exists():
            for f in root.glob(f"*{key}*"):
                if f.is_file():
                    return f
    return None

def do_edit(name, mode, content):
    f = find_file_by_name(name)
    if not f:
        return f"Señor, no encontré el archivo {name}. Dígame el nombre exacto o créelo primero."
    if mode == "agregar":
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(("\n" if f.read_text(encoding="utf-8").strip() else "") + content + "\n")
    else:
        f.write_text(content, encoding="utf-8")
    return f"Actualizado señor: {f.name}."

def do_list(folder_text="escritorio"):
    root = pick_dir(folder_text)
    if not root.exists():
        return "No encontré esa carpeta, señor."
    items = list(root.iterdir())[:25]
    if not items:
        return f"La carpeta {root.name} está vacía, señor."
    nombres = ", ".join(i.name for i in items)
    return f"Tengo {len(items)} elementos en {root.name}: {nombres}."

def do_search_files(query):
    hits = []
    for root in [MEMORY_DIR, DESKTOP_DIR, DOCS_DIR, DOWNLOADS_DIR]:
        if root.exists():
            for f in root.rglob(f"*{query}*"):
                hits.append(f.name)
                if len(hits) >= 10:
                    break
    if not hits:
        return f"No encontré archivos con '{query}', señor."
    return "Encontré: " + ", ".join(hits) + "."

def do_volume(action):
    try:
        ps = {
            "subir": "(New-Object -ComObject WScript.Shell).SendKeys([char]175)",
            "bajar": "(New-Object -ComObject WScript.Shell).SendKeys([char]174)",
            "silencio": "(New-Object -ComObject WScript.Shell).SendKeys([char]173)",
        }[action]
        subprocess.Popen(["powershell", "-Command", ps + "; if($?) {exit 0}"], shell=False)
        return "Volumen ajustado, señor."
    except Exception as e:
        return f"Disculpe señor, no pude tocar el volumen: {e}"

def do_screenshot():
    try:
        from PIL import ImageGrab
        p = MEMORY_DIR / f"captura_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        ImageGrab.grab().save(p)
        return f"Captura guardada señor: {p.name}."
    except ImportError:
        subprocess.Popen(["powershell", "-Command",
            "[System.Windows.Forms.SendKeys]::SendWait('{PRTSC}')"], shell=False)
        return "Captura tomada señor, está en el portapapeles."
    except Exception as e:
        return f"No pude hacer la captura, señor: {e}"

def do_reminder(minutes, text):
    try:
        n = float(minutes)
    except Exception:
        n = 5.0
    def _w():
        time.sleep(n * 60)
        say(f"Señor, le recuerdo: {text}")
    threading.Thread(target=_w, daemon=True).start()
    return f"Recordatorio programado en {n} minutos, señor."

def do_shutdown(kind="apagar"):
    try:
        if kind == "reiniciar":
            subprocess.Popen(["shutdown", "/r", "/t", "30"])
        elif kind == "bloquear":
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
        else:
            subprocess.Popen(["shutdown", "/s", "/t", "30"])
        return f"De acuerdo señor, en 30 segundos {kind}é el equipo."
    except Exception as e:
        return f"No pude completar eso, señor: {e}"

def execute_action(accion, params=None):
    params = params or {}
    a = norm(accion)
    try:
        if a in ("abrir_app", "abrir", "open_app"):
            return do_open_app(params.get("app", params.get("name", "")))
        if a in ("abrir_web", "conectar", "open_web"):
            web = params.get("url", "")
            if not web:
                name = params.get("app", params.get("name", ""))
                for k, url in APP_REGISTRY["websites"].items():
                    if norm(name) in norm(k) or norm(k) in norm(name):
                        web = url; break
            if web:
                if not open_in_browser(web if web.startswith("http") else "https://" + web):
                    return "Señor, no pude abrir el navegador."
                return "Conectado señor."
            return "¿Qué sitio quiere abrir, señor?"
        if a in ("buscar_web", "buscar"):
            q = params.get("query", params.get("q", ""))
            if not open_in_browser("https://www.google.com/search?q=" + quote_plus(q)):
                return "Señor, no pude abrir el navegador."
            return "Búsqueda abierta, señor."
        if a in ("crear_archivo", "crear_nota"):
            return do_create("archivo", params.get("name", "nota"), params.get("content", ""))
        if a in ("crear_carpeta", "crear_carpeta"):
            return do_create("carpeta", params.get("name", "carpeta"))
        if a in ("editar_archivo", "escribir_archivo"):
            return do_edit(params.get("name", ""), params.get("mode", "escribir"), params.get("content", ""))
        if a in ("leer_archivo", "lee"):
            f = find_file_by_name(params.get("name", ""))
            if f:
                txt = f.read_text(encoding="utf-8", errors="ignore")[:600]
                return f"Dice {f.name}: {txt}"
            return "No encontré ese archivo, señor."
        if a in ("lista_archivos", "listar"):
            return do_list(params.get("folder", "escritorio"))
        if a in ("buscar_archivo",):
            return do_search_files(params.get("query", ""))
        if a in ("volumen",):
            return do_volume(params.get("como", "subir"))
        if a in ("captura", "captura_pantalla"):
            return do_screenshot()
        if a in ("recordatorio",):
            return do_reminder(params.get("minutos", 5), params.get("texto", "su recordatorio"))
        if a in ("apagar_pc", "reiniciar_pc", "bloquear_pc"):
            kind = {"apagar_pc": "apagar", "reiniciar_pc": "reiniciar", "bloquear_pc": "bloquear"}[a]
            return do_shutdown(kind)
    except Exception as e:
        return f"Disculpe señor, hubo un problema ejecutando eso: {e}"
    return None

# ==================== CLIMA REAL (Open-Meteo, gratis y sin API key) ====================
_WEATHER_LOCK = threading.Lock()
_WEATHER_CACHE = {"ts": 0.0, "key": None, "data": None}

_WEATHER_CODES = {
    0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado",
    3: "nublado", 45: "con niebla", 48: "con niebla helada",
    51: "con llovizna ligera", 53: "con llovizna", 55: "con llovizna fuerte",
    56: "con llovizna helada", 57: "con llovizna helada fuerte",
    61: "con lluvia ligera", 63: "con lluvia", 65: "con lluvia fuerte",
    66: "con lluvia helada", 67: "con lluvia helada fuerte",
    71: "con nevada ligera", 73: "con nevada", 75: "con nevada fuerte",
    77: "con nieve granular", 80: "con chubascos ligeros", 81: "con chubascos",
    82: "con chubascos fuertes", 85: "con chubascos de nieve",
    86: "con chubascos de nieve fuertes", 95: "con tormenta",
    96: "con tormenta y granizo", 99: "con tormenta fuerte y granizo",
}

def _weather_desc(code):
    try:
        return _WEATHER_CODES.get(int(code), "con el cielo cubierto")
    except Exception:
        return "con el cielo cubierto"

def get_weather(city=""):
    """Temperatura actual real vía Open-Meteo. Devuelve (texto|None, ciudad|None)."""
    key = norm(city or CONFIG.get("weather_city") or "")
    now = time.monotonic()
    with _WEATHER_LOCK:
        if (_WEATHER_CACHE["data"] and _WEATHER_CACHE["key"] == key
                and now - _WEATHER_CACHE["ts"] < 600):
            return _WEATHER_CACHE["data"]
    lat = lon = None
    place = city.strip() if city else ""
    try:
        if key:
            r = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                             params={"name": city, "count": 1, "language": "es", "format": "json"},
                             timeout=4)
            res = (r.json().get("results") or []) if r.status_code == 200 else []
            if res:
                lat, lon = res[0].get("latitude"), res[0].get("longitude")
                place = res[0].get("name") or place
        elif CONFIG.get("weather_use_ip", True):
            # Ubicacion aproximada por IP (dos servicios gratuitos, sin key)
            j = {}
            for url in ("https://ipwho.is/",
                        "http://ip-api.com/json/?fields=status,city,regionName,country,lat,lon"):
                try:
                    r = requests.get(url, timeout=4)
                    cand = r.json() if r.status_code == 200 else {}
                    if cand.get("success") is False or cand.get("status") == "fail":
                        cand = {}
                    if cand:
                        j = cand
                        break
                except Exception:
                    continue
            lat = j.get("latitude", j.get("lat"))
            lon = j.get("longitude", j.get("lon"))
            place = j.get("city") or j.get("region") or j.get("regionName") or ""
    except Exception as e:
        log.info("Clima: no pude ubicar la ciudad (%s)", e)
    if lat is None or lon is None:
        return None, (place or city or None)
    place = place or "su zona"
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "timezone": "auto",
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "weather_code,wind_speed_10m",
        }, timeout=4)
        cur = (r.json().get("current") or {}) if r.status_code == 200 else {}
        if "temperature_2m" not in cur:
            return None, place
        temp = float(cur.get("temperature_2m"))
        feels = cur.get("apparent_temperature")
        hum = cur.get("relative_humidity_2m")
        desc = _weather_desc(cur.get("weather_code"))
        txt = f"Ahora mismo en {place} hay {temp:.0f} grados y está {desc}"
        if feels is not None and abs(float(feels) - temp) >= 2:
            txt += f"; se siente como {float(feels):.0f}"
        if hum is not None:
            txt += f", con {float(hum):.0f} por ciento de humedad"
        txt += "."
        data = (txt, place)
        with _WEATHER_LOCK:
            _WEATHER_CACHE.update(ts=time.monotonic(), key=key, data=data)
        return data
    except Exception as e:
        log.info("Clima: no pude leer la temperatura (%s)", e)
        return None, place

# ==================== ROUTER LOCAL (rapido, gratis, sin IA) ====================
def local_route(text):
    global _pending_confirm
    t = norm(text)
    t = strip_wake(t) or t
    if not t:
        return None
    # Cadena: "... y luego ..." -> ejecuta en serie
    if (" y luego " in t or " luego " in t) and t.count("abre") + t.count("crea") >= 1:
        parts = re.split(r" y luego | luego ", t)
        out = []
        for p in parts:
            r = local_route(p.strip())
            if r:
                out.append(r)
        if out:
            return " ".join(out)

    # Pedir confirmacion primeramente
    if _pending_confirm and any(w in t for w in ["si", "dale", "adelante", "seguro", "confirmo"]):
        acc, prm = _pending_confirm
        _pending_confirm = None
        return execute_action(acc, prm)
    if _pending_confirm and any(w in t for w in ["no", "mejor no", "cancela"]):
        _pending_confirm = None
        return "Cancelado, señor."

    # --- Hora y fecha: respuesta inmediata, sin IA ---
    if (any(w in t for w in ("que hora es", "que horas son", "dime la hora",
                             "hora tienes", "me dices la hora", "hora actual"))
            or t.strip(" ?!.") in ("que hora", "la hora", "hora")):
        h = datetime.now()
        return f"Son las {h.strftime('%H:%M')}, señor. El tiempo vuela cuando hay buena compañía."
    if any(w in t for w in ("que dia es", "que fecha", "fecha de hoy", "dia de hoy",
                            "que dia estamos", "a que dia estamos")):
        h = datetime.now()
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                 "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        return (f"Hoy es {dias[h.weekday()]} {h.day} de {meses[h.month - 1]} "
                f"de {h.year}, señor.")

    # --- Clima: temperatura REAL + se abre la app/página (nunca "no puedo") ---
    if any(w in t for w in ("clima", "temperatura", "pronostico", "va a llover",
                            "esta lloviendo", "que tiempo hace", "como esta el tiempo",
                            "como esta el clima")):
        city = ""
        cm = re.search(r"(?:en|de|para)\s+([a-záéíóúñü\s]{3,30})[?.!¡¿]*$", t)
        if cm:
            city = cm.group(1).strip(" .!¿?")
        if city in ("mi zona", "mi ciudad", "aqui", "acá", "aca"):
            city = ""
        if city:
            try:
                CONFIG["weather_city"] = city
                save_config()
            except Exception:
                pass
            url = "https://www.google.com/search?q=" + quote_plus("clima " + city)
            extra = f" en {city}"
        else:
            url = "https://www.google.com/search?q=clima+hoy"
            extra = ""
        # 1) Temperatura real por voz (Open-Meteo)  2) abrir la página de detalle
        spoken, place = get_weather(city)
        opened = open_in_browser(url)
        if not opened:
            try:
                os.startfile("bingweather:")
                opened = True
            except Exception:
                opened = False
        if spoken:
            if opened:
                return spoken + " Le dejo el pronóstico abierto por si quiere más detalle, señor."
            return spoken
        if opened:
            return (f"Le abro el clima{extra}, señor. Ahí verá la temperatura y el pronóstico "
                    f"de su zona; si quiere otra ciudad, dígame cuál.")
        return "Señor, no pude consultar el clima en este momento. ¿Lo intento de nuevo?"

    m = re.search(r"(crea|crear|nuevo|nueva|haz|hacer) (una |un )?(nota|archivo|texto|carpeta|tarea|recordatorio|lista)\s+(?:llamada |denominada |que se llame )?(.+)", t)
    if m:
        kind = m.group(3)
        resto = m.group(4).strip()
        # "... con texto/contenido ..."
        content = ""
        cm = re.search(r"(con (texto|contenido|mensaje)|dice|que diga)\s+(.+)", resto)
        if cm:
            content = cm.group(3)
            resto = resto[:cm.start()].strip()
        if kind == "carpeta":
            return do_create("carpeta", resto, dest_text=t)
        return do_create("archivo", resto, content, dest_text=t)

    m = re.search(r"(escribe|escribir|pon|agrega|anade|edita|editar)\s+(.+?)\s+(en|al|a el|a|en el)\s*(?:archivo|nota)?\s*(.+)", t)
    if m:
        content = m.group(2).strip()
        name = m.group(4).strip()
        mode = "agregar" if m.group(1) in ("agrega", "anade", "pon") else "escribir"
        return do_edit(name, mode, content)

    m = re.search(r"(lee|leer|abre|abrir|muestra|muestrame) (el )?(archivo|nota)\s+(.+)", t)
    if m:
        return execute_action("leer_archivo", {"name": m.group(4)})

    m = re.search(r"(pon|reproduce|reproducir|suena|busca|buscar) en (youtube|spotify)\s+(.+)", t)
    if m:
        if m.group(2) == "youtube":
            url = "https://www.youtube.com/results?search_query=" + quote_plus(m.group(3))
        else:
            url = "https://open.spotify.com/search/" + quote_plus(m.group(3))
        if not open_in_browser(url):
            return "Señor, no pude abrir el navegador."
        return f"Reproduciendo {m.group(3)}, señor."

    m = re.search(r"(busca|buscar|buscame) (en )?(google )?(?:que es|que significa|como )?\s*(.+)", t)
    if m and m.group(4):
        q = m.group(4).strip()
        qn = norm(q)
        if not q or qn in ("google", "en google"):
            open_in_browser("https://www.google.com")
            return "Google abierto, señor."
        # Frase cortada sin contenido ("...que es la"): no buscar "la"
        if qn in ("la", "el", "de", "en", "que", "a", "al", "por", "un", "una", "como") or len(qn) < 2:
            return "Señor, no alcancé a escuchar qué quiere buscar. Dígame de nuevo, por favor."
        if not open_in_browser("https://www.google.com/search?q=" + quote_plus(q)):
            return "Señor, no pude abrir el navegador."
        return "Busqueda abierta, señor."

    if any(w in t for w in ["sube el volumen", "subir volumen", "mas volumen"]):
        return do_volume("subir")
    if any(w in t for w in ["baja el volumen", "bajar volumen", "menos volumen"]):
        return do_volume("bajar")
    if any(w in t for w in ["silencia", "silencia el volumen", "pon silencio"]):
        return do_volume("silencio")
    if "captura" in t or "pantallazo" in t:
        return do_screenshot()
    if "lista" in t and ("archivo" in t or "carpeta" in t):
        return do_list(t)
    if "busca" in t and "archivo" in t:
        m = re.search(r"busca (el )?archivo\s+(.+)", t)
        return do_search_files(m.group(2) if m else "")
    m = re.search(r"recuerdame (en (\d+(\.\d+)?) minutos?\s+)?(.+)", t)
    if m:
        mins = m.group(3) or 5
        return do_reminder(mins, m.group(4))
    m = re.search(r"(temporizador|alarma)( en (\d+(\.\d+)?) minutos?)?", t)
    if m and m.group(3):
        return do_reminder(m.group(3), "su alarma")
    if any(w in t for w in ["apaga la pc", "apaga el pc", "reinicia la pc", "bloquea la pc"]):
        kind = "apagar" if "apaga" in t else ("reiniciar" if "reinicia" in t else "bloquear")
        return do_shutdown(kind)

    # Abrir app / conectar web (solo si la frase EMPIEZA por el verbo)
    m_open = re.match(
        r"^(abre|abrir|abreme|abrime|lanza|lanzame|ejecuta|inicia|iniciame|"
        r"conecta|conectar|conectame|muestra|muestrame)\s+(.+)$", t)
    if m_open:
        rest = m_open.group(2).strip()
        rest = re.sub(r"^(el|la|los|las|mi|mis|un|una)\s+", "", rest)
        # web primero si coincide
        for k in sorted(APP_REGISTRY["websites"], key=len, reverse=True):
            if norm(k) in rest or rest in norm(k):
                return execute_action("abrir_web", {"app": rest})
        return do_open_app(rest)
    if t.strip(" ?!.") in ("abre", "abrir", "lanza", "ejecuta"):
        return "¿Qué desea que abra, señor?"

    return None

# ==================== CEREBRO PRINCIPAL: OLLAMA (API compatible OpenAI) ====================
# Base URL: http://localhost:11434/v1 | API Key: ollama | Modelo: qwen3.5:9b
def _openai_headers():
    return {
        "Authorization": f"Bearer {CONFIG.get('openai_api_key', 'ollama')}",
        "Content-Type": "application/json",
    }

_MODELS_CACHE = {"ts": 0.0, "ok": False, "names": []}
_MODELS_LOCK = threading.Lock()

def _fetch_models(force=False):
    """Lista los modelos de Ollama (/v1/models) con cache de 30 s."""
    now = time.monotonic()
    with _MODELS_LOCK:
        if not force and _MODELS_CACHE["ts"] and now - _MODELS_CACHE["ts"] < 30:
            return list(_MODELS_CACHE["names"]), _MODELS_CACHE["ok"]
    names, ok = [], False
    try:
        r = requests.get(CONFIG["openai_base_url"] + "/models",
                         headers=_openai_headers(), timeout=2.5)
        ok = r.status_code == 200
        if ok:
            names = [m.get("id") for m in (r.json().get("data") or []) if m.get("id")]
    except Exception:
        ok = False
    with _MODELS_LOCK:
        _MODELS_CACHE.update(ts=time.monotonic(), ok=ok, names=names)
    return names, ok

def ollama_up():
    """True si el endpoint OpenAI local responde."""
    _, ok = _fetch_models()
    return ok

def _available_model(name):
    """True si el modelo esta instalado (no bloquea si el endpoint no lista)."""
    names, _ = _fetch_models()
    return (not names) or (name in names)

def _model_chain():
    """Orden de intento: modelo rapido primero, luego el grande."""
    big = CONFIG.get("openai_model")
    fast = CONFIG.get("fast_model")
    chain = []
    if CONFIG.get("prefer_fast_model", True) and fast:
        chain.append((fast, int(CONFIG.get("fast_timeout", 45))))
    if big and all(m != big for m, _ in chain):
        chain.append((big, int(CONFIG.get("openai_timeout", 75))))
    if fast and all(m != fast for m, _ in chain):
        chain.append((fast, int(CONFIG.get("fast_timeout", 45))))
    return chain

# --- Microfono: elegir el dispositivo de ENTRADA correcto ---
_MIC_BAD = ("asignador", "sound mapper", "mapper", "mezcla", "stereo", "output",
            "altavoz", "speaker", "headphone", "auricular", "controlador primario",
            "salida", "primary")
_MIC_GOOD = ("microfono", "microphone", "mic array", "varios microfonos",
             "realtek", "mic input")

def ensure_microphone_ready():
    """Desmutear y subir volumen del microfono oficial de Windows (pycaw).

    El micrófono "Varios micrófonos (2- Realtek(R) Audio)" puede estar muteado
    a nivel de sistema; en ese caso PyAudio captura silencio (RMS 0) y JARVIS
    parece sordo. Esto lo corrige al arrancar el bucle de voz.
    """
    if not CONFIG.get("mic_auto_unmute", True):
        return False, "desactivado en config"
    try:
        from pycaw.pycaw import AudioUtilities
    except Exception as e:
        log.info("pycaw no disponible (%s); se usa el microfono tal cual", e)
        return False, "pycaw no disponible"
    changed = []
    try:
        devices = AudioUtilities.GetAllDevices()
    except Exception as e:
        log.warning("pycaw: no pude enumerar dispositivos: %s", e)
        return False, "sin dispositivos"
    for d in devices:
        try:
            name = getattr(d, "FriendlyName", "") or ""
            n = norm(name)
            if not n:
                continue
            state = getattr(getattr(d, "state", None), "name", "")
            if state and state != "Active":
                continue
            if any(b in n for b in _MIC_BAD):
                continue
            if not any(g in n for g in ("microfono", "microphone", "realtek", "mic array")):
                continue
            vol = d.EndpointVolume
            if vol is None:
                continue
            was_muted = bool(vol.GetMute())
            level = float(vol.GetMasterVolumeLevelScalar())
            if was_muted:
                vol.SetMute(0, None)
            if level < 0.80:
                vol.SetMasterVolumeLevelScalar(0.90, None)
            if was_muted or level < 0.80:
                changed.append(f"{name} (mute={was_muted}, vol={level:.2f})")
        except Exception:
            continue
    if changed:
        log.info("Mic listo: desmuteado/volumen ajustado -> %s", "; ".join(changed))
        return True, "; ".join(changed)
    log.info("Mic: endpoint de captura activo y sin mute")
    return True, "ok"

def probe_microphone(index, seconds=0.7):
    """Captura un instante del micro; detecta silencio digital (muteado).

    Devuelve (rms, peak) o None si no se pudo abrir.
    """
    try:
        import pyaudio
        import numpy as np
    except Exception:
        return None
    p = pyaudio.PyAudio()
    stream = None
    try:
        info = p.get_device_info_by_index(index)
        rate = int(info.get("defaultSampleRate", 44100) or 44100)
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=rate, input=True,
                        input_device_index=index, frames_per_buffer=1024)
        data = b""
        for _ in range(max(2, int(rate / 1024 * seconds))):
            data += stream.read(1024, exception_on_overflow=False)
        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        if arr.size == 0:
            return 0.0, 0
        rms = float(np.sqrt(np.mean(arr * arr)))
        peak = int(np.max(np.abs(arr)))
        return rms, peak
    except Exception as e:
        log.info("Prueba de micro %s fallo: %s", index, e)
        return None
    finally:
        try:
            if stream is not None:
                stream.stop_stream()
                stream.close()
        except Exception:
            pass
        try:
            p.terminate()
        except Exception:
            pass

def pick_microphone(sr):
    """Devuelve (indice, nombres). Evita 'Sound Mapper' y dispositivos de salida."""
    try:
        names = list(sr.Microphone.list_microphone_names())
    except Exception:
        log.exception("Listar microfonos fallo")
        return None, []

    def score(name):
        n = norm(name)
        if not n:
            return -1000
        s = 0
        if any(b in n for b in _MIC_BAD):
            s -= 100
        if any(g in n for g in _MIC_GOOD):
            s += 20
        if "realtek" in n:
            s += 15
        # El microfono oficial del equipo: "Varios microfonos (2- Realtek(R) Audio)"
        if "2- realtek" in n or "2 realtek" in n:
            s += 40
        if "varios microfonos" in n or "microphone array" in n:
            s += 15
        if "mic array" in n:
            s += 12
        if n.startswith("microfono") or n.startswith("varios microfonos"):
            s += 10
        if "input" in n and "output" not in n:
            s += 5
        if "bluetooth" in n or "hands-free" in n or "auriculares" in n:
            s -= 10
        return s

    forced_i = CONFIG.get("mic_device_index")
    if isinstance(forced_i, int) and 0 <= forced_i < len(names):
        log.info("Mic forzado por config: %s", forced_i)
        return forced_i, names
    forced_name = norm(CONFIG.get("mic_device_name") or "")
    if forced_name:
        for i, nm in enumerate(names):
            if forced_name in norm(nm):
                log.info("Mic forzado por nombre: %s", i)
                return i, names

    ranked = sorted(range(len(names)), key=lambda i: score(names[i]), reverse=True)
    # Comprobar que el dispositivo elegido se puede abrir y NO esta muteado.
    first_open = None
    probed = 0
    for i in ranked:
        if score(names[i]) <= 0:
            break
        try:
            with sr.Microphone(device_index=i):
                pass
        except Exception:
            continue
        if first_open is None:
            first_open = i
        if probed < 4:
            probed += 1
            res = probe_microphone(i)
            if res:
                rms, peak = res
                if peak > 1 and rms > 1e-6:
                    log.info("Micro %s verificado: %s (rms=%.5f peak=%d)",
                             i, names[i], rms, peak)
                    return i, names
                log.warning("Micro %s en silencio digital (muteado): %s",
                            i, names[i])
                continue
        return i, names
    if first_open is not None:
        log.warning("Ningun micro con senal; uso %s (%s)", first_open, names[first_open])
        return first_open, names
    return (ranked[0] if ranked else None), names

def warmup_model():
    """Precarga el modelo rapido para que la primera respuesta no tarde."""
    if not CONFIG.get("warmup_model", True):
        return
    def _w():
        chain = _model_chain()
        if not chain:
            return
        model, _ = chain[0]
        if not _available_model(model):
            return
        payload = {"model": model, "stream": False, "max_tokens": 1,
                   "keep_alive": "2h",
                   "messages": [{"role": "user", "content": "hola"}]}
        try:
            t0 = time.monotonic()
            requests.post(CONFIG["openai_base_url"] + "/chat/completions",
                          json=payload, headers=_openai_headers(), timeout=120)
            log.info("Warmup %s listo en %.1fs", model, time.monotonic() - t0)
        except Exception as e:
            log.warning("Warmup %s fallo: %s", model, e)
    threading.Thread(target=_w, daemon=True).start()

def _clean_model_text(text):
    """Quita bloques de razonamiento que algunos modelos filtran al texto."""
    if not text:
        return ""
    text = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^\s*Thinking Process:.*?(?=\n\n\S)", "", text, flags=re.DOTALL)
    return text.strip()

def _join_reply_parts(parts):
    out = ""
    for part in parts:
        part = (part or "").strip()
        if not part:
            continue
        if not out:
            out = part
        elif out[-1] in " \n" or out.endswith(("(", "¿", "¡")):
            out += part
        elif part[0] in ",.;:!?)]}":
            out += part
        else:
            out += " " + part
    return out.strip()

def _ollama_post(payload, timeout):
    r = requests.post(CONFIG["openai_base_url"] + "/chat/completions",
                      json=payload, headers=_openai_headers(), timeout=timeout)
    if r.status_code == 400 and "reasoning_effort" in payload:
        # Servidor/modelo que no acepta reasoning_effort: reintento limpio
        payload = dict(payload)
        payload.pop("reasoning_effort", None)
        r = requests.post(CONFIG["openai_base_url"] + "/chat/completions",
                          json=payload, headers=_openai_headers(), timeout=timeout)
    r.raise_for_status()
    return r.json()

def ask_ollama(user_text, model=None, timeout=None):
    """Genera texto contra Ollama via /v1/chat/completions (compatible OpenAI).

    Si la respuesta se corta por limite de tokens (finish_reason == 'length'),
    pide la continuacion automaticamente y une las partes: nunca se entrega
    una respuesta a medias.
    """
    model = model or CONFIG["openai_model"]
    timeout = int(timeout or CONFIG.get("openai_timeout", 75))
    deadline = time.monotonic() + timeout
    is_big = (model == CONFIG.get("openai_model"))
    max_tokens = int(CONFIG.get("openai_max_tokens", 700) if is_big
                     else CONFIG.get("fast_max_tokens", 320))
    prompt = user_text
    # qwen3 razona antes de responder: /no_think + reasoning_effort lo desactivan
    if is_big and "qwen3" in model.lower() and "/no_think" not in prompt:
        prompt = prompt + " /no_think"
    system_prompt = SYSTEM_PROMPT
    if not is_big:
        system_prompt += (" Responde en 1 a 3 frases, con naturalidad y humor, "
                          "sin listas ni markdown.")
    msgs = [{"role": "system", "content": system_prompt}]
    msgs += conversation_history[-4:]          # menos historial = menos latencia
    msgs.append({"role": "user", "content": prompt})
    base_payload = {
        "model": model,
        "stream": False,
        "temperature": 0.7 if is_big else 0.6,
        "max_tokens": max_tokens,
        "keep_alive": "2h",
    }
    if is_big and CONFIG.get("openai_disable_thinking", True):
        base_payload["reasoning_effort"] = "none"
    parts = []
    finish = None
    try:
        t0 = time.monotonic()
        for attempt in range(3):
            remaining = deadline - time.monotonic()
            if remaining <= 2:
                break
            payload = dict(base_payload)
            payload["messages"] = list(msgs)
            data = _ollama_post(payload, min(remaining, timeout))
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            part = _clean_model_text(msg.get("content") or "")
            finish = choice.get("finish_reason")
            if part:
                parts.append(part)
            if finish != "length":
                break
            if not part:
                log.warning("Ollama (%s) corto sin texto (finish=length); no se puede continuar", model)
                break
            # Continuacion: el modelo retoma exactamente donde se quedo.
            msgs = msgs + [
                {"role": "assistant", "content": _join_reply_parts(parts)},
                {"role": "user", "content":
                 "Continua exactamente donde te quedaste, sin repetir nada y sin despedirte."},
            ]
            log.info("Ollama (%s) respuesta cortada por limite; pidiendo continuacion (%d chars)",
                     model, len(_join_reply_parts(parts)))
        reply = _join_reply_parts(parts)
        if not reply:
            # El modelo solo devolvio razonamiento: no lo usamos como respuesta.
            log.warning("Ollama (%s) devolvio content vacio (finish=%s)", model, finish)
            return None
        conversation_history.append({"role": "user", "content": user_text})
        conversation_history.append({"role": "assistant", "content": reply})
        while len(conversation_history) > 12:
            conversation_history.pop(0)
        log.info("Ollama OK (%s) en %.1fs: %d chars (finish=%s)",
                 model, time.monotonic() - t0, len(reply), finish)
        return reply
    except requests.exceptions.Timeout:
        log.error("Ollama timeout tras %ss (%s)", timeout, model)
        # Si ya tenemos texto, lo entregamos completo en vez de perderlo.
        partial = _join_reply_parts(parts)
        return partial or None
    except Exception as e:
        log.warning("Ollama (%s) fallo: %s", model, e)
        partial = _join_reply_parts(parts)
        return partial or None

def ask_groq(user_text):
    key = CONFIG.get("groq_api_key", "").strip()
    if not key:
        return None
    conversation_history.append({"role": "user", "content": user_text})
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history[-6:]
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            json={"model": CONFIG["groq_model"], "messages": msgs, "max_tokens": 800, "temperature": 0.85},
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, timeout=15)
        reply = r.json()["choices"][0]["message"]["content"].strip()
        conversation_history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"[Groq] {e}")
        return None

def parse_json_action(reply):
    if not reply:
        return None, None
    m = re.search(r"\{.*\}", reply, re.DOTALL)
    if not m:
        return None, reply
    try:
        obj = json.loads(m.group(0))
        acc = obj.get("accion") or obj.get("action")
        prm = obj.get("params", {})
        if acc and isinstance(prm, dict):
            return (acc, prm), None
    except Exception:
        pass
    # Texto normal sin JSON valido: limpiar
    clean = reply.strip().strip("`").strip()
    if clean.startswith("{"):
        return None, "Disculpe señor, no entendí esa acción."
    return None, clean

def offline_brain(text):
    t = norm(text)
    h = datetime.now()
    if any(w in t for w in ["hola", "buenas"]):
        return f"Hola señor, a sus órdenes. Son las {h.strftime('%H:%M')}."
    if "como estas" in t or "como te va" in t:
        return "Operando al cien por cien, señor. ¿En qué le ayudo?"
    if "quien eres" in t or "que eres" in t or "tu nombre" in t:
        return "Soy JARVIS señor, su asistente personal. Puedo escucharle, hablarle, crear archivos y conectar sus aplicaciones."
    if "que sabes hacer" in t or "que puedes hacer" in t:
        return "Puedo abrir aplicaciones, crear y editar archivos, conectar sus sitios, buscar en internet, ajustar volumen y recordarle cosas, señor."
    if "que hora" in t:
        return f"Son las {h.strftime('%H:%M')}, señor."
    if "que dia" in t or "fecha" in t:
        return f"Hoy es {h.strftime('%A %d de %B')}, señor."
    if "chiste" in t:
        return "¿Por qué los programadores confunden Halloween con Navidad? Porque OCT 31 == DEC 25, señor."
    if "gracias" in t:
        return "A sus órdenes, señor."
    if "clima" in t or "tiempo hace" in t:
        open_in_browser("https://www.meteoblue.com")
        return "Le abrí el pronóstico del clima, señor."
    if "apagar" in t or "hasta luego" in t:
        return "Hasta pronto señor, entro en espera."
    return ("Señor, el cerebro local no respondió a tiempo. "
            "Puedo abrirle una búsqueda en internet o ejecutar una acción directa; "
            "dígame 'busca ...' si lo desea.")

def ask_brain(user_text):
    """Cadena: modelo rapido local -> modelo grande local -> Groq -> offline."""
    global _pending_confirm
    # 1) Ollama local (rapido primero para conversacion en tiempo real)
    if CONFIG.get("brain_enabled", True) and ollama_up():
        for model, tmo in _model_chain():
            if not _available_model(model):
                continue
            reply = ask_ollama(user_text, model=model, timeout=tmo)
            if not reply:
                continue
            acc, clean = parse_json_action(reply)
            if acc:
                act, prm = acc
                if norm(act) in ("apagar_pc", "reiniciar_pc"):
                    _pending_confirm = (act, prm)
                    return "¿Seguro señor? Diga 'sí' para confirmar, o 'no' para cancelar."
                res = execute_action(act, prm)
                return res or "Hecho, señor."
            return clean or reply
        log.warning("Ningun modelo local respondio; usando respaldo")
    # 2) Groq si hay key
    reply = ask_groq(user_text)
    if reply:
        acc, clean = parse_json_action(reply)
        if acc:
            res = execute_action(acc[0], acc[1])
            return res or "Hecho, señor."
        return clean or reply
    # 3) Offline
    return offline_brain(user_text)

# ==================== CEREBRO 3D CIBERNETICO ====================
class BrainCanvas(tk.Canvas):
    """Cerebro humano cibernetico: 2 hemisferios neuronales + cerebelo."""
    def __init__(self, master, size=380, **kw):
        super().__init__(master, width=size, height=size, bg='black',
                         highlightthickness=0, **kw)
        self.state = 'inactive'
        self.t = 0.0
        self.rot_y = 0.0
        self.rot_x = 0.0
        self.center_angle = 0.0
        self.size = size
        self.set_size(size)
        self._animate()

    def set_size(self, size):
        self.size = int(size)
        self.config(width=self.size, height=self.size)
        self.cx = self.size / 2
        self.cy = self.size / 2 - 6
        self.R = self.size / 2 - 8
        self._build()

    def _build(self):
        R = self.R
        nodes = []
        def ellipsoid_surface(center, radii, n):
            cx, cy, cz = center; rx, ry, rz = radii
            out = []
            for _ in range(n):
                # direccion aleatoria en la esfera
                th = random.uniform(0, math.tau)
                z = random.uniform(-1, 1)
                s = math.sqrt(max(0, 1 - z*z))
                x, y, zz = s*math.cos(th), s*math.sin(th), z
                # desplaza ligeramente para dar forma cerebelo/hemisferio
                out.append({
                    'u': cx + x*rx, 'v': cy + y*ry, 'w': cz + zz*rz,
                    'pulse': random.random()*math.tau,
                    'ps': random.uniform(0.02, 0.045),
                    'size': random.uniform(1.2, 2.8),
                    'hemi': 'L' if cx < 0 else 'R',
                    'fire': 0.0,
                })
            return out
        # Hemisferios: elipsoidales, aplanados abajo, alargados adelante-atras
        nodes += ellipsoid_surface((-0.33, 0.06, -0.02), (0.52, 0.44, 0.70), 95)
        nodes += ellipsoid_surface((0.33, 0.06, -0.02), (0.52, 0.44, 0.70), 95)
        # Lóbulo frontal: bulge extra adelante (z positivo)
        nodes += ellipsoid_surface((0, 0.10, 0.55), (0.42, 0.34, 0.30), 30)
        # Cerebelo (abajo atras, mas pequeno y aplanado)
        nodes += ellipsoid_surface((0, -0.48, -0.58), (0.36, 0.17, 0.28), 36)
        # Tronco: columna corta hacia abajo
        nodes += ellipsoid_surface((0, -0.55, -0.15), (0.10, 0.30, 0.10), 12)
        self.nodes = nodes
        # Sinapsis precomputadas (vecinos 3D cercanos) -> rapido y estable
        self.links = []
        for i, a in enumerate(nodes):
            dists = sorted(((math.dist((a['u'], a['v'], a['w']), (b['u'], b['v'], b['w'])), j)
                            for j, b in enumerate(nodes) if j != i))[:3]
            for d, j in dists:
                if d < 0.42:
                    key = (min(i, j), max(i, j))
                    if key not in self.links:
                        self.links.append(key)
        self.impulses = []   # pulsos electricos viajando por sinapsis
        for _ in range(10):
            self._new_impulse(random.random())
        self.rings = [
            {'r': R*0.95, 'speed': 0.003, 'dash': 22, 'gap': 7,  'w': 1.1, 'off': 0.0},
            {'r': R*0.85, 'speed': -0.005, 'dash': 10, 'gap': 5,  'w': 0.7, 'off': 1.0},
            {'r': R*0.74, 'speed': 0.008, 'dash': 5,  'gap': 4,  'w': 1.2, 'off': 2.0},
        ]
        self.data_labels = [
            ('SYS:OK', math.radians(30), R*0.9),
            ('NET:ON', math.radians(150), R*0.9),
            ('CPU:ON', math.radians(270), R*0.9),
        ]

    def _new_impulse(self, t=0.0):
        if not self.links:
            return
        i, j = random.choice(self.links)
        self.impulses.append({'a': i, 'b': j, 't': t, 'speed': random.uniform(0.015, 0.03)})

    def _color(self):
        s = self.state
        if s == 'listening': return (255, 90, 20), (255, 165, 90)
        if s == 'thinking':  return (255, 200, 0), (255, 240, 120)
        if s == 'speaking':  return (0, 255, 130), (120, 255, 190)
        if s == 'inactive':  return (30, 70, 110), (60, 120, 160)
        return (0, 200, 255), (110, 235, 255)

    def _proj(self, n):
        u, v, w = n['u'], n['v'], n['w']
        cy_, sy_ = math.cos(self.rot_y), math.sin(self.rot_y)
        cx_, sx_ = math.cos(self.rot_x), math.sin(self.rot_x)
        breathe = 1.0 + 0.025*math.sin(self.t*1.4)
        u, v, w = u*breathe, v*breathe, w*breathe
        x1 = u*cy_ - w*sy_
        z1 = u*sy_ + w*cy_
        y1 = v*cx_ - z1*sx_
        z2 = v*sx_ + z1*cx_
        sc = 1.9 / (1.9 + z2*0.7)
        return (self.cx + x1*self.R*sc, self.cy - y1*self.R*sc, z2, sc)

    def _hex(self, r, g, b, a=1.0):
        a = max(0.0, min(1.0, a))
        return f"#{int(r*a):02x}{int(g*a):02x}{int(b*a):02x}"

    def _animate(self):
        self.delete('all')
        self.t += 0.016
        active = self.state != 'inactive'
        self.rot_y += 0.005 if active else 0.0007
        self.rot_x = math.sin(self.t*0.25)*0.18
        self.center_angle += 0.03
        mr, mg, mb = self._color()[0]
        hr, hg, hb = self._color()[1]

        # Anillo orbita inclinado (halo)
        for ring in self.rings:
            ring['off'] += ring['speed']
            r = ring['r']
            self.create_oval(self.cx-r, self.cy-r, self.cx+r, self.cy+r,
                             outline=self._hex(mr, mg, mb, 0.10 if active else 0.05), width=1)
            total = ring['dash'] + ring['gap']
            segs = max(4, int(math.tau*r/total))
            for i in range(segs):
                a0 = ring['off'] + i*math.tau/segs
                a1 = a0 + (ring['dash']/(r*math.tau))*math.tau
                self.create_arc(self.cx-r, self.cy-r, self.cx+r, self.cy+r,
                                start=math.degrees(a0), extent=math.degrees(a1-a0),
                                style='arc', outline=self._hex(mr, mg, mb, 0.55 if active else 0.18),
                                width=ring['w'])

        # Proyeccion ordenada por profundidad
        pts = [(self._proj(n), n) for n in self.nodes]
        # Hemisferios: disco translucido detras
        if active:
            for sgn in (-1, 1):
                hx = self.cx + sgn*self.R*0.28*math.cos(self.rot_y)
                hy = self.cy - self.R*0.02
                hr_ = self.R*0.48
                self.create_oval(hx-hr_, hy-hr_*0.85, hx+hr_, hy+hr_*0.85,
                                 fill=self._hex(mr, mg, mb, 0.05), outline=self._hex(mr, mg, mb, 0.18), width=1)

        # Sinapsis
        for i, j in self.links:
            (ax, ay, az, _), _n1 = pts[i]
            (bx, by, bz, _), _n2 = pts[j]
            d = math.hypot(ax-bx, ay-by)
            if d > self.R*0.45:
                continue
            depth = max(0.15, 1 - abs((az+bz)/2)/1.6)
            a = (0.34 if active else 0.08) * depth * max(0.3, 1 - d/(self.R*0.45))
            self.create_line(ax, ay, bx, by, fill=self._hex(mr, mg, mb, a), width=0.8)

        # Impulsos electricos
        if active and random.random() < 0.18 and len(self.impulses) < 16:
            self._new_impulse()
        alive = []
        for imp in self.impulses:
            imp['t'] += imp['speed']
            if imp['t'] >= 1.0:
                if active:
                    self._new_impulse(random.random()*0.2)
                continue
            alive.append(imp)
            (ax, ay, _, _), na = pts[imp['a']]
            (bx, by, _, _), nb = pts[imp['b']]
            px = ax + (bx-ax)*imp['t']; py = ay + (by-ay)*imp['t']
            na['fire'] = 1.0; nb['fire'] = max(nb['fire'], imp['t'])
            for rr, aa in [(9, 0.10), (5, 0.20), (2.5, 0.9)]:
                self.create_oval(px-rr, py-rr, px+rr, py+rr,
                                 fill=self._hex(hr, hg, hb, aa), outline='')
        self.impulses = alive

        # Neuronas (ordenadas back-to-front)
        for (px, py, pz, sc), n in sorted(pts, key=lambda p: p[0][2]):
            n['pulse'] += n['ps']
            glow = 0.5 + math.sin(n['pulse'])*0.5
            fire = n.get('fire', 0.0)
            depth = max(0.25, 1 - abs(pz)/1.8)
            sz = n['size']*sc*(1.0 + glow*0.35 + fire*1.2) if active else n['size']*sc*0.5
            al = ((0.45 + glow*0.5 + fire*0.6) if active else 0.18) * depth
            self.create_oval(px-sz, py-sz, px+sz, py+sz,
                             fill=self._hex(mr, mg, mb, al), outline='')
            if active and (glow > 0.85 or fire > 0.3):
                cs = max(0.6, sz*0.45)
                self.create_oval(px-cs, py-cs, px+cs, py+cs,
                                 fill=self._hex(hr, hg, hb, 0.85), outline='')
            n['fire'] = max(0.0, fire - 0.04)

        # Nucleo central (tronco)
        core_r = 7 if not active else 9 + 1.5*math.sin(self.t*3)
        if active:
            for cr, ca in [(core_r*3.2, 0.06), (core_r*2.2, 0.10)]:
                self.create_oval(self.cx-cr, self.cy-cr, self.cx+cr, self.cy+cr,
                                 fill=self._hex(mr, mg, mb, ca), outline='')
        self.create_oval(self.cx-core_r, self.cy-core_r, self.cx+core_r, self.cy+core_r,
                         fill=self._hex(hr, hg, hb, 0.95 if active else 0.35),
                         outline=self._hex(255, 255, 255, 0.7 if active else 0.2), width=1)

        # Etiquetas flotantes
        if active:
            for txt, ang, rr in self.data_labels:
                a = ang + self.t*0.05
                x = self.cx + rr*math.cos(a); y = self.cy + rr*math.sin(a)
                self.create_text(x, y, text=txt, fill=self._hex(mr, mg, mb, 0.6),
                                 font=('Consolas', 7, 'bold'))

        # Pulso escucha
        if self.state == 'listening':
            for i in range(3):
                pr = 50 + 90*((self.t*1.6 + i*0.4) % 1.0)
                pa = max(0.0, 1 - pr/(self.R*0.6))
                self.create_oval(self.cx-pr, self.cy-pr, self.cx+pr, self.cy+pr,
                                 outline=self._hex(255, 90, 20, pa*0.55), width=1)

        self.after(30, self._animate)

# ==================== APP PRINCIPAL ====================
MIN_SIZE, MAX_SIZE = 220, 720

class JarvisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("J.A.R.V.I.S. - cerebro")
        self.win_size = int(CONFIG.get("window_size", 380))
        self.win_size = max(MIN_SIZE, min(MAX_SIZE, self.win_size))
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = CONFIG.get("window_x") or (sw - self.win_size)//2
        y = CONFIG.get("window_y") or (sh - self.win_size)//2
        self.geometry(f"{self.win_size}x{self.win_size}+{x}+{y}")
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-transparentcolor', 'black')
        self.configure(bg='black')
        self.resizable(False, False)
        self._dx = 0; self._dy = 0
        self._dragging_window = False

        self.canvas = BrainCanvas(self, size=self.win_size)
        self.canvas.place(x=0, y=0)
        self.canvas.bind('<ButtonPress-1>', self._ds)
        self.canvas.bind('<B1-Motion>', self._dm)
        self.canvas.bind('<ButtonRelease-1>', self._save_pos)

        # Barra superior: titulo + tamano + cerrar
        tk.Label(self, text='J.A.R.V.I.S.', bg='black', fg='#00d4ff',
                 font=('Consolas', 10, 'bold')).place(relx=0.03, rely=0.02, anchor='nw')

        def btn(txt, xrel, cmd):
            b = tk.Label(self, text=txt, bg='black', fg='#00d4ff', font=('Consolas', 11, 'bold'),
                         cursor='hand2', padx=4)
            b.place(relx=xrel, rely=0.02, anchor='nw')
            b.bind('<Button-1>', lambda e: cmd())
            return b
        btn('✕', 0.88, self._quit)
        btn('–', 0.80, self._minimize)
        btn('+', 0.74, lambda: self.set_size(self.win_size + 30))
        btn('−', 0.68, lambda: self.set_size(self.win_size - 30))

        # Asa de tamano (esquina inferior derecha)
        self.handle = tk.Label(self, text='◢', bg='black', fg='#00d4ff',
                               font=('Consolas', 16, 'bold'), cursor='size_nw_se')
        self.handle.place(relx=1.0, rely=1.0, x=-4, y=-2, anchor='se')
        self.handle.bind('<ButtonPress-1>', self._resize_start)
        self.handle.bind('<B1-Motion>', self._resize_move)
        self.handle.bind('<ButtonRelease-1>', lambda e: save_config())

        # Rueda + teclas para tamano manual
        self.bind_all('<Control-MouseWheel>', lambda e: self.set_size(self.win_size + (50 if e.delta > 0 else -50)))
        for key, delta in [('plus', 40), ('equal', 40), ('minus', -40), ('0', 0)]:
            self.bind_all(f'<Alt-{key}>', lambda e, d=delta: self.set_size(380 if d == 0 else self.win_size + d))

        # Estado + burbuja (relativos: sobreviven al resize)
        self.sv = tk.StringVar(value='DI "JARVIS" PARA ACTIVAR')
        self.sl = tk.Label(self, textvariable=self.sv, bg='black', fg='#3d7090',
                           font=('Consolas', 9, 'bold'))
        self.sl.place(relx=0.5, rely=0.72, anchor='center')

        self.bv = tk.StringVar(value='')
        self.bl = tk.Label(self, textvariable=self.bv, bg='#010d1a', fg='#a8e8ff',
                           font=('Consolas', 10), wraplength=320, justify='center', padx=12, pady=8)
        self.bl.place(relx=0.5, rely=0.84, anchor='center')
        self._bt = None

        # --- Entrada de texto moderna: marco cian + placeholder + boton enviar ---
        self.entry_box = tk.Frame(self, bg='#03131f', highlightthickness=2,
                                  highlightbackground='#0a4a66',
                                  highlightcolor='#00d4ff')
        self.entry_box.place(relx=0.5, rely=0.945, relwidth=0.9, height=34, anchor='center')
        self.entry = tk.Entry(self.entry_box, bg='#03131f', fg='#d8f6ff',
                              insertbackground='#00d4ff', selectbackground='#00587a',
                              selectforeground='#ffffff', font=('Segoe UI', 10),
                              relief='flat', bd=0, highlightthickness=0)
        self.entry.pack(side='left', fill='both', expand=True, padx=(12, 4), pady=5)
        self.send_btn = tk.Label(self.entry_box, text='➤', bg='#00d4ff', fg='#00131f',
                                 font=('Segoe UI', 11, 'bold'), cursor='hand2', padx=12)
        self.send_btn.pack(side='right', fill='y')
        self.send_btn.bind('<Button-1>', self._from_entry)
        self.entry.bind('<Return>', self._from_entry)
        self.entry.bind('<FocusIn>', self._entry_focus_in)
        self.entry.bind('<FocusOut>', self._entry_focus_out)
        self._ph_on = False
        self._show_placeholder()

        self.is_active = False
        # --- cola segura UI: SOLO el hilo principal toca la ventana ---
        # (Antes los hilos de voz/IA llamaban a la ventana directo y eso
        #  podia tumbar la ventana sin aviso.)
        self._ui_q = queue.Queue()
        self._speaking = threading.Event()   # True mientras JARVIS habla
        self._speak_started = 0.0
        self._manual_close = False
        self.protocol("WM_DELETE_WINDOW", self._quit)
        self.after(60, self._pump)
        global _speak_fn
        _speak_fn = lambda t: self.say_and_show(t)
        self._min_size = self.win_size
        threading.Thread(target=self._voice_loop, daemon=True).start()
        warmup_model()
        log.info("JARVIS v2 online. Cerebro local: %s | %s | rapido=%s | grande=%s",
                 "SI" if ollama_up() else "NO (respaldo Groq/offline)",
                 CONFIG.get("openai_base_url"), CONFIG.get("fast_model"),
                 CONFIG.get("openai_model"))

    # ---- resize manual ----
    def set_size(self, new):
        new = max(MIN_SIZE, min(MAX_SIZE, int(new)))
        if new == self.win_size:
            return
        x, y = self.winfo_x(), self.winfo_y()
        self.win_size = new
        self.geometry(f"{new}x{new}+{x}+{y}")
        self.canvas.set_size(new)
        self.bl.config(wraplength=max(200, new - 40))
        CONFIG["window_size"] = new
        save_config()

    def _resize_start(self, e):
        self._rz_x, self._rz_y = e.x_root, e.y_root
        self._rz_size = self.win_size

    def _resize_move(self, e):
        dx = (e.x_root - self._rz_x) + (e.y_root - self._rz_y)
        self.set_size(self._rz_size + dx // 2)

    def _minimize(self):
        self._min_size = self.win_size
        self.set_size(MIN_SIZE)
        self.sv.set('MINI — + PARA AGRANDAR')

    # ---- mover ventana ----
    def _ds(self, e):
        self._dx, self._dy = e.x, e.y

    def _dm(self, e):
        self.geometry(f"+{self.winfo_x()+e.x-self._dx}+{self.winfo_y()+e.y-self._dy}")

    def _save_pos(self, e):
        CONFIG["window_x"] = self.winfo_x()
        CONFIG["window_y"] = self.winfo_y()
        save_config()

    # ---- UI (segura para hilos: todo pasa por _pump en el hilo principal) ----
    def set_ui(self, state, status, bubble=''):
        # Llamable desde cualquier hilo. NUNCA toca widgets directo.
        try:
            self._ui_q.put(('ui', state, status, bubble))
        except Exception:
            pass

    def say_and_show(self, text):
        try:
            self._ui_q.put(('speak', text))
        except Exception:
            pass

    def _pump(self):
        # Corre SIEMPRE en el hilo principal: aqui si se toca la ventana.
        try:
            while not self._ui_q.empty():
                item = self._ui_q.get()
                kind = item[0]
                if kind == 'ui':
                    self._apply(item[1], item[2], item[3] if len(item) > 3 else '')
                elif kind == 'speak':
                    text = item[1]
                    self._speaking.set()
                    self._speak_started = time.monotonic()
                    self._speak_limit = tts_timeout_for(text) + 15
                    self._apply('speaking', 'RESPONDIENDO...', text)
                    play_sound('ready')
                    speak_threaded(text, on_done=lambda: self._ui_q.put(('speakdone',)))
                elif kind == 'speakdone':
                    self._speaking.clear()
                    if self.is_active:
                        self.set_ui('listening', 'ESCUCHANDO...')
                    else:
                        self.set_ui('inactive', 'DI "JARVIS" PARA ACTIVAR', '')
        except Exception:
            log.exception("UI pump")
        # Solo si la voz se quedara realmente atascada (limite proporcional al texto)
        try:
            limit = getattr(self, '_speak_limit', 90)
            if self._speaking.is_set() and time.monotonic() - getattr(self, '_speak_started', 0) > limit:
                self._speaking.clear()
                self._ui_q.put(('speakdone',))
                log.warning("TTS atascado >%.0fs: escucha reanudada", limit)
        except Exception:
            pass
        try:
            self.after(60, self._pump)
        except Exception:
            pass  # ventana destruida al cerrar

    def _apply(self, state, status, bubble):
        try:
            colors = {'inactive': '#3d7090', 'active': '#00d4ff',
                      'listening': '#ff6432', 'thinking': '#ffd200', 'speaking': '#00ff88'}
            self.canvas.state = state
            self.sl.config(fg=colors.get(state, '#00d4ff'))
            self.sv.set(status)
            if bubble:
                self.bv.set(bubble)
                self.bl.place(relx=0.5, rely=0.84, anchor='center')
                if self._bt:
                    try:
                        self.after_cancel(self._bt)
                    except Exception:
                        pass
                    self._bt = None
                self._bt = self.after(12000, self.bl.place_forget)
            else:
                self.bl.place_forget()
        except Exception:
            log.exception("UI apply")

    # ---- entrada de texto con placeholder ----
    def _show_placeholder(self):
        try:
            if not self.entry.get():
                self._ph_on = True
                self.entry.insert(0, 'Pregúntame algo…')
                self.entry.config(fg='#4f7f96')
        except Exception:
            pass

    def _hide_placeholder(self):
        try:
            if self._ph_on:
                self._ph_on = False
                self.entry.delete(0, 'end')
                self.entry.config(fg='#d8f6ff')
        except Exception:
            pass

    def _entry_focus_in(self, e=None):
        try:
            self.entry_box.config(highlightbackground='#00d4ff')
        except Exception:
            pass
        self._hide_placeholder()

    def _entry_focus_out(self, e=None):
        try:
            self.entry_box.config(highlightbackground='#0a4a66')
        except Exception:
            pass
        self._show_placeholder()

    # ---- voz ----
    def _from_entry(self, e=None):
        self._hide_placeholder()
        txt = self.entry.get().strip()
        self.entry.delete(0, 'end')
        if not txt:
            return "break"
        if not self.is_active:
            self._activate()
        self._handle(txt)
        return "break"

    def _voice_retry(self, reason):
        """Si el microfono falla (ocupado, desconectado, muteado), reintenta solo."""
        n = getattr(self, '_mic_retries', 0)
        if n >= 6:
            log.error("Microfono no disponible tras %d intentos (%s)", n, reason)
            self.set_ui('inactive', 'SIN MICROFONO — ESCRIBA TEXTO')
            return
        self._mic_retries = n + 1
        log.warning("Reintentando microfono (%d/6): %s", n + 1, reason)
        self.set_ui('inactive', 'RECONECTANDO MICROFONO...')
        time.sleep(2)
        threading.Thread(target=self._voice_loop, daemon=True).start()

    def _voice_loop(self):
        try:
            import speech_recognition as sr
        except Exception as e:
            log.exception("STT no disponible")
            self.set_ui('inactive', 'SIN MICROFONO — ESCRIBA TEXTO')
            return
        r = sr.Recognizer()
        # Respuesta rapida al terminar de hablar + no cortar frases largas
        r.energy_threshold = 150
        r.dynamic_energy_threshold = True
        r.pause_threshold = 0.8
        r.non_speaking_duration = 0.4
        r.phrase_threshold = 0.25
        try:
            r.operation_timeout = 12   # no colgarse si Google STT no responde
        except Exception:
            pass
        # El micrófono oficial puede estar muteado en Windows: lo desmuteamos.
        ensure_microphone_ready()
        mic_index, names = pick_microphone(sr)
        if mic_index is None or not names:
            self._voice_retry("no se encontro microfono")
            return
        try:
            mic = sr.Microphone(device_index=mic_index)
            mic_name = names[mic_index]
        except Exception:
            log.exception("Microfono %s invalido", mic_index)
            self._voice_retry(f"microfono {mic_index} invalido")
            return
        log.info("Mic: %s (%s)", mic_index, mic_name)
        try:
            with mic as src:
                self._mic_retries = 0
                try:
                    r.adjust_for_ambient_noise(src, duration=1)
                except Exception:
                    pass
                self.set_ui('inactive', 'DI "JARVIS" PARA ACTIVAR')
                while True:
                    try:
                        # Mientras JARVIS habla NO escucha (no se escucha a si mismo)
                        if self._speaking.is_set():
                            time.sleep(0.15)
                            continue
                        # Vaciar audio viejo capturado mientras JARVIS hablaba (eco)
                        try:
                            if getattr(src, "stream", None) is not None and src.stream.is_active():
                                avail = src.stream.get_read_available()
                                if avail:
                                    src.stream.read(avail, exception_on_overflow=False)
                        except Exception:
                            pass
                        text = self._listen_complete(r, src)
                        if not text:
                            continue
                        if self._speaking.is_set():
                            continue  # eco de la propia voz: se descarta
                        log.info("[VOZ] %s", text)
                        self._save_voice_history(text)
                        t = norm(text)
                        if not self.is_active:
                            if has_wake_word(t):
                                resto = strip_wake(t)
                                self._activate()
                                if len(resto) > 3 and not is_stop_command(text):
                                    self._handle(resto)
                        else:
                            # Solo se apaga si la frase ES el comando de apagado.
                            # "busca en google como apagar..." ya NO lo apaga.
                            if is_stop_command(text):
                                self._deactivate()
                            else:
                                self._handle(text)
                    except Exception:
                        log.exception("voice loop iteracion")
                        time.sleep(0.2)
                        continue
        except Exception:
            log.exception("voice loop fatal")
            self._voice_retry("fallo el flujo de audio")

    def _listen(self, r, mic_src, timeout=8, phrase=20):
        """Escucha completa y segura. Registra por que falla el reconocimiento."""
        try:
            import speech_recognition as sr
        except Exception:
            return None
        try:
            audio = r.listen(mic_src, timeout=timeout, phrase_time_limit=phrase)
        except sr.WaitTimeoutError:
            return None                      # silencio normal, no es un error
        except Exception:
            log.exception("Fallo al capturar audio del microfono")
            return None
        try:
            return r.recognize_google(audio, language='es-ES').lower().strip()
        except sr.UnknownValueError:
            log.debug("STT: no se entendio el audio (ruido o voz muy baja)")
            return None
        except sr.RequestError as e:
            log.warning("STT sin conexion con Google: %s", e)
            return None
        except Exception:
            log.exception("STT fallo inesperado")
            return None

    _INCOMPLETE_TAIL = {
        "la", "el", "de", "en", "que", "a", "al", "del", "por", "para",
        "con", "un", "una", "como", "cuando", "donde", "y", "o", "se",
        "es", "las", "los", "mi", "mis", "su", "sus", "hay", "quiero",
        "busca", "buscar",
    }

    def _looks_incomplete(self, text):
        """True si la frase parece cortada ('...que es la' / '...busca')."""
        words = norm(text).split()
        if not words:
            return False
        return words[-1] in self._INCOMPLETE_TAIL

    def _listen_complete(self, r, src):
        """Escucha y, si se corta a mitad, espera la continuacion (x2)."""
        text = self._listen(r, src)
        if not text:
            return None
        tries = 0
        while self._looks_incomplete(text) and tries < 2:
            self.set_ui('listening', 'SIGO ESCUCHANDO...', text)
            cont = self._listen(r, src, timeout=6, phrase=15)
            if not cont:
                break
            text = text.rstrip() + " " + cont
            tries += 1
        return text

    def _save_voice_history(self, text):
        try:
            p = MEMORY_DIR / "historial_voz.txt"
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now().isoformat(timespec='seconds')} {text}\n")
        except Exception:
            pass

    def _activate(self):
        self.is_active = True
        play_sound('activate')
        self.set_ui('active', 'INICIALIZANDO...')
        time.sleep(0.4)
        msg = "A sus órdenes señor. ¿En qué puedo servirle?"
        self.say_and_show(msg)

    def _deactivate(self):
        self.is_active = False
        global conversation_history; conversation_history = []
        play_sound('deactivate')
        msg = "Hasta pronto señor. Entrando en modo de espera."
        self.say_and_show(msg)
        # Al terminar de hablar, _pump pone 'inactive' solo (is_active=False)

    def _handle(self, text):
        self.set_ui('thinking', 'PROCESANDO...')
        play_sound('think')
        def _w():
            try:
                # 1) Accion local (rapida, gratis, sin internet)
                local = None
                try:
                    local = local_route(text)
                except Exception:
                    log.exception("router local")
                    local = None
                if local:
                    log.info("[JARVIS] %s", local)
                    save_city_info(text, local)
                    self.say_and_show(local)
                    return
                # 2) Cerebro (Ollama local / Groq opcional / offline)
                try:
                    reply = ask_brain(text)
                except Exception:
                    log.exception("cerebro")
                    reply = "Disculpe señor, tuve un problema transitorio."
                log.info("[JARVIS] %s", reply)
                save_city_info(text, reply)
                self.say_and_show(reply)
            except Exception:
                log.exception("handle")
        threading.Thread(target=_w, daemon=True).start()

    def _quit(self):
        # UNICA forma de cerrar: boton X. Nada mas cierra a JARVIS.
        self._manual_close = True
        try:
            self._save_pos(None)
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

def run_app():
    """Arranca JARVIS. Retorna True si se cerro a mano, False si se cayo."""
    log.info("Iniciando JARVIS v2 (cerebro 3D)...")
    try:
        app = JarvisApp()
        app.mainloop()
        return True
    except SystemExit:
        return True
    except Exception:
        log.exception("JARVIS se cayo")
        return False

if __name__ == '__main__':
    # Blindaje anti-cierre-solo: si algo inesperado tumba la ventana,
    # se reabre solo hasta 3 veces y deja todo en jarvis_log.txt
    _intentos = 0
    while True:
        if run_app():
            break  # cierre manual con la X: no reabrir
        _intentos += 1
        if _intentos >= 3:
            print("JARVIS no pudo mantenerse. Revise jarvis_log.txt para ver el error.")
            log.error("JARVIS no pudo mantenerse tras 3 intentos")
            break
        print(f"JARVIS se tropezo... se reabre solo en 2s (intento {_intentos}/3). Revise jarvis_log.txt")
        time.sleep(2)
