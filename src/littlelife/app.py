"""
Little Life — main.py
- Optional camera preview (CAMERA_ENABLED=0 to disable)
"""

from __future__ import annotations

# =====================================================
# Standard library
# =====================================================
import os
import sys
import threading
import tempfile
from pathlib import Path
from typing import Optional

# =====================================================
# Environment bootstrap (DEPLOYMENT SAFE)
# =====================================================

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

APP_DIR = Path(__file__).resolve().parent


def get_runtime_dir() -> Path:
    """
    Returns the directory where runtime config should live.
    - Dev: project directory
    - Frozen app: directory containing the executable
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return APP_DIR


# Load .env if present (optional).
# loads dotenv unconditionally; keeping the behavior but safer on missing dotenv.
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    load_dotenv(find_dotenv(usecwd=True))
except Exception:
    pass


# Ensure local imports work in dev and frozen builds 
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# =====================================================
# Third-party imports
# =====================================================
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QPixmap, QPalette, QColor, QImage
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QGroupBox,
    QStatusBar,
    QFileDialog,
    QComboBox,
)

import cv2

# Local import (identify_image.py expects OPENAI_API_KEY from env or secrets_store)
from identify_image import identify_image


# =====================================================
# Settings / helpers
# =====================================================

def _env_bool(name: str, default: bool = True) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() not in {"0", "false", "no", "off", ""}


def choose_opencv_backend() -> int:
    """
    Choose an OpenCV VideoCapture backend.

    CAMERA_BACKEND can override:
      auto | v4l2 | avfoundation | dshow | msmf

    Defaults:
    - Linux: V4L2 (best for USB microscopes)
    - macOS: AVFoundation
    - Windows: auto
    """
    pref = (os.getenv("CAMERA_BACKEND", "auto") or "auto").strip().lower()

    # Not all OpenCV builds have all these constants, but most do.
    backend_map = {
        "auto": 0,
        "v4l2": getattr(cv2, "CAP_V4L2", 0),
        "avfoundation": getattr(cv2, "CAP_AVFOUNDATION", 0),
        "dshow": getattr(cv2, "CAP_DSHOW", 0),
        "msmf": getattr(cv2, "CAP_MSMF", 0),
    }

    if pref in backend_map:
        return backend_map[pref]

    if sys.platform.startswith("linux"):
        return backend_map["v4l2"]
    if sys.platform == "darwin":
        return backend_map["avfoundation"]
    return 0


def qpixmap_from_bgr(frame_bgr) -> QPixmap:
    """Convert an OpenCV BGR frame to a QPixmap (copying memory safely)."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


# =====================================================
# Thread → UI communication
# =====================================================

class WorkerSignals(QObject):
    success = Signal(dict)
    error = Signal(str)


