
import threading
import socket
from typing import Dict, List, Optional
from .database import Database
from .models import User, Group
from .handler import ClientHandler
import json


class ChatServer:
    def __init__(self, host: str = '127.0.0.1', port: int = 59394):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.db = Database()

        self.users: Dict[str, User] = {}
        self.groups: Dict[str, Group] = {}
        self.clients: List[socket.socket] = []

        self.next_msg_id = 1
        self.msg_id_lock = threading.Lock()

    def start(self):
        self.server.bind((self.host, self.port))
        self.server.listen()
        print(f'Server started on {self.host}:{self.port}')
        self._accept_connections()

    def _accept_connections(self):
        while True:
            print('Server is running and listening ...')
            client, address = self.server.accept()
            self.clients.append(client)
            thread = threading.Thread(target=self._handle_client, args=(client,))
            thread.start()

    def get_next_msg_id(self) -> str:
        with self.msg_id_lock:
            msg_id = str(self.next_msg_id)
            self.next_msg_id += 1
        return msg_id

    def broadcast(self, message: str, targets: Optional[List[User]] = None):
        if targets is None:
            targets = list(self.users.values())

        for user in targets:
            user.send(message)

    def broadcast_online_status(self):
        """Broadcast current online users to all clients"""
        usernames = list(self.users.keys())
        timezones = [u.timezone for u in self.users.values()]
        msg = json.dumps({'type': 'online', 'users': usernames, 'timezones': timezones})
        self.broadcast(msg)

    def _handle_client(self, client: socket.socket):
        handler = ClientHandler(self, client)
        handler.handle()

    def register_user(self, username: str, client: socket.socket, timezone: str) -> Optional[User]:
        if username in self.users:
            return None
        user = User(username, client, timezone)
        self.users[username] = user
        self.broadcast_online_status()
        return user

    def unregister_user(self, username: str):
        if username in self.users:
            del self.users[username]
            self.broadcast_online_status()

    def create_group(self, group_name: str, creator: str, members: List[str]) -> Optional[Group]:
        if group_name in self.groups:
            return None

        group = Group(group_name, creator, members)
        self.groups[group_name] = group

        for member in group.members:
            if member in self.users:
                self.users[member].groups.append(group_name)

        return group

    def get_group(self, group_name: str) -> Optional[Group]:
        return self.groups.get(group_name)

    def delete_group(self, group_name: str) -> bool:
        if group_name in self.groups:
            del self.groups[group_name]
            self.db.delete_group_messages(group_name)
            return True
        return False

    def shutdown(self):
        print("Shutting down server...")
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        self.server.close()
        self.db.close()
