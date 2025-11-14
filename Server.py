import threading
import socket
host = '127.0.0.1'
port = 59374
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((host, port))
server.listen()
clients = []
aliases = []
timezones = []


def build_online_list():
    if not aliases:
        return "ONLINE: (no connected users)"
    return "ONLINE: " + ", ".join([f"{a} ({tz})" for a, tz in zip(aliases, timezones)])


def broadcast(message):
    for client in clients:
        client.send(message)


def handle_client(client):
    while True:
        try:
            message = client.recv(1024)
            broadcast(message)
        except:
            index = clients.index(client)
            clients.remove(client)
            client.close()
            alias = aliases[index]
            broadcast(f'{alias} has left the chat room!'.encode('utf-8'))
            aliases.remove(alias)
            timezones.pop(index)
            broadcast(build_online_list().encode('utf-8'))
            break

def receive():
    while True:
        print('Server is running and listening ...')
        client, address = server.accept()
        print(f'connection is established with {str(address)}')
        client.send('alias?'.encode('utf-8'))
        alias = client.recv(1024).decode('utf-8').strip()
        client.send('timezone?'.encode('utf-8'))
        tz = client.recv(1024).decode('utf-8').strip()
        if not tz:
            tz = 'UTC+06:00'
        aliases.append(alias)
        timezones.append(tz)
        clients.append(client)
        print(f'The alias of this client is {alias} with timezone {tz}')
        broadcast(f'{alias} has connected to the chat room'.encode('utf-8'))
        broadcast(build_online_list().encode('utf-8'))
        client.send('you are now connected!'.encode('utf-8'))
        thread = threading.Thread(target=handle_client, args=(client,))
        thread.start()


if __name__ == "__main__":
    receive()