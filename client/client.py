import socket
import threading
import json
import sys
import time
from typing import List, Dict, Optional
from .hints import Hints
from .messageHandler import MessageHandler


class ChatClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 59394):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.alias: str = ""
        self.timezone: str = "UTC+06:00"

        self.online_users: List[Dict] = []
        self.chat_history: List[Dict] = []
        self.chatlist: List[str] = []
        self.unread_counts: Dict[str, int] = {}

        self.running = True
        self.lock = threading.Lock()

        self.hints = Hints()
        self.message_handler = MessageHandler(self)

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.host, self.port))
        except Exception as e:
            print(f"Could not connect to server at {self.host}:{self.port} ({e})")
            sys.exit(1)

    def register(self, alias: str, timezone: str):
        self.alias = alias
        self.timezone = timezone
        msg = json.dumps({"type": "register", "user": alias, "timezone": timezone}) + "\n"
        self.socket.send(msg.encode())

    def start(self):
        receiver_thread = threading.Thread(target=self._receive_messages, daemon=True)
        receiver_thread.start()
        self._command_loop()

    def _receive_messages(self):
        buffer = b""
        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    print("Disconnected from server.")
                    self.running = False
                    break

                buffer += data
                parts = buffer.split(b'\n')
                buffer = parts.pop()

                for msg in parts:
                    if not msg.strip():
                        continue
                    try:
                        obj = json.loads(msg.decode())
                        self.message_handler.handle(obj)
                    except Exception:
                        continue

            except Exception as e:
                print(f"Error: {e}")
                self.running = False
                break

    def _command_loop(self):
        self.hints.print_help()

        try:
            while self.running:
                cmd = input("\n[send|create_group|add|remove|groups|delete|chats|history|clear|online|quit]> ").strip()

                if cmd == "quit":
                    self._disconnect()
                    break
                elif cmd == "online":
                    self._show_online()
                elif cmd == "chats":
                    self._request_chatlist()
                elif cmd == "create_group":
                    self._create_group()
                elif cmd == "add":
                    self._modify_group("add")
                elif cmd == "remove":
                    self._modify_group("remove")
                elif cmd == "groups":
                    self._list_groups()
                elif cmd == "send":
                    self._send_message()
                elif cmd == "delete":
                    self._delete_message()
                elif cmd == "history":
                    self._view_history()
                elif cmd == "clear":
                    self._clear_history()
                else:
                    print("Unknown command.")

        except KeyboardInterrupt:
            self._disconnect()

    def _send_message(self):
        to = input("To (leave blank to send to all, or type 'group' to send to a group): ").strip()
        msg = input("Message: ")

        payload = {"type": "chat", "text": msg}

        if not to:
            payload["broadcast"] = True
        elif to.lower() == "group":
            group_name = input("Group name: ").strip()
            if not group_name:
                print("Group name required.")
                return
            payload["group"] = group_name
            payload["to"] = group_name
        else:
            payload["to"] = to
            payload["group"] = False

        self._send(payload)

    def _create_group(self):
        group_name = input("Group name: ").strip()
        members_str = input("Members (comma separated, exclude yourself): ").strip()
        members = [m.strip() for m in members_str.split(',') if m.strip()]

        payload = {'type': 'create_group', 'group_name': group_name, 'members': members}
        self._send(payload)
        time.sleep(0.1)

    def _modify_group(self, action: str):
        group_name = input("Group name: ").strip()
        member = input(f"Member to {action}: ").strip()

        payload = {'type': 'modify_group', 'group_name': group_name, 'action': action, 'member': member}
        self._send(payload)
        time.sleep(0.1)

    def _list_groups(self):
        self._send({"type": "list_groups"})
        time.sleep(0.1)

    def _delete_message(self):
        msg_id = input("Message ID to delete: ").strip()
        self._send({"type": "delete_request", "id": msg_id})

    def _view_history(self):
        with_user = input("View history with (username or group): ").strip()
        if not with_user:
            print("Please specify a username or group")
            return

        limit_input = input("Number of messages to fetch (default 50): ").strip()
        limit = int(limit_input) if limit_input.isdigit() else 50

        payload = {"type": "message_history", "with_user": with_user, "limit": limit}
        self._send(payload)

        with self.lock:
            if with_user == self.unread_counts:
                self.unread_counts[with_user] = 0
        time.sleep(0.2)

    def _clear_history(self):
        with_user = input("Clear history with (username or group): ").strip()
        if not with_user:
            print("Please specify a username or group")
            return

        confirm = input(f"Are you sure you want to clear history with '{with_user}'? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Clear operation cancelled.")
            return

        payload = {"type": "clear_history", "with_user": with_user}
        self._send(payload)
        time.sleep(0.1)

    def _request_chatlist(self):
        self._send({"type": "chatlist"})
        time.sleep(0.1)
        with self.lock:
            if not self.chatlist:
                print("No active chats.")
            else:
                print("\n=== Your chats ===")
                for chat in self.chatlist:
                    unread = self.unread_counts.get(chat, 0)
                    if unread > 0:
                        print(f"  {chat} ({unread} unread messages)")
                    else:
                        print(f"  {chat}")
                        print("-----------------\n")


    def _show_online(self):
        with self.lock:
            self.hints.print_online(self.online_users)

    def _disconnect(self):
        try:
            self._send({"type": "disconnect"})
        except:
            pass
        self.running = False
        if self.socket:
            self.socket.close()

    def _send(self, payload: dict):
        msg = json.dumps(payload) + "\n"
        self.socket.send(msg.encode())
