from typing import Dict, Callable
from .hints import Hints


class MessageHandler:
    def __init__(self, client):
        from .client import ChatClient
        self.client: ChatClient = client

    def handle(self, obj: dict):
        msg_type = obj.get("type")

        handlers: Dict[str, Callable] = {
            'online': self._handle_online,
            'chatlist': self._handle_chatlist,
            'group_created': self._handle_group_created,
            'group_modified': self._handle_group_modified,
            'groups_list': self._handle_groups_list,
            'message_history': self._handle_message_history,
            'history_cleared': self._handle_history_cleared,
            'message': self._handle_message,
            'delete': self._handle_delete,
            'error': self._handle_error
        }

        handler = handlers.get(msg_type)
        if handler:
            handler(obj)

    def _handle_online(self, obj: dict):
        with self.client.lock:
            self.client.online_users = [
                {"alias": u, "timezone": t}
                for u, t in zip(obj["users"], obj["timezones"])
            ]
        Hints.print_online(self.client.online_users)

    def _handle_chatlist(self, obj: dict):
        with self.client.lock:
            self.client.chatlist = obj.get("users", [])
        Hints.print_chats(self.client.chatlist, self.client.unread_counts)

    def _handle_group_created(self, obj: dict):
        print(f"\n✓ Group created: {obj.get('group_name')} by {obj.get('created_by')}")

    def _handle_group_modified(self, obj: dict):
        print(f"\n✓ Group modified: {obj.get('group_name')} {obj.get('action')} {obj.get('member')}")

    def _handle_groups_list(self, obj: dict):
        groups = obj.get("groups", [])
        Hints.print_groups(groups)

    def _handle_message_history(self, obj: dict):
        with_user = obj.get('with_user', 'unknown')
        messages = obj.get('messages', [])
        was_cleared = obj.get('cleared', False)

        Hints.print_history_messages(messages, with_user, self.client.alias, was_cleared)

    def _handle_history_cleared(self, obj: dict):
        with_user = obj.get('with_user', 'unknown')
        print(f"\n✓ Chat history with '{with_user}' has been cleared from your view.")
        print("Note: This only affects your view. The other user can still see the messages.\n")

        with self.client.lock:
            self.client.chat_history = [
                m for m in self.client.chat_history
                if not (m.get('to') == with_user or m.get('sender') == with_user)
            ]

    def _handle_message(self, obj: dict):
        msg_obj = {
            "id": obj["id"],
            "sender": obj["from"],
            "to": obj.get("to"),
            "message": obj["text"],
            "timestamp": Hints.format_timestamp(obj["ts"]),
            "group": obj.get("group", False),
        }

        with self.client.lock:
            self.client.chat_history.append(msg_obj)
        if obj.get("from") != self.client.alias:
            sender = obj["from"]
            is_group = obj.get("group", False)
            counter_key = obj.get("to") if is_group else sender

            self.client.unread_counts[counter_key] = \
            self.client.unread_counts.get(counter_key, 0) + 1

        if obj.get("from") != self.client.alias:
            Hints.play_notification()

        Hints.print_chat_history(self.client.chat_history, self.client.alias)

    def _handle_delete(self, obj: dict):
        msg_id = obj["id"]
        with self.client.lock:
            for m in self.client.chat_history:
                if m["id"] == msg_id:
                    m["deleted"] = True

        print(f"Message {msg_id} was deleted by {obj.get('deleted_by', 'unknown')}")
        Hints.print_chat_history(self.client.chat_history, self.client.alias)

    def _handle_error(self, obj: dict):
        print(f"[error] {obj.get('what')}")
