import sys
import threading
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QListWidget, QPushButton, QTextEdit,
                             QLineEdit, QLabel, QSplitter, QInputDialog, QMessageBox,
                             QDialog, QDialogButtonBox, QFormLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QTextCursor, QColor
from client.client import ChatClient


class SignalEmitter(QObject):
    """Helper class to emit signals from background threads"""
    message_received = pyqtSignal(dict)
    update_gui = pyqtSignal(dict)


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setModal(True)
        self.resize(350, 150)

        layout = QFormLayout()

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        layout.addRow("Username:", self.username_input)

        self.timezone_input = QLineEdit("UTC+06:00")
        self.timezone_input.setPlaceholderText("e.g., UTC+06:00")
        layout.addRow("Timezone:", self.timezone_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def get_credentials(self):
        return self.username_input.text().strip(), self.timezone_input.text().strip() or "UTC+06:00"


class ChatGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.client = None
        self.current_chat = None
        self.message_cache = {}  # Store messages by chat

        self.signal_emitter = SignalEmitter()
        self.signal_emitter.update_gui.connect(self._handle_gui_update)

        self._setup_ui()
        self._show_login()

    def _setup_ui(self):
        self.setWindowTitle("Chat Application")
        self.setGeometry(100, 100, 1000, 700)

        # Apply stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QListWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e5f3ff;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QLabel {
                font-weight: bold;
                color: #333;
            }
        """)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Left sidebar
        sidebar = QWidget()
        sidebar.setMaximumWidth(250)
        sidebar_layout = QVBoxLayout()
        sidebar.setLayout(sidebar_layout)

        sidebar_label = QLabel("Chats")
        sidebar_label.setFont(QFont("Arial", 14, QFont.Bold))
        sidebar_layout.addWidget(sidebar_label)

        # Action buttons
        btn_online = QPushButton("🌐 Online Users")
        btn_online.clicked.connect(self._show_online)
        sidebar_layout.addWidget(btn_online)

        btn_groups = QPushButton("👥 My Groups")
        btn_groups.clicked.connect(self._show_groups)
        sidebar_layout.addWidget(btn_groups)

        btn_new_group = QPushButton("➕ New Group")
        btn_new_group.clicked.connect(self._create_group)
        sidebar_layout.addWidget(btn_new_group)

        # Chat list
        self.chat_list = QListWidget()
        self.chat_list.itemClicked.connect(self._on_chat_select)
        sidebar_layout.addWidget(self.chat_list)

        # Right side - Chat area
        chat_widget = QWidget()
        chat_layout = QVBoxLayout()
        chat_widget.setLayout(chat_layout)

        # Chat header
        self.chat_header = QLabel("Select a chat to start messaging")
        self.chat_header.setFont(QFont("Arial", 12, QFont.Bold))
        self.chat_header.setStyleSheet("padding: 10px; background-color: #0078d4; color: white; border-radius: 5px;")
        chat_layout.addWidget(self.chat_header)

        # Messages area
        self.messages_area = QTextEdit()
        self.messages_area.setReadOnly(True)
        self.messages_area.setFont(QFont("Segoe UI", 10))
        chat_layout.addWidget(self.messages_area)

        # Input area
        input_layout = QHBoxLayout()

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.message_input)

        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._send_message)
        send_btn.setMaximumWidth(100)
        input_layout.addWidget(send_btn)

        chat_layout.addLayout(input_layout)

        # Add to main layout with splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(sidebar)
        splitter.addWidget(chat_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)

    def _show_login(self):
        dialog = LoginDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            username, timezone = dialog.get_credentials()
            if username:
                self._connect(username, timezone)
            else:
                QMessageBox.warning(self, "Error", "Username is required!")
                self._show_login()
        else:
            sys.exit()

    def _connect(self, username, timezone):
        try:
            self.client = ChatClient()
            self.client.connect()
            self.client.register(username, timezone)

            # Override message handler
            original_handle = self.client.message_handler.handle

            def gui_handle(obj):
                original_handle(obj)
                self.signal_emitter.update_gui.emit(obj)

            self.client.message_handler.handle = gui_handle

            # Start receiving messages
            threading.Thread(target=self.client._receive_messages, daemon=True).start()

            self.setWindowTitle(f"Chat Application - {username}")
            self._refresh_chats()

        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))
            sys.exit()

    def _handle_gui_update(self, obj):
        msg_type = obj.get('type')

        if msg_type == 'message':
            self._handle_new_message(obj)
        elif msg_type == 'chatlist':
            self._update_chat_list(obj.get('users', []))
        elif msg_type == 'groups_list':
            self._update_groups_list(obj.get('groups', []))
        elif msg_type == 'message_history':
            self._display_history(obj)
        elif msg_type == 'group_created':
            QMessageBox.information(self, "Success", f"Group '{obj.get('group_name')}' created!")
            self._refresh_chats()
        elif msg_type == 'error':
            QMessageBox.warning(self, "Error", obj.get('what', 'Unknown error'))

    def _handle_new_message(self, msg):
        sender = msg.get('from')
        to = msg.get('to')
        text = msg.get('text', '')
        ts = msg.get('ts', 0)
        is_group = msg.get('group', False)

        # Determine chat identifier
        if is_group:
            chat_id = to
        else:
            chat_id = sender if sender != self.client.alias else to

        # Cache the message
        if chat_id not in self.message_cache:
            self.message_cache[chat_id] = []
        self.message_cache[chat_id].append(msg)

        # Update UI if this is the current chat
        if self.current_chat == chat_id:
            self._display_single_message(msg)

    def _display_single_message(self, msg):
        sender = msg.get('from')
        text = msg.get('text', '')
        ts = msg.get('ts', 0)
        deleted = msg.get('deleted', False)

        timestamp = datetime.fromtimestamp(ts).strftime('%H:%M:%S')

        cursor = self.messages_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        if sender == self.client.alias:
            cursor.insertHtml(f'<p style="color: #0078d4;"><b>[{timestamp}] You:</b> {text}</p>')
        else:
            cursor.insertHtml(f'<p style="color: #2d7d2d;"><b>[{timestamp}] {sender}:</b> {text}</p>')

        if deleted:
            cursor.insertHtml('<p style="color: red; text-decoration: line-through;">[DELETED]</p>')

        self.messages_area.setTextCursor(cursor)
        self.messages_area.ensureCursorVisible()

    def _display_history(self, obj):
        messages = obj.get('messages', [])

        self.messages_area.clear()

        for msg in messages:
            self._display_single_message(msg)

    def _send_message(self):
        if not self.current_chat or not self.client:
            return

        text = self.message_input.text().strip()
        if not text:
            return

        # Check if it's a group chat
        is_group = self.current_chat in [g for g in getattr(self.client, 'groups', [])]

        payload = {
            "type": "chat",
            "text": text,
            "to": self.current_chat,
            "group": is_group
        }

        self.client._send(payload)
        self.message_input.clear()

    def _on_chat_select(self, item):
        self.current_chat = item.text()
        self.chat_header.setText(f"Chat with {self.current_chat}")

        # Load history
        self.messages_area.clear()

        payload = {"type": "message_history", "with_user": self.current_chat, "limit": 50}
        self.client._send(payload)

    def _update_chat_list(self, users):
        self.chat_list.clear()
        for user in users:
            if user != self.client.alias:
                self.chat_list.addItem(user)

    def _update_groups_list(self, groups):
        # Show groups in a message box for now
        if groups:
            QMessageBox.information(self, "Your Groups", "\n".join(groups))
        else:
            QMessageBox.information(self, "Your Groups", "You're not in any groups yet.")

    def _refresh_chats(self):
        if self.client:
            self.client._send({"type": "chatlist"})
            self.client._send({"type": "online"})

    def _show_online(self):
        self.client._send({"type": "online"})
        self._refresh_chats()

    def _show_groups(self):
        self.client._send({"type": "list_groups"})

    def _create_group(self):
        group_name, ok = QInputDialog.getText(self, "Create Group", "Group name:")
        if not ok or not group_name:
            return

        members_str, ok = QInputDialog.getText(self, "Create Group", "Members (comma separated):")
        if not ok:
            return

        members = [m.strip() for m in members_str.split(',') if m.strip()]

        payload = {'type': 'create_group', 'group_name': group_name, 'members': members}
        self.client._send(payload)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look

    window = ChatGUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
