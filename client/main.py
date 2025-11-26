from client.client import ChatClient
import getpass
import threading
import time


def main():
    print("=== Welcome to the app ===")
    print("1. Login")
    print("2. Sign Up")
    choice = input("Choose (1/2): ").strip()

    client = ChatClient()
    client.connect()

    # Start receiver thread to handle server responses
    receiver_thread = threading.Thread(target=client._receive_messages, daemon=True)
    receiver_thread.start()
    time.sleep(0.5)  # Give receiver time to start

    if choice == "2":
        print("\n--- Sign Up ---")
        username = input("Choose username: ").strip()
        password = getpass.getpass("Choose password (min 6 chars): ")
        confirm = getpass.getpass("Confirm password: ")

        if password != confirm:
            print("Passwords don't match!")
            return

        if len(password) < 6:
            print("Password must be at least 6 characters!")
            return

        tz = input("Timezone (e.g. UTC+06:00) [UTC+06:00]: ").strip() or "UTC+06:00"

        client.signup(username, password, tz)
        print("\nWaiting for server response...")
        time.sleep(2)

        # After signup, user should see success message from handler
        # Then exit - they need to run the program again to login
        print("\n✓ Signup process complete. Please run the program again to login.")
        return

    else:
        print("\n--- Login ---")
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")

        client.login(username, password)
        print("\nWaiting for authentication...")
        time.sleep(2)

        if not client.alias:
            print("\nLogin failed! Check your credentials.")
            return

    print(f"\n✓ Authenticated as: {client.alias}")
    # Don't call client.start() since receiver is already running
    client._command_loop()


if __name__ == "__main__":
    main()
