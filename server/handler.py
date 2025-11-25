
import socket
import json
import time
from typing import Optional, Dict, Callable
from .models import User, Group


class ClientHandler:

    def __init__(self, server, client: socket.socket):
        from .server import ChatServer
        self.server: ChatServer = server
        self.client = client
        self.user: Optional[User] = None
        self.buffer = ""

    def handle(self):
        while True:
            try:
                raw = self.client.recv(4096)
                if not raw:
                    raise ConnectionError()

                self._process_data(raw.decode('utf-8'))
            except Exception:
                self._cleanup()
                return

    def _process_data(self, data: str):
        self.buffer += data
        parts = self.buffer.split('\n')
        self.buffer = parts.pop()

        for part in parts:
            if not part.strip():
                continue
            try:
                obj = json.loads(part)
                self._handle_message(obj)
            except Exception:
                continue

    def _handle_message(self, obj: dict):
        #Route message based on type
        msg_type = obj.get('type')

        handlers: Dict[str, Callable] = {
            'register': self._handle_register,
            'chat': self._handle_chat,
            'clear_history': self._handle_clear_history,
            'create_group': self._handle_create_group,
            'modify_group': self._handle_modify_group,
            'list_groups': self._handle_list_groups,
            'delete_request': self._handle_delete_request,
            'chatlist': self._handle_chatlist,
            'online': self._handle_online,
            'message_history': self._handle_message_history,
            'disconnect': self._handle_disconnect
        }

        handler = handlers.get(msg_type)
        if handler:
            handler(obj)

    def _handle_register(self, obj: dict):
        #user registration
        username = obj.get('user')
        timezone = obj.get('timezone', 'UTC+06:00')

        user = self.server.register_user(username, self.client, timezone)
        if not user:
            self._send_error('duplicate_user')
            return

        self.user = user

    def _handle_chat(self, obj: dict):
        # message
        if not self.user:
            return

        to = obj.get('to')
        text = obj.get('text', '')
        group_field = obj.get('group')
        broadcast_all = obj.get('broadcast', False)

        msg_id = self.server.get_next_msg_id()
        ts = int(time.time())

        if broadcast_all:
            self._send_broadcast_message(msg_id, text, ts)
        elif self._is_group_message(group_field, to):
            group_name = group_field if isinstance(group_field, str) else to
            self._send_group_message(group_name, msg_id, text, ts)
        else:
            self._send_private_message(to, msg_id, text, ts)

    def _is_group_message(self, group_field, to) -> bool:
        return (isinstance(group_field, str) and group_field) or \
               (isinstance(group_field, bool) and group_field and isinstance(to, str))

    def _send_broadcast_message(self, msg_id: str, text: str, ts: int):
        self.server.db.insert_message(self.user.username, 'ALL', text, ts, False)
        msg = {
            'type': 'message',
            'id': msg_id,
            'from': self.user.username,
            'to': 'ALL',
            'text': text,
            'ts': ts,
            'group': False,
            'broadcast': True
        }
        self.server.broadcast(json.dumps(msg))

    def _send_group_message(self, group_name: str, msg_id: str, text: str, ts: int):
        group = self.server.get_group(group_name)
        if not group:
            self._send_error('group_not_found', {'group': group_name})
            return

        self.server.db.insert_message(self.user.username, group_name, text, ts, True)
        # Increment unread for all members except sender
        for member in group.members:
            if member != self.user.username:
                self.server.db.increment_unread(member, group_name)
        msg = {
            'type': 'message',
            'id': msg_id,
            'from': self.user.username,
            'to': group_name,
            'text': text,
            'ts': ts,
            'group': True
        }
        targets = [self.server.users[u] for u in group.members if u in self.server.users]
        self.server.broadcast(json.dumps(msg), targets)

    def _send_private_message(self, to: str, msg_id: str, text: str, ts: int):
        self.server.db.insert_message(self.user.username, to, text, ts, False)
        if to in self.server.users:
            self.server.db.increment_unread(to, self.user.username)
        msg = {
            'type': 'message',
            'id': msg_id,
            'from': self.user.username,
            'to': to,
            'text': text,
            'ts': ts,
            'group': False
        }
        targets = []
        if self.user.username in self.server.users:
            targets.append(self.server.users[self.user.username])
        if to in self.server.users:
            targets.append(self.server.users[to])
        if targets:
            self.server.broadcast(json.dumps(msg), targets)

    def _handle_clear_history(self, obj: dict):
        if not self.user:
            return

        other_user = obj.get('with_user')
        if not other_user:
            self._send_error('missing_user')
            return

        clear_ts = int(time.time())
        self.server.db.clear_history(self.user.username, other_user, clear_ts)

        response = {
            'type': 'history_cleared',
            'with_user': other_user,
            'cleared_at': clear_ts
        }
        self.user.send(json.dumps(response))

    def _handle_create_group(self, obj: dict):
        if not self.user:
            return

        group_name = obj.get('group_name', '').strip()
        members = obj.get('members', [])

        if not group_name:
            self._send_error('empty_group_name')
            return

        group = self.server.create_group(group_name, self.user.username, members)
        if not group:
            self._send_error('group_exists')
            return

        response = {'type': 'group_created', 'group_name': group_name, 'created_by': self.user.username}
        targets = [self.server.users[m] for m in group.members if m in self.server.users]
        self.server.broadcast(json.dumps(response), targets)

    def _handle_modify_group(self, obj: dict):
        if not self.user:
            return

        group_name = obj.get('group_name')
        action = obj.get('action')
        member = obj.get('member')

        group = self.server.get_group(group_name)
        if not group:
            self._send_error('group_not_found')
            return

        if not group.is_creator(self.user.username):
            self._send_error('not_group_owner')
            return

        if action == 'delete_group':
            response = {'type': 'group_deleted', 'group_name': group_name}
            targets = [self.server.users[m] for m in group.members if m in self.server.users]
            self.server.broadcast(json.dumps(response), targets)

            for member_name in list(group.members):
                if member_name in self.server.users:
                    user_obj = self.server.users[member_name]
                    if group_name in user_obj.groups:
                        user_obj.groups.remove(group_name)

            self.server.delete_group(group_name)
            return
        elif action == 'add':

            if not group.add_member(member):
                self._send_error('already_member')
                return
            if member in self.server.users:
                self.server.users[member].groups.append(group_name)
        elif action == 'remove':
            if not group.remove_member(member):
                self._send_error('not_member')
                return
            if member in self.server.users and group_name in self.server.users[member].groups:
                self.server.users[member].groups.remove(group_name)

        response = {'type': 'group_modified', 'group_name': group_name, 'action': action, 'member': member}
        targets = [self.server.users[m] for m in group.members if m in self.server.users]
        self.server.broadcast(json.dumps(response), targets)

    def _handle_list_groups(self, obj: dict):
        if not self.user:
            return

        response = {'type': 'groups_list', 'groups': self.user.groups}
        self.user.send(json.dumps(response))

    def _handle_delete_request(self, obj: dict):
        if not self.user:
            return

        msg_id = obj.get('id')
        row = self.server.db.get_message(msg_id)

        if not row:
            self._send_error('not_found', {'id': msg_id})
            return

        sender_db, receiver_db, groupchat_db = row
        if sender_db != self.user.username:
            self._send_error('permission_denied', {'id': msg_id})
            return

        self.server.db.delete_message(msg_id)
        evt = {'type': 'delete', 'id': msg_id, 'deleted_by': self.user.username}

        if groupchat_db:
            group = self.server.get_group(receiver_db)
            if group:
                targets = [self.server.users[u] for u in group.members if u in self.server.users]
                self.server.broadcast(json.dumps(evt), targets)
        else:
            targets = []
            if self.user.username in self.server.users:
                targets.append(self.server.users[self.user.username])
            if receiver_db in self.server.users:
                targets.append(self.server.users[receiver_db])
            if targets:
                self.server.broadcast(json.dumps(evt), targets)

    def _handle_chatlist(self, obj: dict):
        response = {'type': 'chatlist', 'users': list(self.server.users.keys())}
        self.user.send(json.dumps(response))

    def _handle_online(self, obj: dict):
        self.server.broadcast_online_status()

    def _handle_message_history(self, obj: dict):
        if not self.user:
            return

        chat_with = obj.get('with_user')
        limit = obj.get('limit', 50)

        self.server.db.reset_unread(self.user.username, chat_with)

        is_group = chat_with in self.server.groups
        rows = self.server.db.get_message_history(self.user.username, chat_with, limit, is_group)
        rows = self.server.db.get_unread_history(self.user.username, chat_with, limit, is_group)


        history = []
        for row in rows:
            mid_db, sender_db, receiver_db, text_db, ts_db, deleted_db = row
            history.append({
                'type': 'message',
                'id': str(mid_db),
                'from': sender_db,
                'to': receiver_db,
                'text': text_db,
                'ts': ts_db,
                'deleted': bool(deleted_db),
                'group': is_group
            })

        response = {
            'type': 'message_history',
            'with_user': chat_with,
            'messages': history,
            'cleared': self.server.db.get_cleared_timestamp(self.user.username, chat_with) > 0
        }
        print(f"[Server] Sending message_history response to {self.user.username}: {len(history)} messages")
        result = self.user.send(json.dumps(response))
        print(f"[Server] Send result: {result}")
        self.user.send(json.dumps(response))

    def _handle_get_unread_counts(self, obj: dict):
        if not self.user:
            return

        counts = self.server.db.get_all_unread_counts(self.user.username)
        response = {
            'type': 'unread_counts',
            'counts': counts
        }
        self.user.send(json.dumps(response))

    def _handle_disconnect(self, obj: dict):
        self._cleanup()
        raise ConnectionError()

    def _send_error(self, error_type: str, extra: dict = None):
        error_msg = {'type': 'error', 'what': error_type}
        if extra:
            error_msg.update(extra)
        if self.user:
            self.user.send(json.dumps(error_msg))

    def _cleanup(self):
        if self.user:
            self.server.unregister_user(self.user.username)
        try:
            self.server.clients.remove(self.client)
        except:
            pass
        try:
            self.client.close()
        except:
            pass