# =====================================================
# Main Window
# =====================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Little Life")
        self.resize(980, 620)

        # ===============================
        # LEFT: Image preview / camera
        # ===============================
        self.image_label = QLabel("No image loaded.\nUse Load Image… to test the API.")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(540, 420)
        self.image_label.setStyleSheet(
            "border: 2px dashed #999; border-radius: 10px; padding: 12px;"
        )

        self.capture_btn = QPushButton("Capture")
        self.identify_btn = QPushButton("Identify")
        self.identify_btn.setEnabled(False)

        self.capture_btn.clicked.connect(self.on_capture)
        self.identify_btn.clicked.connect(self.on_identify)

        button_row = QHBoxLayout()
        button_row.addWidget(self.capture_btn)
        button_row.addWidget(self.identify_btn)
        button_row.addStretch()

        left_col = QVBoxLayout()
        left_col.addWidget(self.image_label, stretch=1)
        left_col.addLayout(button_row)

        left_widget = QWidget()
        left_widget.setLayout(left_col)

        # ===============================
        # RIGHT: Identification panel
        # ===============================
        results_box = QGroupBox("Identification")

        self.result_label = QLabel("—")
        self.result_label.setStyleSheet("font-size: 18px; font-weight: 600;")

        self.conf_label = QLabel("Confidence: —")

        self.sample_label = QLabel("Sample type:")
        self.sample_combo = QComboBox()
        self.sample_combo.addItems(["Pond", "Soil", "Tissue", "Crystal", "Other"])
        self.sample_combo.setCurrentText("Pond")

        self.load_btn = QPushButton("Load Image…")
        self.load_btn.clicked.connect(self.on_load_image)

        self.loaded_path_label = QLabel("No file selected.")
        self.loaded_path_label.setWordWrap(True)
        self.loaded_path_label.setStyleSheet("color: #ddd;")

        self.notes = QTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setPlaceholderText("Organism summary / tips will appear here...")
        self.notes.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                border-radius: 6px;
                padding: 6px;
            }
            """
        )

        palette = self.notes.palette()
        palette.setColor(QPalette.Text, QColor("white"))
        palette.setColor(QPalette.PlaceholderText, QColor("#cccccc"))
        self.notes.setPalette(palette)

        rb = QVBoxLayout()
        rb.addWidget(self.result_label)
        rb.addWidget(self.conf_label)
        rb.addWidget(self.sample_label)
        rb.addWidget(self.sample_combo)
        rb.addWidget(self.load_btn)
        rb.addWidget(self.loaded_path_label)
        rb.addWidget(self.notes, stretch=1)
        results_box.setLayout(rb)

        right_col = QVBoxLayout()
        right_col.addWidget(results_box)

        right_widget = QWidget()
        right_widget.setLayout(right_col)
        right_widget.setFixedWidth(340)

        # ===============================
        # Combine layout
        # ===============================
        main_row = QHBoxLayout()
        main_row.addWidget(left_widget, stretch=1)
        main_row.addWidget(right_widget)

        container = QWidget()
        container.setLayout(main_row)
        self.setCentralWidget(container)

        # ===============================
        # Status bar
        # ===============================
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        # ===============================
        # App state
        # ===============================
        self.current_image_path: Optional[str] = None
        self.temp_files: list[str] = []

        self.signals = WorkerSignals()
        self.signals.success.connect(self._on_identify_success)
        self.signals.error.connect(self._on_identify_error)

        # ===============================
        # Camera (optional live view)
        # ===============================
        self.camera_enabled = _env_bool("CAMERA_ENABLED", default=True)
        self.camera_index = int(os.getenv("CAMERA_INDEX", "0"))
        self.camera_width = int(os.getenv("CAMERA_WIDTH", "1280"))
        self.camera_height = int(os.getenv("CAMERA_HEIGHT", "720"))
        self.camera_timer_ms = int(os.getenv("CAMERA_TIMER_MS", "33"))

        self.cap = None
        self.last_frame = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_camera_frame)

        if self.camera_enabled:
            self._start_camera()
        else:
            self.capture_btn.setEnabled(False)
            self.statusBar().showMessage("Camera disabled (CAMERA_ENABLED=0).")

    # =====================================================
    # UI actions
    # =====================================================

    def on_load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select an image",
            str(APP_DIR),
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;All Files (*)",
        )
        if not file_path:
            return

        # If camera is running, stop preview while showing a loaded still.
        if self.camera_enabled:
            self.timer.stop()

        self.current_image_path = file_path
        self.loaded_path_label.setText(file_path)

        pix = QPixmap(file_path)
        if pix.isNull():
            self.image_label.setText("Could not load image preview.")
        else:
            self.image_label.setPixmap(
                pix.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

        self.identify_btn.setEnabled(True)
        self.result_label.setText("—")
        self.conf_label.setText("Confidence: —")
        self.notes.clear()
        self.statusBar().showMessage("Image loaded. Ready to identify.")

    def _start_camera(self):
        # Release prior capture if any
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        backend = choose_opencv_backend()

        # Prefer explicit backend; fallback to auto if needed.
        if backend:
            self.cap = cv2.VideoCapture(self.camera_index, backend)
            if not self.cap.isOpened():
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = cv2.VideoCapture(self.camera_index)
        else:
            self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            self.statusBar().showMessage(f"Camera {self.camera_index} not available.")
            self.capture_btn.setEnabled(False)
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)

        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)

        print(f"[Camera] Active: {w}x{h} @ {fps:.2f} fps (index={self.camera_index})")

        self.timer.start(self.camera_timer_ms)
        self.statusBar().showMessage(f"Live camera running (index {self.camera_index}).")

    def _update_camera_frame(self):
        if self.cap is None:
            return

        ok, frame = self.cap.read()
        if not ok or frame is None:
            return

        self.last_frame = frame

        pix = qpixmap_from_bgr(frame)
        self.image_label.setPixmap(
            pix.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def on_capture(self):
        if not self.camera_enabled:
            self.statusBar().showMessage("Camera disabled.")
            return

        if self.last_frame is None:
            self.statusBar().showMessage("No camera frame yet.")
            return

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp_path = tmp.name
        tmp.close()

        self.temp_files.append(tmp_path)
        cv2.imwrite(tmp_path, self.last_frame)

        self.current_image_path = tmp_path
        self.loaded_path_label.setText(tmp_path)
        self.identify_btn.setEnabled(True)

        self.result_label.setText("—")
        self.conf_label.setText("Confidence: —")
        self.notes.clear()
        self.statusBar().showMessage("Captured frame. Ready to identify.")

    def closeEvent(self, event):
        for p in self.temp_files:
            try:
                os.unlink(p)
            except Exception:
                pass

        try:
            self.timer.stop()
        except Exception:
            pass

        try:
            if self.cap is not None:
                self.cap.release()
        except Exception:
            pass

        super().closeEvent(event)

    def on_identify(self):
        if not self.current_image_path:
            self.statusBar().showMessage("No image selected.")
            return

        img_path = self.current_image_path
        sample_type = self.sample_combo.currentText()

        self.identify_btn.setEnabled(False)
        self.statusBar().showMessage("Identifying…")

        def run():
            try:
                result = identify_image(img_path, sample_type=sample_type)
                self.signals.success.emit(result)
            except Exception as e:
                self.signals.error.emit(str(e))

        threading.Thread(target=run, daemon=True).start()

    # =====================================================
    # Signal handlers
    # =====================================================

    def _on_identify_success(self, result: dict):
        self.result_label.setText(result.get("best_guess_name", "Unknown"))
        self.conf_label.setText(f"Confidence: {result.get('confidence', 0)}/100")

        self.notes.setPlainText(
            f"{result.get('description','')}\n\n"
            f"Features used:\n{result.get('features_used','')}"
        )

        self.identify_btn.setEnabled(True)
        self.statusBar().showMessage("Done.")

    def _on_identify_error(self, message: str):
        self.notes.setPlainText(f"Error:\n{message}")
        self.identify_btn.setEnabled(True)
        self.statusBar().showMessage("Failed.")


# =====================================================
# App entry point
# =====================================================

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
