
from server.server import ChatServer


def main():
    server = ChatServer(host='127.0.0.1', port=59394)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
