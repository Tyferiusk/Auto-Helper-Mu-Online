# 🎮 Auto Helper para MU Online

**Herramienta automatizada que mantiene activo el helper (auto-ataque) en MU Online, detectando visualmente cuando se desactiva y reactivándolo automáticamente.**

![Versión](https://img.shields.io/badge/version-1.0-blue)
![Python](https://img.shields.io/badge/Python-3.7+-green)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-red)
![Qt](https://img.shields.io/badge/Qt-PySide6-41CD52)
![Licencia](https://img.shields.io/badge/license-MIT-lightgrey)

---

## ✨ Características

- 🎯 **Detección visual** con OpenCV (reconoce estado OFFLINE del helper)
- 🖥️ **Soporte multi-ventana** - Funciona con múltiples cuentas abiertas simultáneamente
- 🎨 **Interfaz gráfica profesional** con PySide6 (Qt)
- 📊 **Consola en tiempo real** con logs coloreados
- 🔄 **Reactivación automática** enviando tecla INICIO (HOME)
- ⚡ **Bajo consumo de recursos** - Intervalo configurable
- 🪟 **Foco inteligente** - Restaura la ventana activa después de actuar
- 📦 **Ejecutable portable** - Puede compilarse a .exe con PyInstaller

---

## 🛡️ ¿Es legal?

**Este script es una herramienta de asistencia, NO un cheat o hack.**

- ✅ **No modifica memoria del juego**
- ✅ **No inyecta código**
- ✅ **Solo simula pulsaciones de teclado** (como si lo hiciera un humano)
- ✅ **Es completamente visible** (código abierto)

> ⚠️ **Nota**: Verifica las reglas del servidor específico de MU Online. Algunos servidores pueden prohibir la automatización. Úsalo bajo tu responsabilidad.

---

## 📋 Requisitos
- Resolucion del computador 1920 x 1080 al 100%
- Cliente resolucion 800 x 600 (esto se puede cambiar en las opciones del juego)
- Windows 7, 8, 10 o 11
- Python 3.7 o superior
- MU Online ejecutándose con la ventana que contenga `"www.mu-exilio.com"` en el título

### Instalación de dependencias

```bash
pip install opencv-python numpy pywin32 pyside6 mss
