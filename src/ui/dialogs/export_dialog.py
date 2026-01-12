"""
Export Format Dialogu
=====================
Çeşitli formatlarda export seçimi için dialog.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QPushButton, QLabel, QComboBox, QLineEdit, QFileDialog,
    QTextEdit, QProgressBar, QMessageBox, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

from core.class_manager import ClassManager
from core.annotation_manager import AnnotationManager
from core.exporter import (
    YOLOExporter, COCOExporter, CustomTXTExporter, CustomJSONExporter
)


class ExportWorker(QThread):
    """Export işlemini arka planda çalıştırır."""
    
    progress = Signal(int, int)  # current, total
    finished = Signal(int)  # exported count
    error = Signal(str)
    
    def __init__(self, exporter, annotations_dict, output_dir, image_files):
        super().__init__()
        self.exporter = exporter
        self.annotations_dict = annotations_dict
        self.output_dir = output_dir
        self.image_files = image_files
    
    def run(self):
        try:
            self.exporter.set_progress_callback(self._on_progress)
            count = self.exporter.export(
                self.annotations_dict, 
                self.output_dir, 
                self.image_files
            )
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))
    
    def _on_progress(self, current, total):
        self.progress.emit(current, total)


class ExportFormatDialog(QDialog):
    """
    Export format seçimi dialog'u.
    
    Özellikler:
    - Format seçimi (YOLO, COCO, Custom)
    - YOLO versiyon seçimi
    - Custom format için örnek dosya yükleme
    - Çıktı klasörü seçimi
    - İlerleme çubuğu
    """
    
    def __init__(
        self, 
        class_manager: ClassManager, 
        annotation_manager: AnnotationManager,
        image_files: list,
        default_output_dir: Path = None,
        parent=None
    ):
        super().__init__(parent)
        self._class_manager = class_manager
        self._annotation_manager = annotation_manager
        self._image_files = image_files
        self._default_output_dir = default_output_dir
        
        self._custom_json_template = None
        self._worker = None
        
        self.setWindowTitle("Dışa Aktar")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)
        
        self._setup_ui()
        self._connect_signals()
        self._update_ui_state()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Başlık
        title = QLabel("📦 Export Format Seçimi")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Format seçimi
        format_group = QGroupBox("Format")
        format_layout = QVBoxLayout(format_group)
        
        self.format_btn_group = QButtonGroup(self)
        
        # YOLO seçeneği
        yolo_layout = QHBoxLayout()
        self.yolo_radio = QRadioButton("YOLO")
        self.yolo_radio.setChecked(True)
        self.format_btn_group.addButton(self.yolo_radio, 0)
        yolo_layout.addWidget(self.yolo_radio)
        
        self.yolo_version_combo = QComboBox()
        self.yolo_version_combo.addItems([
            "YOLOv5", "YOLOv6", "YOLOv7", "YOLOv8", 
            "YOLOv9", "YOLOv10", "YOLOv11"
        ])
        self.yolo_version_combo.setCurrentText("YOLOv8")
        yolo_layout.addWidget(self.yolo_version_combo)
        yolo_layout.addStretch()
        format_layout.addLayout(yolo_layout)
        
        yolo_info = QLabel("💡 Tüm YOLO versiyonları aynı formatı kullanır")
        yolo_info.setStyleSheet("color: gray; font-size: 11px; margin-left: 20px;")
        format_layout.addWidget(yolo_info)
        
        # COCO seçeneği
        self.coco_radio = QRadioButton("COCO (JSON)")
        self.format_btn_group.addButton(self.coco_radio, 1)
        format_layout.addWidget(self.coco_radio)
        
        coco_info = QLabel("💡 Standart COCO annotation formatı (segmentation dahil)")
        coco_info.setStyleSheet("color: gray; font-size: 11px; margin-left: 20px;")
        format_layout.addWidget(coco_info)
        
        # Custom seçeneği
        self.custom_radio = QRadioButton("Custom (Özel Format)")
        self.format_btn_group.addButton(self.custom_radio, 2)
        format_layout.addWidget(self.custom_radio)
        
        layout.addWidget(format_group)
        
        # Custom format ayarları
        self.custom_group = QGroupBox("Custom Format Ayarları")
        custom_layout = QVBoxLayout(self.custom_group)
        
        # Format tipi
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Format tipi:"))
        
        self.custom_type_combo = QComboBox()
        self.custom_type_combo.addItems(["TXT", "JSON"])
        type_layout.addWidget(self.custom_type_combo)
        type_layout.addStretch()
        custom_layout.addLayout(type_layout)
        
        # TXT format string
        self.txt_format_group = QGroupBox("Format String")
        txt_format_layout = QVBoxLayout(self.txt_format_group)
        
        self.format_string_input = QLineEdit()
        self.format_string_input.setText("{class_id} {x_center} {y_center} {width} {height}")
        self.format_string_input.setPlaceholderText("Örn: {class_id} {x_center} {y_center} {width} {height}")
        txt_format_layout.addWidget(self.format_string_input)
        
        placeholders_info = QLabel(
            "Kullanılabilir: {class_id}, {class_name}, {x_center}, {y_center}, "
            "{width}, {height}, {x1}, {y1}, {x2}, {y2}, "
            "{x1_pixel}, {y1_pixel}, {x2_pixel}, {y2_pixel}"
        )
        placeholders_info.setWordWrap(True)
        placeholders_info.setStyleSheet("color: gray; font-size: 10px;")
        txt_format_layout.addWidget(placeholders_info)
        
        custom_layout.addWidget(self.txt_format_group)
        
        # JSON şablon yükleme
        self.json_format_group = QGroupBox("JSON Şablonu")
        json_format_layout = QVBoxLayout(self.json_format_group)
        
        json_btn_layout = QHBoxLayout()
        self.load_json_btn = QPushButton("📂 Şablon Yükle...")
        json_btn_layout.addWidget(self.load_json_btn)
        self.json_status_label = QLabel("Şablon yüklenmedi")
        self.json_status_label.setStyleSheet("color: gray;")
        json_btn_layout.addWidget(self.json_status_label)
        json_btn_layout.addStretch()
        json_format_layout.addLayout(json_btn_layout)
        
        json_info = QLabel(
            "💡 JSON şablonu yüklemezseniz, varsayılan nested yapı kullanılacak"
        )
        json_info.setWordWrap(True)
        json_info.setStyleSheet("color: gray; font-size: 10px;")
        json_format_layout.addWidget(json_info)
        
        custom_layout.addWidget(self.json_format_group)
        
        layout.addWidget(self.custom_group)
        
        # Çıktı klasörü
        output_group = QGroupBox("Çıktı Klasörü")
        output_layout = QHBoxLayout(output_group)
        
        self.output_path_input = QLineEdit()
        if self._default_output_dir:
            self.output_path_input.setText(str(self._default_output_dir))
        self.output_path_input.setPlaceholderText("Çıktı klasörünü seçin...")
        output_layout.addWidget(self.output_path_input)
        
        self.browse_btn = QPushButton("📁 Gözat...")
        output_layout.addWidget(self.browse_btn)
        
        layout.addWidget(output_group)
        
        # Bilgi
        info_label = QLabel(f"📊 {len(self._image_files)} görsel export edilecek")
        info_label.setStyleSheet("color: #2196F3;")
        layout.addWidget(info_label)
        
        # İlerleme çubuğu
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Butonlar
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("İptal")
        self.cancel_btn.setStyleSheet("padding: 8px 20px;")
        button_layout.addWidget(self.cancel_btn)
        
        self.export_btn = QPushButton("📦 Dışa Aktar")
        self.export_btn.setStyleSheet(
            "padding: 8px 24px; background-color: #4CAF50; color: white; font-weight: bold;"
        )
        button_layout.addWidget(self.export_btn)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        self.format_btn_group.buttonClicked.connect(self._on_format_changed)
        self.custom_type_combo.currentTextChanged.connect(self._on_custom_type_changed)
        self.browse_btn.clicked.connect(self._browse_output)
        self.load_json_btn.clicked.connect(self._load_json_template)
        self.export_btn.clicked.connect(self._start_export)
        self.cancel_btn.clicked.connect(self.reject)
    
    def _update_ui_state(self):
        """UI durumunu güncelle."""
        is_custom = self.custom_radio.isChecked()
        self.custom_group.setVisible(is_custom)
        
        is_yolo = self.yolo_radio.isChecked()
        self.yolo_version_combo.setEnabled(is_yolo)
        
        if is_custom:
            is_txt = self.custom_type_combo.currentText() == "TXT"
            self.txt_format_group.setVisible(is_txt)
            self.json_format_group.setVisible(not is_txt)
        
        # Dialog boyutunu ayarla
        self.adjustSize()
    
    def _on_format_changed(self, btn):
        self._update_ui_state()
    
    def _on_custom_type_changed(self, text):
        self._update_ui_state()
    
    def _browse_output(self):
        """Çıktı klasörü seç."""
        folder = QFileDialog.getExistingDirectory(
            self, "Çıktı Klasörü Seç",
            str(self._default_output_dir) if self._default_output_dir else ""
        )
        if folder:
            self.output_path_input.setText(folder)
    
    def _load_json_template(self):
        """JSON şablon dosyası yükle."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "JSON Şablon Seç", "",
            "JSON Dosyaları (*.json)"
        )
        if file_path:
            try:
                import json
                with open(file_path, "r", encoding="utf-8") as f:
                    self._custom_json_template = json.load(f)
                self.json_status_label.setText(f"✓ {Path(file_path).name}")
                self.json_status_label.setStyleSheet("color: green;")
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"JSON dosyası okunamadı:\n{e}")
    
    def _start_export(self):
        """Export işlemini başlat."""
        output_path = self.output_path_input.text().strip()
        if not output_path:
            QMessageBox.warning(self, "Uyarı", "Lütfen çıktı klasörünü seçin.")
            return
        
        output_dir = Path(output_path)
        
        # Exporter oluştur
        exporter = self._create_exporter()
        if exporter is None:
            return
        
        # Annotations dict oluştur
        annotations_dict = {}
        for image_path in self._image_files:
            key = str(image_path)
            if key in self._annotation_manager._annotations:
                annotations_dict[key] = self._annotation_manager._annotations[key]
        
        # UI'ı hazırla
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self._image_files))
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Export başlatılıyor...")
        self.export_btn.setEnabled(False)
        
        # Worker oluştur ve başlat
        self._worker = ExportWorker(
            exporter, annotations_dict, output_dir, self._image_files
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_export_finished)
        self._worker.error.connect(self._on_export_error)
        self._worker.start()
    
    def _create_exporter(self):
        """Seçilen formata göre exporter oluştur."""
        if self.yolo_radio.isChecked():
            version = self.yolo_version_combo.currentText().replace("YOLO", "")
            return YOLOExporter(self._class_manager, version)
        
        elif self.coco_radio.isChecked():
            return COCOExporter(self._class_manager)
        
        elif self.custom_radio.isChecked():
            if self.custom_type_combo.currentText() == "TXT":
                format_string = self.format_string_input.text().strip()
                if not format_string:
                    QMessageBox.warning(self, "Uyarı", "Lütfen format string'i girin.")
                    return None
                return CustomTXTExporter(self._class_manager, format_string)
            else:
                return CustomJSONExporter(
                    self._class_manager, 
                    self._custom_json_template or {}
                )
        
        return None
    
    def _on_progress(self, current, total):
        """İlerleme güncelle."""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Export ediliyor: {current}/{total}")
    
    def _on_export_finished(self, count):
        """Export tamamlandığında."""
        self.progress_bar.setValue(self.progress_bar.maximum())
        
        output_path = self.output_path_input.text()
        format_name = self._get_format_name()
        
        QMessageBox.information(
            self, "Başarılı",
            f"✓ {count} görsel {format_name} formatında dışa aktarıldı.\n\n"
            f"Konum: {output_path}"
        )
        self.accept()
    
    def _on_export_error(self, error_msg):
        """Export hatası."""
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        self.export_btn.setEnabled(True)
        
        QMessageBox.critical(self, "Hata", f"Export sırasında hata oluştu:\n{error_msg}")
    
    def _get_format_name(self) -> str:
        """Seçilen format adını döndür."""
        if self.yolo_radio.isChecked():
            return self.yolo_version_combo.currentText()
        elif self.coco_radio.isChecked():
            return "COCO JSON"
        elif self.custom_radio.isChecked():
            return f"Custom {self.custom_type_combo.currentText()}"
        return "Unknown"
    
    def closeEvent(self, event):
        """Dialog kapatılırken."""
        if self._worker and self._worker.isRunning():
            self._worker.wait()
        super().closeEvent(event)
