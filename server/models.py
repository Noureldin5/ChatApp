
from typing import Set, List
import time
import socket


class User:

    def __init__(self, username: str, client_socket: socket.socket, timezone: str = 'UTC+06:00'):
        self.username = username
        self.socket = client_socket
        self.timezone = timezone
        self.groups: List[str] = []

    def send(self, message: str) -> bool:
        """Send a message to this user's socket"""
        try:
            if not message.endswith('\n'):
                message += '\n'
            self.socket.send(message.encode('utf-8'))
            return True
        except Exception:
            return False

    def __repr__(self):
        return f"User(username='{self.username}', timezone='{self.timezone}')"


class Group:

    def __init__(self, name: str, creator: str, members: List[str]):
        self.name = name
        self.creator = creator
        self.members: Set[str] = set(members + [creator])
        self.created_at = int(time.time())

    def add_member(self, member: str) -> bool:
        #Add a member to the group
        if member in self.members:
            return False
        self.members.add(member)
        return True

    def remove_member(self, member: str) -> bool:
        #Remove a member from the group
        if member not in self.members:
            return False
        self.members.discard(member)
        return True
    def delete_group(self):
        self.members.clear()
        return True

    def is_creator(self, user: str) -> bool:
        #Chect the creator of the group
        return user == self.creator

    def __repr__(self):
        return f"Group(name='{self.name}', creator='{self.creator}', members={len(self.members)})"
