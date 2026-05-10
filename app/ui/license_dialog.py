from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.services.license_service import LicenseService


class LicenseActivationDialog(QDialog):
    def __init__(self, license_service: LicenseService, parent=None) -> None:
        super().__init__(parent)
        self.license_service = license_service

        self.setWindowTitle("Activate Cafe POS")
        self.setModal(True)
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)

        title = QLabel("Software Activation")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(title)

        help_text = QLabel(
            "Enter your signed activation code below. Trial and permanent codes are both supported."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        machine_text = QTextEdit()
        machine_text.setReadOnly(True)
        machine_text.setMaximumHeight(74)
        machine_text.setText(
            "Machine ID (send this to admin for code generation):\n"
            f"{self.license_service.machine_id()}"
        )
        layout.addWidget(machine_text)

        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("CAFEPOS1-XXXXX-XXXXX-XXXXX-...")
        self.license_input.setMinimumHeight(36)
        layout.addWidget(self.license_input)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #b42318; font-weight: 600;")
        layout.addWidget(self.status_label)

        button_box = QDialogButtonBox()
        self.activate_btn = QPushButton("Activate")
        self.cancel_btn = QPushButton("Exit")
        button_box.addButton(self.activate_btn, QDialogButtonBox.AcceptRole)
        button_box.addButton(self.cancel_btn, QDialogButtonBox.RejectRole)
        layout.addWidget(button_box)

        self.activate_btn.clicked.connect(self._on_activate_clicked)
        self.cancel_btn.clicked.connect(self.reject)
        self.license_input.returnPressed.connect(self._on_activate_clicked)

    def _on_activate_clicked(self) -> None:
        token = self.license_input.text().strip()
        if not token:
            self.status_label.setText("Activation code is required.")
            return

        status = self.license_service.activate_with_token(token)
        if not status.valid:
            self.status_label.setText(status.reason)
            return

        payload = status.payload
        if payload is None:
            QMessageBox.information(self, "Activated", "Activation successful.")
        elif payload.kind == "permanent":
            QMessageBox.information(self, "Activated", "Permanent license activated successfully.")
        else:
            QMessageBox.information(
                self,
                "Activated",
                f"{payload.kind.title()} license activated. Expires: {payload.expires_at}",
            )
        self.accept()


class LicenseManageDialog(LicenseActivationDialog):
    def __init__(self, license_service: LicenseService, parent=None) -> None:
        super().__init__(license_service=license_service, parent=parent)
        self.setWindowTitle("Manage License")
        self.cancel_btn.setText("Close")

        current = self.license_service.summary_text()
        status = QLabel(f"Current Status: {current}")
        status.setWordWrap(True)
        status.setStyleSheet("color: #1d4ed8; font-weight: 700;")
        self.layout().insertWidget(2, status)
