"""
Class Selector Popup Widget
===========================
Class selection menu that opens in top-right corner after BBox drawing.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QBrush, QKeyEvent


class ClassSelectorPopup(QFrame):
    """
    Class selector popup widget.
    Shown in top-right corner when BBox drawing is completed.
    """
    
    # Signals
    class_selected = Signal(int)  # Selected class ID
    cancelled = Signal()
    closed = Signal()  # When popup is closed
    navigate_requested = Signal(str)  # 'next' or 'prev' - request to change photo
    
    def __init__(self, class_manager, last_used_class_id: int = 0, parent=None):
        super().__init__(parent)
        self._class_manager = class_manager
        self._last_used_class_id = last_used_class_id
        self._buttons = []
        
        # Drag state for movable popup
        self._drag_pos = None
        
        # Non-modal window - allow interaction with bbox
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        
        # Listen for focus change - close when window changes
        from PySide6.QtWidgets import QApplication
        QApplication.instance().focusChanged.connect(self._on_focus_changed)
        
        self._setup_ui()
        
    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: #2b2b2b;
                border: 2px solid #0d6efd;
                border-radius: 8px;
                padding: 8px;
            }
            QPushButton {
                text-align: left;
                padding: 8px 12px;
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #3c3c3c;
            }
            QPushButton:focus {
                background: #0d6efd;
            }
            QLabel {
                color: #888;
                font-size: 11px;
                padding: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Title
        title = QLabel(self.tr("Select Class (1-9 or Enter)"))
        layout.addWidget(title)
        
        # Class buttons
        for idx, label_class in enumerate(self._class_manager.classes):
            btn = QPushButton()
            btn.setIcon(self._create_color_icon(label_class.color))
            
            # Show keyboard shortcut (1-9)
            shortcut_text = f"[{idx + 1}]" if idx < 9 else ""
            btn.setText(f"{shortcut_text} {label_class.name}")
            btn.setProperty("class_id", label_class.id)
            
            # Highlight default class
            if label_class.id == self._last_used_class_id:
                btn.setStyleSheet(btn.styleSheet() + "background: #0d6efd;")
                btn.setFocus()
            
            btn.clicked.connect(lambda checked, cid=label_class.id: self._on_class_clicked(cid))
            layout.addWidget(btn)
            self._buttons.append(btn)
        
        # Cancel info
        cancel_label = QLabel(self.tr("ESC: Cancel"))
        layout.addWidget(cancel_label)
        
    def _create_color_icon(self, color_hex: str, size: int = 16) -> QIcon:
        """Create color icon."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color_hex)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, size, size, 3, 3)
        painter.end()
        
        return QIcon(pixmap)
    
    def _on_class_clicked(self, class_id: int):
        """When class button is clicked."""
        self.class_selected.emit(class_id)
        self.close()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Keyboard events."""
        key = event.key()
        
        # ESC - cancel
        if key == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
            return
        
        # Enter - select default class
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.class_selected.emit(self._last_used_class_id)
            self.close()
            return
        
        # A/Left - previous image
        if key in (Qt.Key.Key_A, Qt.Key.Key_Left):
            self.navigate_requested.emit('prev')
            self.close()
            return
        
        # D/Right - next image
        if key in (Qt.Key.Key_D, Qt.Key.Key_Right):
            self.navigate_requested.emit('next')
            self.close()
            return
        
        # 1-9 keys - select class
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            if idx < len(self._buttons):
                class_id = self._buttons[idx].property("class_id")
                self.class_selected.emit(class_id)
                self.close()
                return
        
        super().keyPressEvent(event)
    
    def show_at(self, global_pos: QPoint):
        """Show at specified position."""
        self.move(global_pos)
        self.show()
        self.setFocus()
    
    def closeEvent(self, event):
        """Send signal when popup is closed."""
        # Disconnect focus change
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().focusChanged.disconnect(self._on_focus_changed)
        except:
            pass
        self.closed.emit()
        super().closeEvent(event)
    
    def _on_focus_changed(self, old, new):
        """Close popup if application loses focus."""
        if not self.isVisible():
            return
        
        # If new focus widget is None (switched to another app)
        # or not this popup or one of its child widgets
        if new is None:
            self.close()
        elif new is not None:
            # Check if focus is inside this popup
            widget = new
            while widget is not None:
                if widget is self:
                    return  # Inside popup, don't close
                widget = widget.parent()
            # Outside popup - switched to another window
            # Check if inside main application
            if new.window() != self:
                # If focus goes outside application, close
                pass
    
    def mousePressEvent(self, event):
        """Save start position to drag popup."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Drag popup."""
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            diff = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + diff)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Drag completed."""
        self._drag_pos = None
        super().mouseReleaseEvent(event)
