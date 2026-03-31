import sys
import time
import cv2
import numpy as np
import win32gui
import win32api
import win32con
import mss
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QTextEdit, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QGroupBox, QMessageBox
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QIcon, QTextCursor, QColor, QFont

# ========== CONFIGURACIÓN ==========
WINDOW_TITLE = "www.mu-exilio.com"
REGION_RELATIVE = (4, 454, 139, 40)
MATCH_THRESHOLD = 0.8
CHECK_INTERVAL = 1.5
SCANCODE_HOME = 0x47
# ===================================

# Cargar plantillas (deben estar en la misma carpeta)
template_online = cv2.imread("online.png", cv2.IMREAD_GRAYSCALE)
template_offline = cv2.imread("offline.png", cv2.IMREAD_GRAYSCALE)

class EjecutarScriptThread(QThread):
    script_detenido = Signal()
    print_signal = Signal(str, QColor)

    def run(self):
        while not self.isInterruptionRequested():
            try:
                windows = self.get_mu_windows()
                
                if not windows:
                    self.print_signal.emit("Esperando ventanas del juego...", QColor(255, 165, 0))
                    time.sleep(5)
                    continue
                
                for hwnd in windows:
                    if self.isInterruptionRequested():
                        break
                    
                    if self.is_helper_offline(hwnd):
                        titulo = win32gui.GetWindowText(hwnd)
                        self.print_signal.emit(f"⚔️ Helper OFFLINE detectado en {titulo}", QColor(255, 0, 0))
                        self.print_signal.emit("   → Enviando tecla INICIO (scancode + foco)", QColor(255, 165, 0))
                        self.send_home_key_scancode_with_focus(hwnd)
                        time.sleep(2)  # Evitar múltiples envíos
                
                time.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                self.print_signal.emit(f"Error: {e}", QColor(255, 0, 0))
                time.sleep(1.7)
        
        self.script_detenido.emit()

    def get_mu_windows(self):
        handles = []
        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and WINDOW_TITLE in win32gui.GetWindowText(hwnd):
                handles.append(hwnd)
        win32gui.EnumWindows(enum_callback, None)
        return handles

    def capture_region(self, hwnd):
        rect = win32gui.GetWindowRect(hwnd)
        abs_left = rect[0] + REGION_RELATIVE[0]
        abs_top = rect[1] + REGION_RELATIVE[1]
        
        with mss.mss() as sct:
            monitor = {
                "left": abs_left,
                "top": abs_top,
                "width": REGION_RELATIVE[2],
                "height": REGION_RELATIVE[3]
            }
            img = sct.grab(monitor)
            return np.array(img)

    def is_helper_offline(self, hwnd):
        try:
            region = self.capture_region(hwnd)
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(gray, template_offline, cv2.TM_CCOEFF_NORMED)
            return np.max(result) > MATCH_THRESHOLD
        except:
            return False

    def send_home_key_scancode_with_focus(self, hwnd):
        try:
            # Guardar la ventana que estaba activa
            foreground = win32gui.GetForegroundWindow()
            
            # Traer la ventana del juego al frente
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.1)
            
            # Enviar tecla HOME usando scancode
            win32api.keybd_event(win32con.VK_HOME, SCANCODE_HOME, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(win32con.VK_HOME, SCANCODE_HOME, win32con.KEYEVENTF_KEYUP, 0)
            
            # Volver a la ventana anterior (comenta si no quieres)
            if foreground and foreground != hwnd:
                win32gui.SetForegroundWindow(foreground)
            
            self.print_signal.emit("   ✅ Helper reactivado", QColor(0, 255, 0))
            return True
        except Exception as e:
            self.print_signal.emit(f"   ❌ Error al enviar tecla: {e}", QColor(255, 0, 0))
            return False


class Console(QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 9))

    def print_message(self, message, color):
        self.setTextColor(color)
        self.append(message)
        self.setTextColor(QColor(0, 0, 0))  # Restaurar color a negro
        # Auto-scroll al final
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)


