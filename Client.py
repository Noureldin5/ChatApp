
import socket
import threading
import json
import sys
import time
import winsound



def prompt(text, default=None):
    v = input(text)
    if not v and default is not None:
        return default
    return v


def print_online(online):
    print("\nOnline:")
    for user in online:
        print(f"  {user['alias']} ({user['timezone']})")


def print_chat(chat, my_alias):
    print("\n--- Chat ---")
    for m in chat:
        if m.get('deleted'):
            continue
        t = m['timestamp']
        sender = m['sender']
        to = m.get('to')
        msg = m['message']
        mid = m['id']
        is_group = m.get('group', False)
        if is_group:
            # group message: show group name as target
            if sender == my_alias:
                print(f"[{mid}] {t} you -> group:{to}: {msg}")
            else:
                print(f"[{mid}] {t} {sender} -> group:{to}: {msg}")
        else:
            if to:
                if to == my_alias:
                    print(f"[{mid}] {t} {sender} -> you: {msg}")
                elif sender == my_alias:
                    print(f"[{mid}] {t} you -> {to}: {msg}")
                else:
                    print(f"[{mid}] {t} {sender} -> {to}: {msg}")
            else:
                who = "you" if sender == my_alias else sender
                print(f"[{mid}] {t} {who}: {msg}")


