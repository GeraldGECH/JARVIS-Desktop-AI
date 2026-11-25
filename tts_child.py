# -*- coding: utf-8 -*-
"""Hijo TTS: habla en un proceso SEPARADO.

Por que: el motor de voz de Windows (SAPI via pyttsx3) puede colgarse o
morir en el proceso principal despues de abrir el navegador. Asi, si este
proceso falla, JARVIS sigue vivo y escuchando.

Uso:
    python tts_child.py "texto" [rate] [volume]
"""
import sys


def main():
    text = sys.argv[1] if len(sys.argv) > 1 else ""
    if not text.strip():
        return 0
    try:
        rate = int(float(sys.argv[2])) if len(sys.argv) > 2 else 172
    except Exception:
        rate = 172
    try:
        volume = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    except Exception:
        volume = 1.0
    import pyttsx3
    e = pyttsx3.init()
    voices = e.getProperty("voices")
    # Helena es la voz espanola (es-ES) instalada en Windows.
    spanish = next((v for v in voices if "helena" in v.name.lower()), None)
    if not spanish:
        spanish = next((v for v in voices if any(x in v.name.lower()
                                                 for x in ["spanish", "helena", "sabina", "es_"])), None)
    if spanish:
        e.setProperty("voice", spanish.id)
    e.setProperty("rate", rate)
    e.setProperty("volume", volume)
    e.say(text)
    e.runAndWait()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        print(f"[TTS-CHILD] {ex}", file=sys.stderr)
        sys.exit(1)
