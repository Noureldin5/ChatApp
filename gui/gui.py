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
        self.setWindowTitle("Chat Login")
        self.setModal(True)
        self.resize(400, 280)

        main_layout = QVBoxLayout()

        # Tab widget for login/signup
        self.tabs = QTabWidget()

        # Login tab
        login_tab = QWidget()
        login_layout = QFormLayout()
        login_layout.setSpacing(15)

        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("Enter your username")
        login_layout.addRow("Username:", self.login_username)

        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Enter your password")
        self.login_password.setEchoMode(QLineEdit.Password)
        login_layout.addRow("Password:", self.login_password)

        login_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        login_buttons.accepted.connect(self._do_login)
        login_buttons.rejected.connect(self.reject)
        login_layout.addRow(login_buttons)

        login_tab.setLayout(login_layout)

        # Signup tab
        signup_tab = QWidget()
        signup_layout = QFormLayout()
        signup_layout.setSpacing(15)

        self.signup_username = QLineEdit()
        self.signup_username.setPlaceholderText("Choose a username")
        signup_layout.addRow("Username:", self.signup_username)

        self.signup_password = QLineEdit()
        self.signup_password.setPlaceholderText("Choose a password (min 6 chars)")
        self.signup_password.setEchoMode(QLineEdit.Password)
        signup_layout.addRow("Password:", self.signup_password)

        self.signup_confirm = QLineEdit()
        self.signup_confirm.setPlaceholderText("Confirm password")
        self.signup_confirm.setEchoMode(QLineEdit.Password)
        signup_layout.addRow("Confirm:", self.signup_confirm)

        self.signup_timezone = QLineEdit("UTC+06:00")
        self.signup_timezone.setPlaceholderText("e.g., UTC+06:00")
        signup_layout.addRow("Timezone:", self.signup_timezone)

        signup_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        signup_buttons.accepted.connect(self._do_signup)
        signup_buttons.rejected.connect(self.reject)
        signup_layout.addRow(signup_buttons)

        signup_tab.setLayout(signup_layout)

        # Add tabs
        self.tabs.addTab(login_tab, "Login")
        self.tabs.addTab(signup_tab, "Sign Up")

        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

        self.auth_mode = None  # 'login' or 'signup'
        self.username = None
        self.password = None
        self.timezone = "UTC+06:00"

    def _do_login(self):
        """Handle login button click"""
        username = self.login_username.text().strip()
        password = self.login_password.text()

        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter both username and password")
            return

        self.auth_mode = 'login'
        self.username = username
        self.password = password
        self.accept()

    def _do_signup(self):
        """Handle signup button click"""
        username = self.signup_username.text().strip()
        password = self.signup_password.text()
        confirm = self.signup_confirm.text()
        timezone = self.signup_timezone.text().strip() or "UTC+06:00"

        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter username and password")
            return

        if len(password) < 6:
            QMessageBox.warning(self, "Error", "Password must be at least 6 characters")
            return

        if password != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match")
            return

        self.auth_mode = 'signup'
        self.username = username
        self.password = password
        self.timezone = timezone
        self.accept()

    def get_credentials(self):
        return self.auth_mode, self.username, self.password, self.timezone


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
            auth_mode, username, password, timezone = dialog.get_credentials()
            if username and password:
                self._connect(auth_mode, username, password, timezone)
            else:
                QMessageBox.warning(self, "Error", "Username and password are required")
                self._show_login()
        else:
            sys.exit()

    def _connect(self, auth_mode, username, password, timezone):
        try:
            print(f"[GUI] Connecting as {username}...")
            self.client = ChatClient()
            self.client.connect()
            print(f"[GUI] Connected to server")

            # Store credentials for potential re-auth
            self._username = username
            self._auth_mode = auth_mode
            self._timezone = timezone

            # Override message handler to emit signals to GUI thread
            original_handler = self.client.message_handler.handle

            def gui_message_handler(obj):
                try:
                    original_handler(obj)
                except Exception as e:
                    print(f"[GUI] Original handler error: {e}")

                self.signal_emitter.update_gui.emit(obj)

            self.client.message_handler.handle = gui_message_handler

            # Start receiver thread
            receiver_thread = threading.Thread(target=self.client._receive_messages, daemon=True)
            receiver_thread.start()
            print(f"[GUI] Receiver thread started")

            # Send login or signup request
            if auth_mode == 'login':
                self.client.login(username, password)
                print(f"[GUI] Sent login request for {username}")
            elif auth_mode == 'signup':
                self.client.signup(username, password, timezone)
                print(f"[GUI] Sent signup request for {username}")

            # Wait a bit for auth response before setting up UI
            QTimer.singleShot(500, lambda: self._finalize_connection(username))

        except Exception as e:
            print(f"[GUI] Connection error: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Connection Error", f"Failed to connect: {e}")
            self._show_login()

    def _finalize_connection(self, username):
        """Finalize connection after successful authentication"""
        if self.client and self.client.running and self.client.alias:
            self.setWindowTitle(f"Chat - {self.client.alias}")
            self.status_bar.showMessage(f"✓ Connected as {self.client.alias}")

            # Load initial data
            QTimer.singleShot(200, self._load_unread_counts)
            QTimer.singleShot(400, self._initial_refresh)

            # Set up periodic refresh (every 10 seconds)
            self._start_periodic_refresh()
        else:
            print("[GUI] Authentication may have failed, waiting...")

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
        self.refresh_timer.start(10000)  # Refresh every 10 seconds

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
            if msg_type == 'login_success':
                username = obj.get('username')
                print(f"[GUI] Login successful for {username}")
            elif msg_type == 'signup_success':
                username = obj.get('username')
                message = obj.get('message', 'Account created!')
                QMessageBox.information(self, "Success", f"{message}\nPlease login with your credentials.")
                # Disconnect and show login dialog again
                if self.client:
                    self.client.running = False
                self._show_login()
            elif msg_type == 'error':
                error_type = obj.get('what', 'unknown')
                details = obj.get('details', 'An error occurred')

                error_messages = {
                    'invalid_credentials': 'Invalid username or password',
                    'already_logged_in': 'User already connected from another session',
                    'username_taken': 'Username already exists',
                    'weak_password': 'Password must be at least 6 characters',
                    'invalid_input': 'Invalid input provided',
                    'signup_failed': 'Failed to create account',
                    'not_authenticated': 'Authentication required. Please login first.',
                    'registration_disabled': 'Direct registration disabled. Please use login or signup.'
                }

                error_msg = error_messages.get(error_type, details)

                # Only show message box for auth errors
                auth_errors = ['invalid_credentials', 'username_taken', 'weak_password',
                               'invalid_input', 'signup_failed', 'not_authenticated',
                               'registration_disabled', 'already_logged_in']

                if error_type in auth_errors:
                    QMessageBox.warning(self, "Error", error_msg)
                    if self.client:
                        self.client.running = False
                    self._show_login()
                else:
                    # For other errors, just show in status bar
                    self.status_bar.showMessage(f"❌ {error_msg}", 3000)

            elif msg_type == 'message':
                self._handle_new_message(obj)
            elif msg_type == 'chatlist':
                self._update_chat_list(obj.get('users', []))
            elif msg_type == 'groups_list':
                self._update_groups_list(obj.get('groups', []))
            elif msg_type == 'message_history':
                self._display_history(obj)
            elif msg_type == 'unread_counts':
                with self.client.lock:
                    self.client.unread_counts = obj.get('counts', {})
                self._update_unread_indicators()
            elif msg_type == 'group_created':
                group_name = obj.get('group_name', 'Unknown')
                self.status_bar.showMessage(f"✓ Group '{group_name}' created", 2000)
                QTimer.singleShot(200, self._refresh_groups)
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

                self.status_bar.showMessage(f"✓ Group '{group}' deleted", 2000)
                QTimer.singleShot(200, self._refresh_groups)
            elif msg_type == 'group_modified':
                action = obj.get('action', '')
                member = obj.get('member', '')
                group = obj.get('group_name', '')

                action_msg = {
                    'add': f"✓ Added {member} to {group}",
                    'remove': f"✓ Removed {member} from {group}",
                }.get(action, f"Modified: {action}")

                self.status_bar.showMessage(action_msg, 2000)
                QTimer.singleShot(200, self._refresh_groups)
            elif msg_type == 'history_cleared':
                if self.current_chat:
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
        except Exception as e:
            print(f"[GUI] Update error: {e}")
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

            # Refresh the appropriate list to show unread indicator
            if is_group:
                self._refresh_groups()
            else:
                self._refresh_chats()

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

        # Only update if viewing the same chat
        if with_user != self.current_chat:
            return

        self.messages_area.clear()

        if was_cleared:
            self.messages_area.append("ℹ️ History was cleared previously\n")

        if not messages:
            self.messages_area.append(f"No messages yet. Start chatting with {with_user}!")
        else:
            for msg in messages:
                self._display_single_message(msg)


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
        """Update window title with unread counts"""
        with self.client.lock:
            total_unread = sum(self.client.unread_counts.values())

        if total_unread > 0:
            self.setWindowTitle(f"Chat - {self.client.alias} ({total_unread} unread)")
        else:
            self.setWindowTitle(f"Chat - {self.client.alias}")


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

        # Update database
        try:
            self.client._send({"type": "mark_read", "with_user": self.current_chat})
        except:
            pass

        self._update_unread_indicators()

        # Load message history (no loading screen)
        self.messages_area.clear()

        payload = {"type": "message_history", "with_user": self.current_chat, "limit": 50}
        try:
            self.client._send(payload)
        except Exception as e:
            self.messages_area.clear()
            self.messages_area.append(f"❌ Failed to load messages: {e}")
            self.status_bar.showMessage(f"❌ Error: {e}", 3000)

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

        # Update database
        try:
            self.client._send({"type": "mark_read", "with_user": self.current_chat})
        except:
            pass

        self._update_unread_indicators()

        # Load group message history (no loading screen)
        self.messages_area.clear()

        payload = {"type": "message_history", "with_user": self.current_chat, "limit": 50}
        try:
            self.client._send(payload)
        except Exception as e:
            self.messages_area.clear()
            self.messages_area.append(f"❌ Failed to load messages: {e}")
            self.status_bar.showMessage(f"❌ Error: {e}", 3000)

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
        }

        if is_group:
            payload["group"] = self.current_chat
        else:
            payload["group"] = False

        try:
            self.client._send(payload)
            self.message_input.clear()
        except Exception as e:
            self.status_bar.showMessage(f"❌ Failed: {e}", 3000)

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
            except Exception as e:
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
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create group: {e}")

    def _add_member_to_group(self):
        """Add a member to the current group"""
        if not self.current_chat or self.current_tab != 1:
            QMessageBox.warning(self, "Error", "Please select a group first")
            return

        # Request online users first
        try:
            self.client._send({"type": "online"})
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to fetch online users: {e}")
            return

        # Wait for response then show dialog
        QTimer.singleShot(300, self._show_add_member_dialog)

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
            try:
                self.client._send(payload)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add member: {e}")

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
            try:
                self.client._send(payload)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove member: {e}")

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
            try:
                self.client._send(payload)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete group: {e}")

    # ============ Refresh Methods ============

    def _refresh_all(self):
        """Manually trigger refresh"""
        self._refresh_chats()
        self._refresh_groups()
        self.status_bar.showMessage("🔄 Refreshed", 1500)

    def _refresh_chats(self):
        """Request updated chat list from server"""
        if self.client and self.client.running:
            try:
                self.client._send({"type": "chatlist"})
            except Exception as e:
                print(f"[GUI] Failed to refresh chats: {e}")

    def _refresh_groups(self):
        """Request updated groups list from server"""
        if self.client and self.client.running:
            try:
                self.client._send({"type": "list_groups"})
            except Exception as e:
                print(f"[GUI] Failed to refresh groups: {e}")

    def _show_online_users(self):
        """Show list of online users"""
        if not self.client:
            return

        self.client._send({"type": "online"})

        # Wait for response then show
        QTimer.singleShot(200, self._display_online_users)

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

