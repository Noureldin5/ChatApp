import sys
import threading
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QListWidget, QPushButton, QTextEdit,
                             QLineEdit, QLabel, QSplitter, QInputDialog, QMessageBox,
                             QDialog, QDialogButtonBox, QFormLayout, QTabWidget,
                             QListWidgetItem, QMenu, QShortcut, QToolButton)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QKeySequence
from client.client import ChatClient
from client.hints import Hints


class SignalEmitter(QObject):
    """Helper class to emit signals from background threads"""
    update_gui = pyqtSignal(dict)

    def __init__(self):
        super().__init__()


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login to Chat")
        self.setModal(True)
        self.resize(350, 150)

        layout = QFormLayout()
        layout.setSpacing(15)

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
        self.current_tab = 0  # 0=chats, 1=groups
        self.groups_cache = []
        self.refresh_timer = None

        # Initialize signal emitter in main thread
        self.signal_emitter = SignalEmitter()
        self.signal_emitter.update_gui.connect(self._handle_gui_update)

        self._setup_ui()
        self._show_login()

    def _setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle("Chat Application")
        self.setGeometry(100, 100, 1100, 700)

        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QPushButton {
                background-color: #0084ff; color: white; border: none;
                padding: 8px 16px; border-radius: 4px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0073e6; }
            QPushButton:pressed { background-color: #0062cc; }
            QLineEdit { 
                padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px;
                background-color: white;
            }
            QListWidget {
                border: 1px solid #ddd; border-radius: 4px;
                background-color: white; font-size: 13px;
            }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #f0f0f0; }
            QListWidget::item:selected { background-color: #e3f2fd; color: black; }
            QListWidget::item:hover { background-color: #f5f5f5; }
            QTextEdit {
                border: 1px solid #ddd; border-radius: 4px;
                background-color: white; padding: 10px;
            }
            QLabel { font-size: 13px; }
            QTabWidget::pane { border: 1px solid #ddd; border-radius: 4px; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # ============ Left Sidebar ============
        sidebar = QWidget()
        sidebar.setMaximumWidth(300)
        sidebar.setMinimumWidth(250)
        sidebar_layout = QVBoxLayout()
        sidebar.setLayout(sidebar_layout)

        # Header
        header = QLabel("Messages")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("padding: 10px; color: #333;")
        sidebar_layout.addWidget(header)

        # Tab widget for Chats and Groups
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # ===== Chats Tab =====
        chats_tab = QWidget()
        chats_layout = QVBoxLayout()
        chats_tab.setLayout(chats_layout)

        btn_online = QPushButton("🌐 Show Online Users")
        btn_online.clicked.connect(self._show_online_users)
        chats_layout.addWidget(btn_online)

        self.chat_list = QListWidget()
        self.chat_list.itemClicked.connect(self._on_chat_select)
        chats_layout.addWidget(self.chat_list)

        self.tab_widget.addTab(chats_tab, "💬 Chats")

        # ===== Groups Tab =====
        groups_tab = QWidget()
        groups_layout = QVBoxLayout()
        groups_tab.setLayout(groups_layout)

        btn_new_group = QPushButton("➕ Create New Group")
        btn_new_group.clicked.connect(self._create_group)
        groups_layout.addWidget(btn_new_group)

        self.group_list = QListWidget()
        self.group_list.itemClicked.connect(self._on_group_select)
        groups_layout.addWidget(self.group_list)

        self.tab_widget.addTab(groups_tab, "👥 Groups")

        sidebar_layout.addWidget(self.tab_widget)

        # Refresh button
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self._refresh_all)
        sidebar_layout.addWidget(btn_refresh)

        # ============ Right Side - Chat Area ============
        chat_widget = QWidget()
        chat_layout = QVBoxLayout()
        chat_widget.setLayout(chat_layout)

        # Chat header with menu button
        header_container = QWidget()
        header_layout = QHBoxLayout()
        header_container.setLayout(header_layout)
        header_container.setStyleSheet("background-color: #0084ff; padding: 10px; border-radius: 4px;")

        self.chat_header = QLabel("Select a chat to start")
        self.chat_header.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.chat_header.setStyleSheet("color: white;")
        header_layout.addWidget(self.chat_header)

        header_layout.addStretch()

        # Three-dot menu button
        self.menu_btn = QToolButton()
        self.menu_btn.setText("⋮")
        self.menu_btn.setFont(QFont("Segoe UI", 16))
        self.menu_btn.setStyleSheet("""
            QToolButton {
                background: transparent; color: white; border: none; 
                padding: 0 5px; font-weight: bold;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.2); 
                border-radius: 4px;
            }
        """)
        self.menu_btn.clicked.connect(self._show_context_menu)
        header_layout.addWidget(self.menu_btn)

        chat_layout.addWidget(header_container)

        # Messages display area
        self.messages_area = QTextEdit()
        self.messages_area.setReadOnly(True)
        self.messages_area.setFont(QFont("Segoe UI", 11))
        chat_layout.addWidget(self.messages_area)

        # Input area
        input_container = QWidget()
        input_layout = QHBoxLayout()
        input_container.setLayout(input_layout)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.message_input)

        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._send_message)
        send_btn.setMinimumWidth(100)
        input_layout.addWidget(send_btn)

        chat_layout.addWidget(input_container)

        # Splitter for resizable layout
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(sidebar)
        splitter.addWidget(chat_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+R"), self, self._refresh_all)
        QShortcut(QKeySequence("Ctrl+N"), self, self._create_group)

    def _show_context_menu(self):
        """Show context menu with available actions"""
        if not self.current_chat:
            return

        menu = QMenu(self)
        menu.addAction("🗑️ Delete Message", self._delete_message)
        menu.addAction("🧹 Clear History", self._clear_history)

        # Group-specific actions
        if self.current_tab == 1:  # Groups tab
            menu.addSeparator()
            menu.addAction("➕ Add Member", self._add_member_to_group)
            menu.addAction("➖ Remove Member", self._remove_member_from_group)
            menu.addAction("❌ Delete Group", self._delete_current_group)

        menu.exec_(self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft()))

    # ============ Connection & Login ============

    def _show_login(self):
        """Show login dialog"""
        dialog = LoginDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            username, timezone = dialog.get_credentials()
            if username:
                self._connect(username, timezone)
            else:
                QMessageBox.warning(self, "Error", "Username is required")
                self._show_login()
        else:
            sys.exit()

    def _connect(self, username, timezone):
        try:
            print(f"[GUI] Connecting as {username}...")
            self.client = ChatClient()

            # Override message handler to emit signals to GUI thread
            def gui_message_handler(obj):
                self.signal_emitter.update_gui.emit(obj)

            self.client.message_handler.handle = gui_message_handler
            self.client.connect()
            print(f"[GUI] Connected to server")

            self.client.register(username, timezone)
            print(f"[GUI] Registered as {username}")

            # Start receiver thread
            receiver_thread = threading.Thread(target=self.client._receive_messages, daemon=True)
            receiver_thread.start()
            print(f"[GUI] Receiver thread started")

            self.setWindowTitle(f"Chat - {username}")
            self.status_bar.showMessage(f"✓ Connected as {username}")

            # Load unread counts from database
            QTimer.singleShot(500, self._load_unread_counts)

            # Initial data load
            QTimer.singleShot(1000, self._initial_refresh)

            # Set up periodic refresh (every 5 seconds)
            self._start_periodic_refresh()

        except Exception as e:
            print(f"[GUI] Connection error: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Connection Error", f"Failed to connect: {e}")
            self._show_login()

    def _load_unread_counts(self):
        """Request unread counts from server on startup"""
        if self.client and self.client.running:
            try:
                self.client._send({"type": "get_unread_counts"})
            except:
                pass

    def _initial_refresh(self):
        """Initial data load after connection"""
        self._refresh_chats()
        self._refresh_groups()

    def _start_periodic_refresh(self):
        """Use QTimer for thread-safe periodic refresh"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._auto_refresh)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds

    def _auto_refresh(self):
        """Auto-refresh callback (runs in GUI thread)"""
        if self.client and self.client.running:
            self._refresh_chats()
            self._refresh_groups()

    # ============ Message Handlers ============

    def _handle_gui_update(self, obj):
        """Handle all incoming messages from server (runs in GUI thread)"""
        msg_type = obj.get('type')

        try:
            if msg_type == 'message':
                self._handle_new_message(obj)
            elif msg_type == 'chatlist':
                self._update_chat_list(obj.get('users', []))
            elif msg_type == 'groups_list':
                self._update_groups_list(obj.get('groups', []))
            elif msg_type == 'message_history':
                self._display_history(obj)
            elif msg_type == 'unread_counts':
                # Load unread counts from server
                with self.client.lock:
                    self.client.unread_counts = obj.get('counts', {})
                self._update_unread_indicators()
            elif msg_type == 'group_created':
                group_name = obj.get('group_name', 'Unknown')
                self.status_bar.showMessage(f"✓ Group '{group_name}' created!", 3000)
                QTimer.singleShot(500, self._refresh_groups)
            elif msg_type == 'group_deleted':
                group = obj.get('group_name', '')
                with self.client.lock:
                    if group in self.groups_cache:
                        self.groups_cache.remove(group)
                    if group in self.client.unread_counts:
                        del self.client.unread_counts[group]

                if self.current_chat == group:
                    self.current_chat = None
                    self.chat_header.setText("Select a chat to start")
                    self.messages_area.clear()

                self.status_bar.showMessage(f"✓ Group '{group}' deleted", 3000)
                QTimer.singleShot(300, self._refresh_groups)
            elif msg_type == 'group_modified':
                action = obj.get('action', '')
                member = obj.get('member', '')
                group = obj.get('group_name', '')

                action_msg = {
                    'add': f"✓ Added {member} to {group}",
                    'remove': f"✓ Removed {member} from {group}",
                }.get(action, f"Modified: {action}")

                self.status_bar.showMessage(action_msg, 3000)
                QTimer.singleShot(500, self._refresh_groups)
            elif msg_type == 'history_cleared':
                self.messages_area.clear()
                self.messages_area.append("✓ History cleared\n")
                self.status_bar.showMessage("✓ History cleared", 2000)
            elif msg_type == 'delete':
                self._handle_message_delete(obj)
            elif msg_type == 'online':
                # Store online users in client
                with self.client.lock:
                    self.client.online_users = [
                        {"alias": u, "timezone": t}
                        for u, t in zip(obj.get("users", []), obj.get("timezones", []))
                    ]
            elif msg_type == 'error':
                error_msg = obj.get('what', 'Unknown error')
                details = obj.get('details', '')
                full_msg = f"{error_msg}: {details}" if details else error_msg
                self.status_bar.showMessage(f"❌ {full_msg}", 5000)
                QMessageBox.warning(self, "Error", full_msg)
        except Exception as e:
            print(f"GUI update error: {e}")
            import traceback
            traceback.print_exc()

    def _handle_new_message(self, msg):
        """Handle incoming message in real-time"""
        sender = msg.get('from')
        to = msg.get('to')
        is_group = msg.get('group', False)

        # Determine which chat this message belongs to
        if is_group:
            chat_key = to  # Group name
        else:
            # For private messages, use the other person's name
            chat_key = sender if sender != self.client.alias else to

        # Update unread count if not currently viewing this chat
        if sender != self.client.alias and self.current_chat != chat_key:
            with self.client.lock:
                self.client.unread_counts[chat_key] = self.client.unread_counts.get(chat_key, 0) + 1

            self._update_unread_indicators()

            # Play notification sound
            try:
                Hints.play_notification()
            except:
                pass

        # Display message if currently viewing this chat
        if self.current_chat and self.current_chat == chat_key:
            self._display_single_message(msg)

    def _handle_message_delete(self, obj):
        """Handle message deletion notification"""
        msg_id = obj.get('id')
        deleted_by = obj.get('deleted_by', 'unknown')

        self.status_bar.showMessage(f"✓ Message {msg_id} deleted by {deleted_by}", 3000)

        # Reload history if currently viewing the affected chat
        if self.current_chat:
            payload = {"type": "message_history", "with_user": self.current_chat, "limit": 50}
            self.client._send(payload)

    # ============ Display Methods ============

    def _display_single_message(self, msg):
        """Display a single message in the chat area"""
        sender = msg.get('from', 'Unknown')
        text = msg.get('text', '')
        ts = msg.get('ts', 0)
        deleted = msg.get('deleted', False)
        msg_id = msg.get('id', '')
        is_group = msg.get('group', False)

        import html
        text_escaped = html.escape(text)
        sender_escaped = html.escape(sender)

        timestamp = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
        cursor = self.messages_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        if deleted:
            cursor.insertHtml(
                f'<p style="color: #999; font-style: italic; margin: 5px;">'
                f'[{timestamp}] 🗑️ Message {msg_id} was deleted</p>'
            )
        elif sender == self.client.alias:
            # Own messages - right aligned, blue
            cursor.insertHtml(
                f'<div style="text-align: right; margin: 8px 5px;">'
                f'<span style="background-color: #0084ff; color: white; padding: 10px 14px; '
                f'border-radius: 18px; display: inline-block; max-width: 65%; word-wrap: break-word;">'
                f'{text_escaped}</span><br>'
                f'<small style="color: #999; font-size: 10px;">ID: {msg_id} • {timestamp}</small>'
                f'</div>'
            )
        else:
            # Others' messages - left aligned, gray
            sender_display = f'<strong style="color: #0084ff; font-size: 11px;">{sender_escaped}</strong><br>' if is_group else ''
            cursor.insertHtml(
                f'<div style="margin: 8px 5px;">'
                f'{sender_display}'
                f'<span style="background-color: #e4e6eb; color: #000; padding: 10px 14px; '
                f'border-radius: 18px; display: inline-block; max-width: 65%; word-wrap: break-word;">'
                f'{text_escaped}</span><br>'
                f'<small style="color: #999; font-size: 10px;">ID: {msg_id} • {timestamp}</small>'
                f'</div>'
            )

        self.messages_area.setTextCursor(cursor)
        self.messages_area.ensureCursorVisible()

    def _display_history(self, obj):
        """Display message history"""
        messages = obj.get('messages', [])
        was_cleared = obj.get('cleared', False)
        with_user = obj.get('with_user', self.current_chat)

        self.messages_area.clear()
        self.status_bar.showMessage("✓ Loaded", 1000)

        if was_cleared:
            self.messages_area.append("ℹ️ History was cleared previously\n")

        if not messages:
            self.messages_area.append(f"No messages yet. Start chatting with {with_user}!")
        else:
            for msg in messages:
                self._display_single_message(msg)

    def _check_loading_timeout(self, chat_name):
        """Check if still loading after timeout"""
        if self.current_chat == chat_name and "Loading" in self.messages_area.toPlainText():
            self.messages_area.clear()
            self.messages_area.append(
                f"⚠️ Failed to load messages.\n\n"
                f"Possible reasons:\n"
                f"• Server not responding\n"
                f"• Network issue\n"
                f"• Connection lost\n\n"
                f"Try clicking 🔄 Refresh or reconnecting."
            )
            self.status_bar.showMessage("❌ Loading timeout", 3000)

    # ============ Chat List Updates ============

    def _update_chat_list(self, users):
        """Update the chat list with unread indicators"""
        current_selection = self.current_chat if self.current_tab == 0 else None
        self.chat_list.clear()

        # Filter out self and groups
        chats = [u for u in users if u != self.client.alias and u not in self.groups_cache]

        with self.client.lock:
            unread_counts = self.client.unread_counts.copy()

        for user in chats:
            unread = unread_counts.get(user, 0)

            if unread > 0:
                item = QListWidgetItem(f"{user} 🔴 ({unread})")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item = QListWidgetItem(user)

            self.chat_list.addItem(item)

            # Re-select if this was the current chat
            if user == current_selection:
                self.chat_list.setCurrentItem(item)

    def _update_groups_list(self, groups):
        """Update the groups list with unread indicators"""
        current_selection = self.current_chat if self.current_tab == 1 else None
        self.group_list.clear()
        self.groups_cache = groups

        with self.client.lock:
            unread_counts = self.client.unread_counts.copy()

        for group in groups:
            unread = unread_counts.get(group, 0)

            if unread > 0:
                item = QListWidgetItem(f"{group} 🔴 ({unread})")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item = QListWidgetItem(group)

            self.group_list.addItem(item)

            # Re-select if this was the current group
            if group == current_selection:
                self.group_list.setCurrentItem(item)

    def _update_unread_indicators(self):
        """Update window title and lists with unread counts"""
        with self.client.lock:
            total_unread = sum(self.client.unread_counts.values())

        if total_unread > 0:
            self.setWindowTitle(f"Chat - {self.client.alias} ({total_unread} unread)")
        else:
            self.setWindowTitle(f"Chat - {self.client.alias}")

        # Refresh lists to show updated unread counts
        self._refresh_chats()
        self._refresh_groups()

    # ============ Chat Selection ============

    def _on_chat_select(self, item):
        """Handle chat selection"""
        chat_text = item.text()

        # Extract chat name (remove unread indicator if present)
        if ' 🔴 ' in chat_text:
            self.current_chat = chat_text.split(' 🔴 ')[0].strip()
        elif ' (' in chat_text:
            self.current_chat = chat_text.split(' (')[0].strip()
        else:
            self.current_chat = chat_text.strip()

        self.current_tab = 0
        self.chat_header.setText(f"💬 {self.current_chat}")

        # Reset unread count for this chat
        with self.client.lock:
            if self.current_chat in self.client.unread_counts:
                self.client.unread_counts[self.current_chat] = 0

        self._update_unread_indicators()

        # Load message history
        self.messages_area.clear()
        self.messages_area.append("⏳ Loading messages...")
        self.status_bar.showMessage("Loading messages...")

        payload = {"type": "message_history", "with_user": self.current_chat, "limit": 50}
        self.client._send(payload)

    def _on_group_select(self, item):
        """Handle group selection"""
        group_text = item.text()

        # Extract group name (remove unread indicator if present)
        if ' 🔴 ' in group_text:
            self.current_chat = group_text.split(' 🔴 ')[0].strip()
        elif ' (' in group_text:
            self.current_chat = group_text.split(' (')[0].strip()
        else:
            self.current_chat = group_text.strip()

        self.current_tab = 1
        self.chat_header.setText(f"👥 {self.current_chat}")

        # Reset unread count for this group
        with self.client.lock:
            if self.current_chat in self.client.unread_counts:
                self.client.unread_counts[self.current_chat] = 0

        self._update_unread_indicators()

        # Load group message history
        self.messages_area.clear()
        self.messages_area.append("⏳ Loading group messages...")
        self.status_bar.showMessage("Loading messages...")

        payload = {"type": "message_history", "with_user": self.current_chat, "limit": 50}
        self.client._send(payload)

    def _on_tab_changed(self, index):
        """Handle tab change between Chats and Groups"""
        self.current_tab = index
        # Clear current selection when switching tabs
        if hasattr(self, 'group_list') and hasattr(self, 'chat_list'):
            if index == 0:
                self.group_list.clearSelection()
            else:
                self.chat_list.clearSelection()

    # ============ Sending Messages ============

    def _send_message(self):
        """Send a message to current chat"""
        if not self.current_chat or not self.client:
            self.status_bar.showMessage("❌ Select a chat first", 2000)
            return

        text = self.message_input.text().strip()
        if not text:
            return

        # Determine if current chat is a group
        is_group = self.current_chat in self.groups_cache

        payload = {
            "type": "chat",
            "text": text,
            "to": self.current_chat,
            "group": is_group
        }

        try:
            self.client._send(payload)
            self.message_input.clear()
            self.status_bar.showMessage("✓ Sent", 1000)
        except Exception as e:
            self.status_bar.showMessage(f"❌ Failed: {e}", 3000)
            QMessageBox.critical(self, "Send Error", f"Failed to send message: {e}")

    # ============ Message Operations ============

    def _delete_message(self):
        """Delete a message by ID"""
        if not self.current_chat:
            QMessageBox.warning(self, "No Chat", "Please select a chat first")
            return

        msg_id, ok = QInputDialog.getText(
            self, "Delete Message",
            "Enter the message ID to delete:\n(You can only delete your own messages)"
        )

        if ok and msg_id.strip():
            try:
                self.client._send({"type": "delete_request", "id": msg_id.strip()})
                self.status_bar.showMessage(f"Deleting message {msg_id}...", 2000)
            except Exception as e:
                self.status_bar.showMessage(f"❌ Failed: {e}", 3000)
                QMessageBox.critical(self, "Error", f"Failed to delete message: {e}")

    def _clear_history(self):
        """Clear chat history for current chat"""
        if not self.current_chat:
            QMessageBox.warning(self, "No Chat", "Please select a chat first")
            return

        reply = QMessageBox.question(
            self, "Clear History",
            f"Clear your chat history with '{self.current_chat}'?\n\n"
            f"Note: This only clears history from your view.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            payload = {"type": "clear_history", "with_user": self.current_chat}
            self.client._send(payload)
            self.status_bar.showMessage("Clearing history...", 2000)

    # ============ Group Management ============

    def _create_group(self):
        """Create a new group"""
        group_name, ok = QInputDialog.getText(
            self, "Create New Group",
            "Enter group name:"
        )

        if not ok or not group_name.strip():
            return

        group_name = group_name.strip()

        members_str, ok = QInputDialog.getText(
            self, "Add Members",
            f"Add members to '{group_name}':\n"
            f"(Enter comma-separated usernames)\n"
            f"Leave blank to create an empty group"
        )

        if not ok:
            return

        members = [m.strip() for m in members_str.split(',') if m.strip()]

        payload = {
            'type': 'create_group',
            'group_name': group_name,
            'members': members
        }

        try:
            self.client._send(payload)
            self.status_bar.showMessage(f"Creating group '{group_name}'...", 2000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create group: {e}")

    def _add_member_to_group(self):
        """Add a member to the current group"""
        if not self.current_chat or self.current_tab != 1:
            QMessageBox.warning(self, "Error", "Please select a group first")
            return

        # Request online users first
        self.client._send({"type": "online"})
        self.status_bar.showMessage("Fetching online users...", 1000)

        # Wait for response then show dialog
        QTimer.singleShot(400, self._show_add_member_dialog)

    def _show_add_member_dialog(self):
        """Show dialog to select user to add"""
        with self.client.lock:
            online_users = [u['alias'] for u in self.client.online_users
                           if u['alias'] != self.client.alias]

        if not online_users:
            QMessageBox.warning(self, "No Users", "No online users available to add")
            return

        member, ok = QInputDialog.getItem(
            self, "Add Member to Group",
            f"Select user to add to '{self.current_chat}':",
            online_users,
            0,
            False
        )

        if ok and member:
            payload = {
                'type': 'modify_group',
                'group_name': self.current_chat,
                'action': 'add',
                'member': member
            }
            self.client._send(payload)
            self.status_bar.showMessage(f"Adding {member} to {self.current_chat}...", 2000)

    def _remove_member_from_group(self):
        """Remove a member from the current group"""
        if not self.current_chat or self.current_tab != 1:
            QMessageBox.warning(self, "Error", "Please select a group first")
            return

        member, ok = QInputDialog.getText(
            self, "Remove Member",
            f"Enter username to remove from '{self.current_chat}':"
        )

        if ok and member.strip():
            member = member.strip()
            payload = {
                'type': 'modify_group',
                'group_name': self.current_chat,
                'action': 'remove',
                'member': member
            }
            self.client._send(payload)
            self.status_bar.showMessage(f"Removing {member} from {self.current_chat}...", 2000)

    def _delete_current_group(self):
        """Delete the current group (creator only)"""
        if not self.current_chat or self.current_tab != 1:
            QMessageBox.warning(self, "Error", "Please select a group first")
            return

        reply = QMessageBox.question(
            self, "Delete Group",
            f"Are you sure you want to delete group '{self.current_chat}'?\n\n"
            f"This will remove the group for all members and delete all messages.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            payload = {
                'type': 'modify_group',
                'group_name': self.current_chat,
                'action': 'delete_group',
                'member': ''
            }
            self.client._send(payload)
            self.status_bar.showMessage(f"Deleting group '{self.current_chat}'...", 2000)

    # ============ Refresh Methods ============

    def _refresh_all(self):
        """Manually trigger refresh"""
        self._refresh_chats()
        self._refresh_groups()
        self.status_bar.showMessage("✓ Refreshed", 2000)

    def _refresh_chats(self):
        """Request updated chat list from server"""
        if self.client and self.client.running:
            try:
                self.client._send({"type": "chatlist"})
            except:
                pass

    def _refresh_groups(self):
        """Request updated groups list from server"""
        if self.client and self.client.running:
            try:
                self.client._send({"type": "list_groups"})
            except:
                pass

    def _show_online_users(self):
        """Show list of online users"""
        if not self.client:
            return

        self.client._send({"type": "online"})
        self.status_bar.showMessage("Fetching online users...", 1000)

        # Wait for response then show
        QTimer.singleShot(300, self._display_online_users)

    def _display_online_users(self):
        """Display online users dialog"""
        with self.client.lock:
            users = self.client.online_users.copy()

        if not users:
            QMessageBox.information(self, "Online Users", "No users currently online")
            return

        online_list = "\n".join([f"🟢 {u['alias']} ({u['timezone']})" for u in users])
        QMessageBox.information(self, f"Online Users ({len(users)})", online_list)

    # ============ Cleanup ============

    def closeEvent(self, event):
        """Clean up on window close"""
        if self.refresh_timer:
            self.refresh_timer.stop()

        if self.client:
            try:
                self.client._send({"type": "disconnect"})
                self.client.running = False
            except:
                pass

        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = ChatGUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

