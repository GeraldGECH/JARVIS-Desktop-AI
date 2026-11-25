# Contribuir a JARVIS

¡Gracias por querer mejorar JARVIS! Este es un proyecto abierto para que cualquiera lo use, aprenda, lo modifique y lo lleve más lejos.

## Cómo contribuir

1. **Haz un fork** del repositorio.
2. **Crea una rama** para tu mejora:
   ```bash
   git checkout -b mi-mejora
   ```
3. **Haz tus cambios** y pruébalos localmente.
4. **Haz commit** con un mensaje claro:
   ```bash
   git commit -m "Agrega: descripción corta de la mejora"
   ```
5. **Abre un Pull Request** explicando qué hiciste y por qué.

## Ideas bienvenidas

- Voz 100% offline (Whisper / faster-whisper).
- TTS más natural (Piper, Coqui, etc.).
- Nuevas automatizaciones y acciones.
- Mejor detección de intención.
- Soporte para más apps y servicios.
- Interfaz, animaciones o temas nuevos.
- Documentación, traducciones y tutoriales.

## Reglas simples

- Sé respetuoso con los demás colaboradores.
- No incluyas claves, tokens, contraseñas ni datos personales.
- Si agregas dependencias, actualiza `requirements.txt`.
- Prueba que `python -m py_compile stark.py tts_child.py` pase antes de enviar.
- Explica cómo probar tu cambio en el PR.

## Reportar bugs

Abre un Issue con:

- Qué esperabas que pasara.
- Qué pasó en realidad.
- Pasos para reproducirlo.
- Tu versión de Windows, Python y modelo de Ollama.
- El fragmento relevante de `jarvis_log.txt` (sin datos personales).

¡Expande tu mente y usa tu imaginación! 🚀
