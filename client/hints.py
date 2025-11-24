from typing import List, Dict
import winsound
import time


class Hints:
    @staticmethod
    def prompt(text: str, default=None) -> str:
        value = input(text)
        if not value and default is not None:
            return default
        return value

    @staticmethod
    def print_online(online_users: List[Dict]):
        print("\nOnline:")
        for user in online_users:
            print(f"  {user['alias']} ({user['timezone']})")

    @staticmethod
    def print_chat_history(messages: List, my_alias: str):
        print("\n--- Chat ---")
        for msg in messages:
            if msg.get('deleted'):
                continue
            Hints._print_single_message(msg, my_alias)

    @staticmethod
    def _print_single_message(msg: Dict, my_alias: str):
        msg_id = msg['id']
        timestamp = msg['timestamp']
        sender = msg['sender']
        to = msg.get('to')
        text = msg['message']
        is_group = msg.get('group', False)

        if is_group:
            who = "you" if sender == my_alias else sender
            print(f"[{msg_id}] {timestamp} {who} -> group:{to}: {text}")
        else:
            if to == my_alias:
                print(f"[{msg_id}] {timestamp} {sender} -> you: {text}")
            elif sender == my_alias:
                print(f"[{msg_id}] {timestamp} you -> {to}: {text}")
            else:
                print(f"[{msg_id}] {timestamp} {sender} -> {to}: {text}")

    @staticmethod
    def print_history_messages(messages: List[Dict], with_user: str, alias: str, was_cleared: bool):
        print(f"\n=== Chat history with {with_user} ===")

        if was_cleared:
            print("(History was previously cleared - showing messages after clear)")

        if not messages:
            if was_cleared:
                print("No new messages since you cleared the history.")
            else:
                print("No messages found.")
        else:
            for m in messages:
                t = Hints.format_timestamp(m['ts'])
                sender = m['from']
                to = m.get('to')
                msg_text = m['text']
                mid = m['id']
                deleted = m.get('deleted', False)
                deleted_str = " [DELETED]" if deleted else ""
                is_group = m.get('group', False)

                if is_group:
                    who = "you" if sender == alias else sender
                    print(f"[{mid}] {t} {who} in group:{to}: {msg_text}{deleted_str}")
                else:
                    if to == alias:
                        print(f"[{mid}] {t} {sender} -> you: {msg_text}{deleted_str}")
                    elif sender == alias:
                        print(f"[{mid}] {t} you -> {to}: {msg_text}{deleted_str}")
                    else:
                        print(f"[{mid}] {t} {sender} -> {to}: {msg_text}{deleted_str}")

        print("=== End of history ===\n")

    @staticmethod
    def print_chats(chatlist: List[str], unread_counts: Dict):
        print("\n Your Chats:")
        if not chatlist:
            print("  No active chats.")
        else:
             for chat in chatlist:
                 if unread_counts and chat in unread_counts and unread_counts[chat] > 0:
                     count = unread_cuounts[chat]
                     print(f"  {chat} ({count} unread messages{'s' if count > 1 else ''})")
                 else:
                      print(f"  {chat}")
        print("-----------------\n")

    @staticmethod
    def print_groups(groups: List[str]):
        print("\nYour groups:")
        for group in groups:
            print(f"  {group}")

    @staticmethod
    def print_help():
        print("Commands:")
        print("  send          - send a message")
        print("  create_group  - create a group and add members")
        print("  add           - add a member to a group")
        print("  delete_group  - delete a group and all its messages")
        print("  remove        - remove a member from a group")
        print("  groups        - list groups you belong to")
        print("  delete        - delete a message you sent")
        print("  history       - view chat history")
        print("  clear         - clear chat history (only from your view)")
        print("  chats         - list users you've chatted with")
        print("  online        - show current online users")
        print("  quit          - disconnect and exit")

    @staticmethod
    def play_notification():
        try:
            winsound.PlaySound('notif.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                print('\a', end='', flush=True)

    @staticmethod
    def format_timestamp(ts) -> str:
        try:
            return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(ts)))
        except:
            return str(ts)
