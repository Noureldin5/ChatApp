from client.client import ChatClient
import getpass


def main():
    print("=== Welcome to the app ===")
    print("1. Login")
    print("2. Sign Up")
    choice = input("Choose (1/2): ").strip()

    client = ChatClient()
    client.connect()

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
        import time
        time.sleep(2)

        if not client.alias:
            print("\nSignup failed! Please try logging in or use a different username.")
            return

    else:
        print("\n--- Login ---")
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")

        client.login(username, password)
        print("\nWaiting for authentication...")
        import time
        time.sleep(2)

        if not client.alias:
            print("\nLogin failed! Check your credentials.")
            return

    print(f"\n✓ Authenticated as: {client.alias}")
    client.start()


if __name__ == "__main__":
    main()
