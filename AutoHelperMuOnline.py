import sys
import os
import time
import traceback
from datetime import datetime

# ========== SISTEMA DE LOGS ==========
LOG_FILE = "AutoHelper_log.txt"

def write_log(message, level="INFO"):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    except:
        pass

def log_error(error):
    write_log(f"ERROR: {error}", "ERROR")
    write_log(traceback.format_exc(), "TRACE")

write_log("=" * 60)
write_log("INICIO DEL PROGRAMA")
write_log("=" * 60)
write_log(f"Python version: {sys.version}")
write_log(f"OS: {sys.platform}")

# ========== VERIFICACIÓN DE DEPENDENCIAS ==========
try:
    import cv2
    write_log(f"OpenCV version: {cv2.__version__}")
except Exception as e:
    write_log(f"Error cargando OpenCV: {e}", "ERROR")

try:
    import win32gui, win32api, win32con
    write_log("win32gui, win32api, win32con cargados correctamente")
except Exception as e:
    write_log(f"Error cargando módulos win32: {e}", "ERROR")

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QTextEdit, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QGroupBox, QMessageBox
    from PySide6.QtCore import QThread, Signal, Qt
    from PySide6.QtGui import QIcon, QTextCursor, QColor, QFont
    write_log("PySide6 cargado correctamente")
except Exception as e:
    write_log(f"Error cargando PySide6: {e}", "ERROR")

import mss
import numpy as np

# ========== CONFIGURACIÓN ==========
WINDOW_TITLE = "www.mu-exilio.com"
REGION_RELATIVE = (4, 454, 139, 40)      # zona ONLINE/OFFLINE
MATCH_THRESHOLD = 0.8
CHECK_INTERVAL = 0.2                     # más rápido (0.2 segundos)
SCANCODE_HOME = 0x47

# Configuración para maná (sin OCR, por comparación de imágenes)
MANA_REGION = (628, 600, 30, 17)         # x, y, ancho, alto (relativo a la ventana)
MANA_STABLE_SECONDS = 5.0                # tiempo sin cambios para considerar inactivo
# ===================================

write_log(f"Configuración cargada: WINDOW_TITLE={WINDOW_TITLE}, REGION={REGION_RELATIVE}, MANA_REGION={MANA_REGION}")

# Cargar plantillas
template_online = cv2.imread("online.png", cv2.IMREAD_GRAYSCALE)
template_offline = cv2.imread("offline.png", cv2.IMREAD_GRAYSCALE)

if template_online is None:
    write_log("ERROR: No se pudo cargar online.png", "ERROR")
else:
    write_log(f"online.png cargado: {template_online.shape}")

if template_offline is None:
    write_log("ERROR: No se pudo cargar offline.png", "ERROR")
else:
    write_log(f"offline.png cargado: {template_offline.shape}")

# ========== FUNCIONES DE INFORMACIÓN DE PANTALLA ==========
def get_screen_resolution():
    width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    return width, height

def get_screen_dpi():
    try:
        import ctypes
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc = user32.GetDC(0)
        if hdc:
            dpi_x = gdi32.GetDeviceCaps(hdc, 88)
            dpi_y = gdi32.GetDeviceCaps(hdc, 90)
            user32.ReleaseDC(0, hdc)
            return dpi_x, dpi_y
        else:
            return 96, 96
    except Exception as e:
        write_log(f"Error obteniendo DPI: {e}", "ERROR")
        return 96, 96

def check_dpi_scaling():
    dpi_x, dpi_y = get_screen_dpi()
    write_log(f"DPI detectado: X={dpi_x}, Y={dpi_y}")
    if dpi_x == 96 and dpi_y == 96:
        write_log("DPI 100% (escala correcta)")
        return True, "DPI 100% correcto"
    else:
        scale_percent = (dpi_x / 96) * 100
        msg = f"⚠️ ESCALA DPI AL {scale_percent:.0f}% (DPI={dpi_x}). El script requiere 100% (96 DPI) para capturas precisas."
        write_log(msg, "WARNING")
        return False, msg