class MiVentana(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon("helper_icon.png") if self.icon_exists("helper_icon.png") else QIcon())
        self.setWindowTitle("Auto Helper by Tyferiusk")
        self.setFixedSize(500, 400)
        
        # Verificar plantillas al iniciar
        self.check_templates()
        
        self.setup_ui()
        
        self.script_thread = EjecutarScriptThread()
        self.script_thread.print_signal.connect(self.textEdit_consola.print_message)
        self.script_thread.script_detenido.connect(self.habilitar_botones)

    def icon_exists(self, path):
        try:
            import os
            return os.path.exists(path)
        except:
            return False

    def check_templates(self):
        import os
        if not os.path.exists("online.png"):
            self.show_template_warning("online.png")
        if not os.path.exists("offline.png"):
            self.show_template_warning("offline.png")

    def show_template_warning(self, filename):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Archivo faltante")
        msg.setText(f"No se encontró el archivo {filename}")
        msg.setInformativeText(f"Asegúrate de que {filename} esté en la misma carpeta que el ejecutable")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def setup_ui(self):
        # Widget central
        centralwidget = QWidget(self)
        self.setCentralWidget(centralwidget)
        
        # Layout principal vertical
        layout_principal = QVBoxLayout(centralwidget)
        layout_principal.setSpacing(10)
        layout_principal.setContentsMargins(15, 15, 15, 15)
        
        # Grupo de información
        grupo_info = QGroupBox("Información")
        layout_info = QHBoxLayout(grupo_info)
        
        self.label_estado = QLabel("🔴 Detenido")
        self.label_estado.setStyleSheet("font-weight: bold; color: red;")
        layout_info.addWidget(self.label_estado)
        
        layout_info.addStretch()
        
        self.label_ventanas = QLabel("Ventanas: --")
        layout_info.addWidget(self.label_ventanas)
        
        layout_principal.addWidget(grupo_info)
        
        # Grupo de configuración
        grupo_config = QGroupBox("Configuración")
        layout_config = QHBoxLayout(grupo_config)
        
        layout_config.addWidget(QLabel("Región de detección:"))
        layout_config.addWidget(QLabel(f"({REGION_RELATIVE[0]}, {REGION_RELATIVE[1]})"))
        layout_config.addStretch()
        layout_config.addWidget(QLabel("Intervalo:"))
        layout_config.addWidget(QLabel(f"{CHECK_INTERVAL}s"))
        
        layout_principal.addWidget(grupo_config)
        
        # Consola
        grupo_consola = QGroupBox("Consola")
        layout_consola = QVBoxLayout(grupo_consola)
        
        self.textEdit_consola = Console()
        self.textEdit_consola.setMinimumHeight(180)
        layout_consola.addWidget(self.textEdit_consola)
        
        layout_principal.addWidget(grupo_consola)
        
        # Botones
        layout_botones = QHBoxLayout()
        layout_botones.addStretch()
        
        self.pushButton_ejecutar = QPushButton("▶ Ejecutar Helper")
        self.pushButton_ejecutar.setMinimumWidth(120)
        self.pushButton_ejecutar.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        self.pushButton_parar = QPushButton("⏹ Detener")
        self.pushButton_parar.setMinimumWidth(120)
        self.pushButton_parar.setEnabled(False)
        self.pushButton_parar.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        
        layout_botones.addWidget(self.pushButton_ejecutar)
        layout_botones.addWidget(self.pushButton_parar)
        layout_botones.addStretch()
        
        layout_principal.addLayout(layout_botones)
        
        # Conectar botones
        self.pushButton_ejecutar.clicked.connect(self.iniciar_script)
        self.pushButton_parar.clicked.connect(self.detener_script)

    def actualizar_contador_ventanas(self):
        try:
            handles = []
            def enum_callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd) and WINDOW_TITLE in win32gui.GetWindowText(hwnd):
                    handles.append(hwnd)
            win32gui.EnumWindows(enum_callback, None)
            self.label_ventanas.setText(f"Ventanas: {len(handles)}")
        except:
            pass

    def iniciar_script(self):
        self.pushButton_ejecutar.setEnabled(False)
        self.pushButton_parar.setEnabled(True)
        self.label_estado.setText("🟢 Ejecutando...")
        self.label_estado.setStyleSheet("font-weight: bold; color: green;")
        self.textEdit_consola.print_message("=" * 50, QColor(100, 100, 100))
        self.textEdit_consola.print_message("Auto Helper by Tyferiusk INICIADO", QColor(0, 150, 255))
        self.textEdit_consola.print_message("=" * 50, QColor(100, 100, 100))
        self.script_thread.start()
        
        # Timer para actualizar contador de ventanas
        self.timer_ventanas = self.startTimer(300)

    def timerEvent(self, event):
        self.actualizar_contador_ventanas()

    def detener_script(self):
        self.script_thread.requestInterruption()
        self.label_estado.setText("🟡 Deteniendo...")
        self.label_estado.setStyleSheet("font-weight: bold; color: orange;")

    def habilitar_botones(self):
        self.pushButton_ejecutar.setEnabled(True)
        self.pushButton_parar.setEnabled(False)
        self.label_estado.setText("🔴 Detenido")
        self.label_estado.setStyleSheet("font-weight: bold; color: red;")
        self.textEdit_consola.print_message("=" * 50, QColor(100, 100, 100))
        self.textEdit_consola.print_message("Auto Helper DETENIDO", QColor(255, 100, 0))
        self.textEdit_consola.print_message("=" * 50, QColor(100, 100, 100))
        
        # Detener timer
        if hasattr(self, 'timer_ventanas'):
            self.killTimer(self.timer_ventanas)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    ventana = MiVentana()
    ventana.show()
    
    sys.exit(app.exec())