import sys
import threading
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QListWidget, QPushButton, QTextEdit,
                             QLineEdit, QLabel, QSplitter, QInputDialog, QMessageBox,
                             QDialog, QDialogButtonBox, QFormLayout, QTabWidget,
                             QListWidgetItem, QMenu)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QTextCursor, QColor, QBrush
from client.client import ChatClient
from client.hints import Hints


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
        self.current_tab = 0  # 0 = chats, 1 = groups
        self.message_cache = {}  # Store messages by chat
        self.groups_cache = []  # Store group names

        self.signal_emitter = SignalEmitter()
        self.signal_emitter.update_gui.connect(self._handle_gui_update)

        self._setup_ui()
        self._show_login()

    def _setup_ui(self):
        self.setWindowTitle("Chat Application")
        self.setGeometry(100, 100, 1200, 800)

        # Enhanced stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QListWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 5px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e5e5e5;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QLineEdit {
                padding: 10px;
                border: 2px solid #ddd;
                border-radius: 5px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e5e5e5;
                padding: 10px 20px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
                color: white;
            }
        """)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Left sidebar
        sidebar = QWidget()
        sidebar.setMaximumWidth(300)
        sidebar_layout = QVBoxLayout()
        sidebar.setLayout(sidebar_layout)

        # Sidebar title with unread counter
        self.sidebar_title = QLabel("Messages")
        self.sidebar_title.setFont(QFont("Arial", 16, QFont.Bold))
        self.sidebar_title.setStyleSheet("color: #333;")
        sidebar_layout.addWidget(self.sidebar_title)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # === CHATS TAB ===
        chats_tab = QWidget()
        chats_layout = QVBoxLayout()
        chats_tab.setLayout(chats_layout)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self._refresh_chats)
        chats_layout.addWidget(btn_refresh)

        btn_online = QPushButton("🌐 Online Users")
        btn_online.clicked.connect(self._show_online)
        chats_layout.addWidget(btn_online)

        self.chat_list = QListWidget()
        self.chat_list.itemClicked.connect(self._on_chat_select)
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self._show_chat_context_menu)
        chats_layout.addWidget(self.chat_list)

        self.tab_widget.addTab(chats_tab, "💬 Chats")

        # === GROUPS TAB ===
        groups_tab = QWidget()
        groups_layout = QVBoxLayout()
        groups_tab.setLayout(groups_layout)

        btn_new_group = QPushButton("➕ Create Group")
        btn_new_group.clicked.connect(self._create_group)
        groups_layout.addWidget(btn_new_group)

        btn_refresh_groups = QPushButton("🔄 Refresh Groups")
        btn_refresh_groups.clicked.connect(self._refresh_groups)
        groups_layout.addWidget(btn_refresh_groups)

        self.group_list = QListWidget()
        self.group_list.itemClicked.connect(self._on_group_select)
        self.group_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.group_list.customContextMenuRequested.connect(self._show_group_context_menu)
        groups_layout.addWidget(self.group_list)

        self.tab_widget.addTab(groups_tab, "👥 Groups")

        sidebar_layout.addWidget(self.tab_widget)

        # Right side - Chat area
        chat_widget = QWidget()
        chat_layout = QVBoxLayout()
        chat_widget.setLayout(chat_layout)

        # Chat header
        header_container = QWidget()
        header_layout = QHBoxLayout()
        header_container.setLayout(header_layout)
        header_container.setStyleSheet("padding: 10px; background-color: #0078d4; border-radius: 5px;")

        self.chat_header = QLabel("Select a chat to start messaging")
        self.chat_header.setFont(QFont("Arial", 14, QFont.Bold))
        self.chat_header.setStyleSheet("color: white;")
        header_layout.addWidget(self.chat_header)

        btn_clear_history = QPushButton("🗑️ Clear")
        btn_clear_history.clicked.connect(self._clear_history)
        btn_clear_history.setMaximumWidth(100)
        btn_clear_history.setStyleSheet("background-color: #d13438;")
        header_layout.addWidget(btn_clear_history)

        chat_layout.addWidget(header_container)

        # Messages area
        self.messages_area = QTextEdit()
        self.messages_area.setReadOnly(True)
        self.messages_area.setFont(QFont("Segoe UI", 11))
        chat_layout.addWidget(self.messages_area)

        # Input area
        input_layout = QHBoxLayout()

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.message_input)

        send_btn = QPushButton("Send 📤")
        send_btn.clicked.connect(self._send_message)
        send_btn.setMaximumWidth(120)
        input_layout.addWidget(send_btn)

        chat_layout.addLayout(input_layout)

        # Add to main layout
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
                QMessageBox.warning(self, "Error", "Username required")
                sys.exit(0)
        else:
            sys.exit(0)

    def _connect(self, username, timezone):
        try:
            self.client = ChatClient()

            # Override message handler to use GUI signals
            original_handle = self.client.message_handler.handle

            def gui_handle(obj):
                self.signal_emitter.update_gui.emit(obj)

            self.client.message_handler.handle = gui_handle

            self.client.connect()
            self.client.register(username, timezone)

            # Start receiver thread
            receiver_thread = threading.Thread(target=self.client._receive_messages, daemon=True)
            receiver_thread.start()

            # Initial refresh
            self._refresh_chats()
            self._refresh_groups()

        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))
            sys.exit(1)

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
            QMessageBox.information(self, "Group Created",
                                    f"Group '{obj.get('group_name')}' created by {obj.get('created_by')}")
            self._refresh_groups()
        elif msg_type == 'group_modified':
            QMessageBox.information(self, "Group Modified",
                                    f"{obj.get('action').title()}: {obj.get('member')}")
            self._refresh_groups()
        elif msg_type == 'history_cleared':
            self.messages_area.clear()
            self.messages_area.append(f"✓ History cleared with {obj.get('with_user')}")
        elif msg_type == 'online':
            # FIX: Transform server data into expected format
            users_list = obj.get('users', [])
            timezones_list = obj.get('timezones', [])
            online_users = [
                {'alias': u, 'timezone': t}
                for u, t in zip(users_list, timezones_list)
            ]
            self._show_online_users(online_users)
        elif msg_type == 'error':
            QMessageBox.warning(self, "Error", obj.get('what', 'Unknown error'))

    def _show_online_users(self, users):
        """Display online users dialog"""
        if not users:
            QMessageBox.information(self, "Online Users", "No users online")
            return

        online_list = "\n".join([f"🟢 {u['alias']} ({u['timezone']})" for u in users])
        QMessageBox.information(self, "Online Users", online_list)

    def _handle_new_message(self, msg):
        """Handle incoming message and update unread counters"""
        sender = msg.get('from')
        to = msg.get('to')
        text = msg.get('text', '')
        is_group = msg.get('group', False)

        # Increment unread counter (only for messages from others)
        if sender != self.client.alias:
            counter_key = to if is_group else sender

            with self.client.lock:
                self.client.unread_counts[counter_key] = \
                    self.client.unread_counts.get(counter_key, 0) + 1

            # Play notification sound
            Hints.play_notification()

            # Update unread indicators
            self._update_unread_indicators()

        # Display message if viewing current chat
        if self.current_chat and \
                ((is_group and to == self.current_chat) or \
                 (not is_group and (sender == self.current_chat or to == self.current_chat))):
            self._display_single_message(msg)

    def _display_single_message(self, msg):
        """Display a single message in the chat area"""
        sender = msg.get('from')
        text = msg.get('text', '')
        ts = msg.get('ts', 0)
        deleted = msg.get('deleted', False)
        msg_id = msg.get('id', '')

        timestamp = datetime.fromtimestamp(ts).strftime('%H:%M:%S')

        cursor = self.messages_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        if deleted:
            cursor.insertHtml(
                f"<p style='color: gray; font-style: italic;'>[{msg_id}] {timestamp} - Message deleted</p>")
        elif sender == self.client.alias:
            # Your messages (blue bubble on right)
            cursor.insertHtml(
                f"<div style='text-align: right; margin: 5px 0;'>"
                f"<span style='background-color: #0078d4; color: white; padding: 8px 12px; "
                f"border-radius: 15px; display: inline-block; max-width: 70%;'>"
                f"<b>You</b> {timestamp}<br>{text}"
                f"</span></div>"
            )
        else:
            # Others' messages (gray bubble on left)
            cursor.insertHtml(
                f"<div style='text-align: left; margin: 5px 0;'>"
                f"<span style='background-color: #e5e5e5; color: black; padding: 8px 12px; "
                f"border-radius: 15px; display: inline-block; max-width: 70%;'>"
                f"<b>{sender}</b> {timestamp}<br>{text}"
                f"</span></div>"
            )

        self.messages_area.setTextCursor(cursor)
        self.messages_area.ensureCursorVisible()

    def _display_history(self, obj):
        """Display message history"""
        messages = obj.get('messages', [])
        was_cleared = obj.get('cleared', False)

        self.messages_area.clear()

        if was_cleared:
            self.messages_area.append("⚠️ History was previously cleared\n")

        if not messages:
            self.messages_area.append("No messages to display")
        else:
            for msg in messages:
                self._display_single_message(msg)

    def _send_message(self):
        """Send a message"""
        if not self.current_chat or not self.client:
            QMessageBox.warning(self, "No Chat", "Select a chat first")
            return

        text = self.message_input.text().strip()
        if not text:
            return

        # Check if it's a group chat
        is_group = self.current_chat in self.groups_cache

        payload = {
            "type": "chat",
            "text": text,
            "to": self.current_chat,
            "group": is_group
        }

        self.client._send(payload)
        self.message_input.clear()

    def _on_chat_select(self, item):
        """Handle chat selection and reset unread counter"""
        chat_text = item.text()
        # Remove unread counter from display text
        self.current_chat = chat_text.split(' (')[0] if '(' in chat_text else chat_text
        self.current_tab = 0

        self.chat_header.setText(f"💬 Chat with {self.current_chat}")

        # Reset unread counter for this chat
        with self.client.lock:
            if self.current_chat in self.client.unread_counts:
                self.client.unread_counts[self.current_chat] = 0

        # Update UI to remove unread indicator
        self._update_unread_indicators()

        # Load chat history
        self.messages_area.clear()
        payload = {"type": "message_history", "with_user": self.current_chat, "limit": 50}
        self.client._send(payload)

    def _on_group_select(self, item):
        """Handle group selection and reset unread counter"""
        group_text = item.text()
        self.current_chat = group_text.split(' (')[0] if '(' in group_text else group_text
        self.current_tab = 1

        self.chat_header.setText(f"👥 Group: {self.current_chat}")

        # Reset unread counter for this group
        with self.client.lock:
            if self.current_chat in self.client.unread_counts:
                self.client.unread_counts[self.current_chat] = 0

        # Update UI
        self._update_unread_indicators()

        # Load group history
        self.messages_area.clear()
        payload = {"type": "message_history", "with_user": self.current_chat, "limit": 50}
        self.client._send(payload)

    def _on_tab_changed(self, index):
        """Handle tab change"""
        self.current_tab = index

    def _update_chat_list(self, users):
        """Update chat list with unread indicators"""
        self.chat_list.clear()

        with self.client.lock:
            chats = [u for u in users if u != self.client.alias]
            unread_counts = self.client.unread_counts.copy()

        for user in chats:
            unread = unread_counts.get(user, 0)

            if unread > 0:
                item_text = f"{user} ({unread} unread)"
                item = QListWidgetItem(item_text)
                # Yellow background for unread
                item.setBackground(QBrush(QColor("#fff3cd")))
                # Bold text
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item = QListWidgetItem(user)

            self.chat_list.addItem(item)

    def _update_groups_list(self, groups):
        """Update groups list with unread indicators"""
        self.group_list.clear()
        self.groups_cache = groups  # Store for later use

        with self.client.lock:
            unread_counts = self.client.unread_counts.copy()

        for group in groups:
            unread = unread_counts.get(group, 0)

            if unread > 0:
                item_text = f"{group} ({unread} unread)"
                item = QListWidgetItem(item_text)
                # Yellow background for unread
                item.setBackground(QBrush(QColor("#fff3cd")))
                # Bold text
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item = QListWidgetItem(group)

            self.group_list.addItem(item)

    def _update_unread_indicators(self):
        """Update sidebar title with total unread count"""
        with self.client.lock:
            total_unread = sum(self.client.unread_counts.values())

        if total_unread > 0:
            self.sidebar_title.setText(f"Messages ({total_unread})")
            self.sidebar_title.setStyleSheet("color: #d13438; font-weight: bold;")
        else:
            self.sidebar_title.setText("Messages")
            self.sidebar_title.setStyleSheet("color: #333;")

        # Refresh both lists to update UI
        self._refresh_chats()
        self._refresh_groups()

    def _refresh_chats(self):
        """Refresh chat list"""
        if self.client:
            self.client._send({"type": "chatlist"})

    def _refresh_groups(self):
        """Refresh groups list"""
        if self.client:
            self.client._send({"type": "list_groups"})

    def _show_online(self):
        """Request online users"""
        self.client._send({"type": "online"})

    def _create_group(self):
        """Create a new group"""
        group_name, ok = QInputDialog.getText(self, "Create Group", "Group name:")
        if not ok or not group_name:
            return

        members_str, ok = QInputDialog.getText(self, "Create Group",
                                               "Members (comma separated, exclude yourself):")
        if not ok:
            return

        members = [m.strip() for m in members_str.split(',') if m.strip()]

        payload = {'type': 'create_group', 'group_name': group_name, 'members': members}
        self.client._send(payload)

    def _clear_history(self):
        """Clear chat history"""
        if not self.current_chat:
            QMessageBox.warning(self, "No Chat", "Select a chat first")
            return

        reply = QMessageBox.question(
            self, "Clear History",
            f"Clear history with '{self.current_chat}'?\nThis only affects your view.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            payload = {"type": "clear_history", "with_user": self.current_chat}
            self.client._send(payload)

    def _show_chat_context_menu(self, position):
        """Right-click menu for chat list"""
        item = self.chat_list.itemAt(position)
        if not item:
            return

        menu = QMenu()
        clear_action = menu.addAction("🗑️ Clear History")
        mark_read_action = menu.addAction("✓ Mark as Read")

        action = menu.exec_(self.chat_list.mapToGlobal(position))

        if action == clear_action:
            chat_name = item.text().split(' (')[0]
            self.current_chat = chat_name
            self._clear_history()
        elif action == mark_read_action:
            chat_name = item.text().split(' (')[0]
            with self.client.lock:
                self.client.unread_counts[chat_name] = 0
            self._update_unread_indicators()

    def _show_group_context_menu(self, position):
        """Right-click menu for group list"""
        item = self.group_list.itemAt(position)
        if not item:
            return

        menu = QMenu()
        clear_action = menu.addAction("🗑️ Clear History")
        mark_read_action = menu.addAction("✓ Mark as Read")
        add_member_action = menu.addAction("➕ Add Member")
        remove_member_action = menu.addAction("➖ Remove Member")

        action = menu.exec_(self.group_list.mapToGlobal(position))

        group_name = item.text().split(' (')[0]

        if action == clear_action:
            self.current_chat = group_name
            self._clear_history()
        elif action == mark_read_action:
            with self.client.lock:
                self.client.unread_counts[group_name] = 0
            self._update_unread_indicators()
        elif action == add_member_action:
            member, ok = QInputDialog.getText(self, "Add Member", "Member username:")
            if ok and member:
                payload = {'type': 'modify_group', 'group_name': group_name, 'action': 'add', 'member': member}
                self.client._send(payload)
        elif action == remove_member_action:
            member, ok = QInputDialog.getText(self, "Remove Member", "Member username:")
            if ok and member:
                payload = {'type': 'modify_group', 'group_name': group_name, 'action': 'remove', 'member': member}
                self.client._send(payload)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = ChatGUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