# Registrar info de pantalla
try:
    res_x, res_y = get_screen_resolution()
    write_log(f"Resolución de pantalla: {res_x}x{res_y}")
    dpi_ok, dpi_msg = check_dpi_scaling()
except Exception as e:
    write_log(f"Error obteniendo información de pantalla: {e}", "ERROR")

# ========== CLASE DEL THREAD PRINCIPAL (MULTIVENTANA MEJORADA) ==========
class EjecutarScriptThread(QThread):
    script_detenido = Signal()
    print_signal = Signal(str, QColor)

    def __init__(self):
        super().__init__()
        # Diccionario para mantener estado del maná por ventana
        self.mana_state = {}  # clave: hwnd, valor: {'last_img': None, 'stable_counter': 0, 'last_trigger_time': 0}

    def run(self):
        write_log("Thread de ejecución iniciado (modo multiventana sin bloqueos)")
        contador_ciclos = 0

        while not self.isInterruptionRequested():
            try:
                contador_ciclos += 1
                windows = self.get_mu_windows()

                if not windows:
                    if contador_ciclos % 20 == 0:
                        write_log(f"No se encontraron ventanas con título '{WINDOW_TITLE}'")
                    self.print_signal.emit("Esperando ventanas del juego...", QColor(255, 165, 0))
                    time.sleep(2)
                    continue

                # Procesar cada ventana de forma independiente y rápida
                for hwnd in windows:
                    if self.isInterruptionRequested():
                        break

                    # --- 1. DETECCIÓN POR PLANTILLA OFFLINE (rápida) ---
                    is_offline = self.is_helper_offline(hwnd)

                    if is_offline:
                        titulo = win32gui.GetWindowText(hwnd)
                        write_log(f"⚠️ Helper OFFLINE detectado por plantilla en ventana: {titulo}")
                        self.print_signal.emit(f"⚔️ OFFLINE (plantilla) en {titulo}", QColor(255, 0, 0))
                        self.send_home_and_reset(hwnd)
                        # Pequeña pausa para no saturar
                        time.sleep(0.5)
                        continue  # Ya se reactivó, pasar a siguiente ventana

                    # --- 2. DETECCIÓN POR MANÁ (sin bloqueos, usando estabilidad en el tiempo) ---
                    self.check_mana_stability(hwnd)

                # Pequeña pausa entre ciclos
                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                error_msg = f"Error en ciclo principal: {e}"
                write_log(error_msg, "ERROR")
                write_log(traceback.format_exc(), "TRACE")
                self.print_signal.emit(f"Error: {e}", QColor(255, 0, 0))
                time.sleep(0.5)

        write_log("Thread de ejecución finalizado")
        self.script_detenido.emit()

    # ---------- MÉTODOS AUXILIARES ----------
    def get_mu_windows(self):
        handles = []
        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                titulo = win32gui.GetWindowText(hwnd)
                if WINDOW_TITLE in titulo:
                    handles.append(hwnd)
        win32gui.EnumWindows(enum_callback, None)
        return handles

    def capture_region(self, hwnd, region):
        """Captura una región (x, y, w, h) relativa a la ventana y devuelve imagen BGR (numpy)"""
        try:
            rect = win32gui.GetWindowRect(hwnd)
            abs_left = rect[0] + region[0]
            abs_top = rect[1] + region[1]
            with mss.mss() as sct:
                monitor = {
                    "left": abs_left,
                    "top": abs_top,
                    "width": region[2],
                    "height": region[3]
                }
                img = sct.grab(monitor)
                return np.array(img)
        except Exception as e:
            write_log(f"Error capturando región {region}: {e}", "ERROR")
            return None

    def is_helper_offline(self, hwnd):
        try:
            if template_offline is None:
                return False
            region_img = self.capture_region(hwnd, REGION_RELATIVE)
            if region_img is None:
                return False
            gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(gray, template_offline, cv2.TM_CCOEFF_NORMED)
            max_val = np.max(result)
            if max_val > MATCH_THRESHOLD:
                write_log(f"Match OFFLINE detectado: valor={max_val:.3f}", "DEBUG")
                return True
            return False
        except Exception as e:
            write_log(f"Error en is_helper_offline: {e}", "ERROR")
            return False

    def images_are_equal(self, img1, img2, threshold=0.99):
        """Compara dos imágenes usando correlación normalizada. Devuelve True si son muy similares."""
        if img1 is None or img2 is None:
            return False
        try:
            # Convertir a escala de grises
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            # Asegurar mismo tamaño
            if gray1.shape != gray2.shape:
                gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))
            result = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)
            similarity = result[0][0]
            return similarity >= threshold
        except Exception as e:
            write_log(f"Error comparando imágenes: {e}", "ERROR")
            return False

    def check_mana_stability(self, hwnd):
        """Actualiza el estado del maná para una ventana. Si se mantiene estable por MANA_STABLE_SECONDS, envía HOME."""
        now = time.time()
        # Inicializar estado si no existe
        if hwnd not in self.mana_state:
            self.mana_state[hwnd] = {
                'last_img': None,
                'stable_counter': 0,
                'last_trigger_time': 0
            }
        state = self.mana_state[hwnd]

        # No hacer nada si acabamos de enviar HOME (evitar spam)
        if now - state['last_trigger_time'] < 10:
            return

        # Capturar imagen actual del maná
        current_img = self.capture_region(hwnd, MANA_REGION)
        if current_img is None:
            return

        # Si no hay imagen anterior, guardar y salir
        if state['last_img'] is None:
            state['last_img'] = current_img
            state['stable_counter'] = 0
            return

        # Comparar con la imagen anterior
        if self.images_are_equal(state['last_img'], current_img):
            # Se mantiene igual: incrementar contador
            state['stable_counter'] += 1
            # Calcular tiempo que lleva estable (cada ciclo = CHECK_INTERVAL segundos)
            stable_time = state['stable_counter'] * CHECK_INTERVAL
            if stable_time >= MANA_STABLE_SECONDS:
                write_log(f"⚠️ Maná estable durante {stable_time:.1f} segundos en ventana {hwnd} -> helper inactivo")
                self.print_signal.emit(f"💧 Maná sin cambios durante {MANA_STABLE_SECONDS}s en ventana", QColor(255, 165, 0))
                self.send_home_and_reset(hwnd)
                state['last_trigger_time'] = now
                state['stable_counter'] = 0  # resetear contador tras enviar
                # Actualizar imagen para evitar reactivar inmediatamente
                state['last_img'] = self.capture_region(hwnd, MANA_REGION)
        else:
            # El maná cambió -> helper activo, reiniciar contador
            if state['stable_counter'] > 0:
                write_log(f"Maná cambió en ventana {hwnd}, helper activo", "DEBUG")
            state['stable_counter'] = 0
            state['last_img'] = current_img

    def send_home_and_reset(self, hwnd):
        """Envía tecla HOME a la ventana y limpia su estado de maná para evitar falsos reintentos."""
        titulo = win32gui.GetWindowText(hwnd)
        write_log(f"Enviando HOME a ventana: {titulo} (HWND={hwnd})")
        self.print_signal.emit(f"   → Enviando HOME a {titulo}", QColor(255, 165, 0))
        success = self.send_home_key_scancode_with_focus(hwnd)
        if success:
            write_log(f"✅ Helper reactivado en {hwnd}")
            # Limpiar estado de maná para que empiece de nuevo
            if hwnd in self.mana_state:
                self.mana_state[hwnd]['last_img'] = None
                self.mana_state[hwnd]['stable_counter'] = 0
        else:
            write_log(f"❌ Falló reactivación en {hwnd}", "ERROR")

    def send_home_key_scancode_with_focus(self, hwnd):
        try:
            foreground = win32gui.GetForegroundWindow()
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.05)
            win32api.keybd_event(win32con.VK_HOME, SCANCODE_HOME, 0, 0)
            time.sleep(0.07)
            win32api.keybd_event(win32con.VK_HOME, SCANCODE_HOME, win32con.KEYEVENTF_KEYUP, 0)
            if foreground and foreground != hwnd:
                win32gui.SetForegroundWindow(foreground)
            return True
        except Exception as e:
            write_log(f"Error enviando tecla: {e}", "ERROR")
            return False

    # Método de depuración: capturar y guardar región de maná
    def capture_and_save_mana_region(self, hwnd, output_path="mana_region.png"):
        img = self.capture_region(hwnd, MANA_REGION)
        if img is not None:
            cv2.imwrite(output_path, img)
            write_log(f"Región de maná guardada en: {output_path}")
            return True, output_path
        return False, "No se pudo capturar"