def play_notification_sound(filename='notif.wav'):
    try:
        winsound.PlaySound(filename, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            print('\a', end='', flush=True)

def main():
    host = "127.0.0.1"
    port = 59394
    alias = prompt("Choose an alias: ")
    tz = prompt("Timezone (e.g. UTC+06:00) [UTC+06:00]: ", "UTC+06:00")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
    except Exception as e:
        print(f"Could not connect to server at {host}:{port} ({e})")
        sys.exit(1)
    s.send((json.dumps({"type": "register", "user": alias, "timezone": tz}) + "\n").encode())
    online = []
    chat = []
    chatlist = []
    lock = threading.Lock()
    running = True

    def format_ts(ts):
        try:
            return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(ts)))
        except:
            return str(ts)

    def print_help():
        print("Commands:")
        print("  send          - send a message. You'll be asked for recipient (blank=group) and message text.")
        print("  create_group  - create a group and add members.")
        print("  add           - add a member to a group (you must be the creator).")
        print("  remove        - remove a member from a group (you must be the creator).")
        print("  groups        - list groups you belong to.")
        print("  delete        - delete a message you sent. You need the numeric message ID shown in [id].")
        print("  history       - view chat history with a specific user or group.")
        print("  clear         - clear chat history with a specific user or group (only from your view).")
        print("  chats         - request the list of users you've chatted with from the server.")
        print("  online        - show current online users and their timezones.")
        print("  quit          - disconnect and exit the client.")
        print("Note: Clearing history only affects YOUR view. Others can still see the messages.")

    def receiver():
        nonlocal online, chat, chatlist, running
        buffer = b""
        while running:
            try:
                data = s.recv(4096)
                if not data:
                    print("Disconnected from server.")
                    running = False
                    break
                buffer += data
                parts = buffer.split(b'\n')
                buffer = parts.pop()  # remainder
                for msg in parts:
                    if not msg.strip():
                        continue
                    try:
                        obj = json.loads(msg.decode())
                    except:
                        continue
                    typ = obj.get("type")
                    if typ == "online":
                        with lock:
                            online = [
                                {"alias": u, "timezone": t}
                                for u, t in zip(obj["users"], obj["timezones"])
                            ]
                        print_online(online)
                    elif typ == "chatlist":
                        with lock:
                            chatlist = obj.get("users", [])
                        print("\nChats:")
                        for c in chatlist:
                            print(f"  {c}")
                    elif typ == "group_created":
                        print(f"\n✓ Group created: {obj.get('group_name')} by {obj.get('created_by')}")
                    elif typ == "group_modified":
                        print(f"\n✓ Group modified: {obj.get('group_name')} {obj.get('action')} {obj.get('member')}")
                    elif typ == "groups_list":
                        groups = obj.get("groups", [])
                        print("\nYour groups:")
                        for g in groups:
                            print(f"  {g}")
                    elif typ == "message_history":
                        with_user = obj.get('with_user', 'unknown')
                        messages = obj.get('messages', [])
                        was_cleared = obj.get('cleared', False)

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
                                t = format_ts(m['ts'])
                                sender = m['from']
                                to = m.get('to')
                                msg = m['text']
                                mid = m['id']
                                deleted = m.get('deleted', False)
                                deleted_str = " [DELETED]" if deleted else ""
                                is_group = m.get('group', False)

                                if is_group:
                                    who = "you" if sender == alias else sender
                                    print(f"[{mid}] {t} {who} in group:{to}: {msg}{deleted_str}")
                                else:
                                    if to == alias:
                                        print(f"[{mid}] {t} {sender} -> you: {msg}{deleted_str}")
                                    elif sender == alias:
                                        print(f"[{mid}] {t} you -> {to}: {msg}{deleted_str}")
                                    else:
                                        print(f"[{mid}] {t} {sender} -> {to}: {msg}{deleted_str}")

                        print("=== End of history ===\n")
                    elif typ == "history_cleared":
                        with_user = obj.get('with_user', 'unknown')
                        print(f"\n✓ Chat history with '{with_user}' has been cleared from your view.")
                        print("Note: This only affects your view. The other user can still see the messages.\n")

                        with lock:
                            if obj.get('with_user') and obj.get('with_user') in [m.get('to') for m in chat if m.get('group')]:
                                chat[:] = [m for m in chat if not (m.get('group') and m.get('to') == obj.get('with_user'))]
                            else:
                                chat[:] = [m for m in chat if not (m.get('to') == obj.get('with_user') or m.get('sender') == obj.get('with_user'))]
                    elif typ == "message":
                        m = obj
                        msg_obj = {
                            "id": m["id"],
                            "sender": m["from"],
                            "to": m.get("to"),
                            "message": m["text"],
                            "timestamp": format_ts(m["ts"]),
                            "group": m.get("group", False),
                        }
                        with lock:
                            chat.append(msg_obj)
                        # play notification only for messages not sent by me
                        if m.get("from") != alias:
                            play_notification_sound('notif.wav')
                        print_chat(chat, alias)
                    elif typ == "delete":
                        mid = obj["id"]
                        with lock:
                            for m in chat:
                                if m["id"] == mid:
                                    m["deleted"] = True
                        print(f"Message {mid} was deleted by {obj.get('deleted_by', 'unknown')}")
                        print_chat(chat, alias)
                    elif typ == "error":
                        print(f"[error] {obj.get('what')}")
                    else:
                        # other events
                        pass
            except Exception as e:
                print(f"Error: {e}")
                running = False
                break

    t = threading.Thread(target=receiver, daemon=True)
    t.start()

    print_help()

    try:
        while running:
            cmd = input("\n[send|create_group|add|remove|groups|delete|chats|history|clear|online|quit]> ").strip()
            if cmd == "quit":
                try:
                    s.send((json.dumps({"type": "disconnect"}) + "\n").encode())
                except:
                    pass
                running = False
                s.close()
                break
            elif cmd == "online":
                with lock:
                    print_online(online)
            elif cmd == "chats":
                s.send((json.dumps({"type": "chatlist"}) + "\n").encode())
                time.sleep(0.1)
            elif cmd == "create_group":
                g = input("Group name: ").strip()
                members = input("Members (comma separated, exclude yourself): ").strip().split(',')
                members = [m.strip() for m in members if m.strip()]
                payload = {'type': 'create_group', 'group_name': g, 'members': members}
                s.send((json.dumps(payload) + "\n").encode())
                time.sleep(0.1)
            elif cmd == "add":
                g = input("Group name: ").strip()
                m = input("Member to add: ").strip()
                payload = {'type': 'modify_group', 'group_name': g, 'action': 'add', 'member': m}
                s.send((json.dumps(payload) + "\n").encode())
                time.sleep(0.1)
            elif cmd == "remove":
                g = input("Group name: ").strip()
                m = input("Member to remove: ").strip()
                payload = {'type': 'modify_group', 'group_name': g, 'action': 'remove', 'member': m}
                s.send((json.dumps(payload) + "\n").encode())
                time.sleep(0.1)
            elif cmd == "groups":
                s.send((json.dumps({"type": "list_groups"}) + "\n").encode())
                time.sleep(0.1)
            elif cmd == "send":
                to = input("To (leave blank to send to a group): ").strip()
                msg = input("Message: ")
                payload = {"type": "chat", "text": msg}
                if to:
                    # private message
                    payload["to"] = to
                    payload["group"] = False
                else:
                    # group message - ask for group name
                    group_name = input("Group name: ").strip()
                    if not group_name:
                        print("Group name required.")
                        continue
                    payload["group"] = group_name
                    payload["to"] = group_name
                s.send((json.dumps(payload) + "\n").encode())
            elif cmd == "delete":
                mid = input("Message ID to delete: ").strip()
                s.send((json.dumps({"type": "delete_request", "id": mid}) + "\n").encode())
            elif cmd == "history":
                with_user = input("View history with (username or group): ").strip()
                if not with_user:
                    print("Please specify a username or group")
                    continue
                limit_input = input("Number of messages to fetch (default 50): ").strip()
                limit = int(limit_input) if limit_input.isdigit() else 50
                payload = {
                    "type": "message_history",
                    "with_user": with_user,
                    "limit": limit
                }
                s.send((json.dumps(payload) + "\n").encode())
                time.sleep(0.2)
            elif cmd == "clear":
                with_user = input("Clear history with (username or group): ").strip()
                if not with_user:
                    print("Please specify a username or group")
                    continue
                confirm = input(
                    f"Are you sure you want to clear history with '{with_user}'? (yes/no): ").strip().lower()
                if confirm not in ['yes', 'y']:
                    print("Clear operation cancelled.")
                    continue
                payload = {
                    "type": "clear_history",
                    "with_user": with_user
                }
                s.send((json.dumps(payload) + "\n").encode())
                time.sleep(0.1)
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        try:
            s.send((json.dumps({"type": "disconnect"}) + "\n").encode())
        except:
            pass
        s.close()
        running = False


if __name__ == "__main__":
    main()