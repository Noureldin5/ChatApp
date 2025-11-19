
from client.client import ChatClient


def main():
    alias = input("Choose an alias: ")
    tz = input("Timezone (e.g. UTC+06:00) [UTC+06:00]: ").strip() or "UTC+06:00"

    client = ChatClient()
    client.connect()
    client.register(alias, tz)
    client.start()


if __name__ == "__main__":
    main()