# ========== INTERFAZ GRÁFICA (sin cambios importantes) ==========
class Console(QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 9))

    def print_message(self, message, color):
        self.setTextColor(color)
        self.append(message)
        self.setTextColor(QColor(0, 0, 0))
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

class MiVentana(QMainWindow):
    def __init__(self):
        super().__init__()
        write_log("Inicializando ventana principal")
        self.setWindowIcon(QIcon("helper_icon.png") if os.path.exists("helper_icon.png") else QIcon())
        self.setWindowTitle("Auto Helper - Multiventana (Offline + Maná estable)")
        self.setFixedSize(550, 450)

        self.check_templates()
        self.setup_ui()

        self.script_thread = EjecutarScriptThread()
        self.script_thread.print_signal.connect(self.textEdit_consola.print_message)
        self.script_thread.script_detenido.connect(self.habilitar_botones)

        self.mostrar_info_pantalla()
        write_log("Ventana principal inicializada")

    def check_templates(self):
        if not os.path.exists("online.png"):
            self.show_template_warning("online.png")
        if not os.path.exists("offline.png"):
            self.show_template_warning("offline.png")

    def show_template_warning(self, filename):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Archivo faltante")
        msg.setText(f"No se encontró el archivo {filename}")
        msg.setInformativeText(f"Asegúrate de que {filename} esté en la misma carpeta")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def mostrar_info_pantalla(self):
        try:
            res_x, res_y = get_screen_resolution()
            self.textEdit_consola.print_message(f"📺 Resolución: {res_x} x {res_y}", QColor(0, 0, 255))
            dpi_x, dpi_y = get_screen_dpi()
            self.textEdit_consola.print_message(f"🖥️ DPI: X={dpi_x}, Y={dpi_y}", QColor(0, 0, 255))
            if dpi_x != 96 or dpi_y != 96:
                scale = (dpi_x / 96) * 100
                self.textEdit_consola.print_message(
                    f"⚠️ Escala al {scale:.0f}% (DPI {dpi_x}). Requiere 100% para capturas precisas.",
                    QColor(255, 0, 0)
                )
            else:
                self.textEdit_consola.print_message("✅ Escala DPI 100% correcta", QColor(0, 128, 0))
        except Exception as e:
            self.textEdit_consola.print_message(f"Error info pantalla: {e}", QColor(255, 0, 0))

    def capturar_y_mostrar_zona(self):
        windows = self.script_thread.get_mu_windows()
        if not windows:
            QMessageBox.warning(self, "Sin ventanas", "No se encontró ninguna ventana del juego.")
            return
        hwnd = windows[0]
        output_file = "region_capturada.png"
        try:
            img = self.script_thread.capture_region(hwnd, REGION_RELATIVE)
            if img is not None:
                cv2.imwrite(output_file, img)
                self.textEdit_consola.print_message(f"✅ Región ONLINE/OFFLINE guardada en {output_file}", QColor(0, 128, 0))
                QMessageBox.information(self, "Captura", f"Guardada en {output_file}")
            else:
                raise Exception("No se pudo capturar")
        except Exception as e:
            self.textEdit_consola.print_message(f"❌ Error: {e}", QColor(255, 0, 0))

    def capturar_y_mostrar_mana(self):
        windows = self.script_thread.get_mu_windows()
        if not windows:
            QMessageBox.warning(self, "Sin ventanas", "No se encontró ninguna ventana del juego.")
            return
        hwnd = windows[0]
        output_file = "mana_region.png"
        success, result = self.script_thread.capture_and_save_mana_region(hwnd, output_file)
        if success:
            self.textEdit_consola.print_message(f"✅ Región de maná guardada en {output_file}", QColor(0, 128, 0))
            QMessageBox.information(self, "Captura", f"Guardada en {output_file}")
        else:
            self.textEdit_consola.print_message(f"❌ Error: {result}", QColor(255, 0, 0))

    def setup_ui(self):
        centralwidget = QWidget(self)
        self.setCentralWidget(centralwidget)
        layout_principal = QVBoxLayout(centralwidget)

        grupo_info = QGroupBox("Información")
        layout_info = QHBoxLayout(grupo_info)
        self.label_estado = QLabel("🔴 Detenido")
        self.label_estado.setStyleSheet("font-weight: bold; color: red;")
        layout_info.addWidget(self.label_estado)
        layout_info.addStretch()
        self.label_ventanas = QLabel("Ventanas: --")
        layout_info.addWidget(self.label_ventanas)
        layout_principal.addWidget(grupo_info)

        grupo_consola = QGroupBox("Consola")
        layout_consola = QVBoxLayout(grupo_consola)
        self.textEdit_consola = Console()
        layout_consola.addWidget(self.textEdit_consola)
        layout_principal.addWidget(grupo_consola)

        layout_botones = QHBoxLayout()
        self.pushButton_ejecutar = QPushButton("▶ Ejecutar Helper")
        self.pushButton_parar = QPushButton("⏹ Detener")
        self.pushButton_ver_zona = QPushButton("🔍 Ver zona OFF/ON")
        self.pushButton_ver_mana = QPushButton("💧 Ver zona maná")
        self.pushButton_parar.setEnabled(False)

        layout_botones.addWidget(self.pushButton_ejecutar)
        layout_botones.addWidget(self.pushButton_parar)
        layout_botones.addWidget(self.pushButton_ver_zona)
        layout_botones.addWidget(self.pushButton_ver_mana)

        layout_principal.addLayout(layout_botones)

        self.pushButton_ejecutar.clicked.connect(self.iniciar_script)
        self.pushButton_parar.clicked.connect(self.detener_script)
        self.pushButton_ver_zona.clicked.connect(self.capturar_y_mostrar_zona)
        self.pushButton_ver_mana.clicked.connect(self.capturar_y_mostrar_mana)

    def actualizar_contador_ventanas(self):
        try:
            handles = self.script_thread.get_mu_windows()
            self.label_ventanas.setText(f"Ventanas: {len(handles)}")
        except Exception as e:
            write_log(f"Error actualizando contador: {e}", "ERROR")

    def iniciar_script(self):
        write_log("Usuario inició el script")
        self.pushButton_ejecutar.setEnabled(False)
        self.pushButton_parar.setEnabled(True)
        self.label_estado.setText("🟢 Ejecutando...")
        self.label_estado.setStyleSheet("font-weight: bold; color: green;")
        self.script_thread.start()
        self.timer_ventanas = self.startTimer(300)

    def timerEvent(self, event):
        self.actualizar_contador_ventanas()

    def detener_script(self):
        write_log("Usuario detuvo el script")
        self.script_thread.requestInterruption()
        self.label_estado.setText("🟡 Deteniendo...")

    def habilitar_botones(self):
        write_log("Script detenido, habilitando botones")
        self.pushButton_ejecutar.setEnabled(True)
        self.pushButton_parar.setEnabled(False)
        self.label_estado.setText("🔴 Detenido")
        if hasattr(self, 'timer_ventanas'):
            self.killTimer(self.timer_ventanas)

if __name__ == "__main__":
    try:
        write_log("Creando aplicación Qt...")
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        ventana = MiVentana()
        ventana.show()
        write_log("Ventana mostrada, iniciando loop...")
        sys.exit(app.exec())
    except Exception as e:
        write_log(f"ERROR FATAL: {e}", "ERROR")
        write_log(traceback.format_exc(), "TRACE")
        raise
