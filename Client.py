import threading
import socket
alias = input('Choose an alias >>> ')
timezone = input('Enter your timezone (e.g. +02:00 or leave empty for UTC+06:00) >>> ').strip()
if not timezone:
    timezone = 'UTC+06:00'
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('127.0.0.1', 59374))


def client_receive():
    while True:
        try:
            message = client.recv(1024).decode('utf-8')
            if message == "alias?":
                client.send(alias.encode('utf-8'))
            elif message == 'timezone?':
                client.send(timezone.encode('utf-8'))
            elif message.startswith('ONLINE:'):
                print(f'\n[{message}]')
            else:
                print(message)
        except:
            print('Error!')
            client.close()
            break


def client_send():
    while True:
        message = f'{alias}: {input("")}'
        client.send(message.encode('utf-8'))


receive_thread = threading.Thread(target=client_receive)
receive_thread.start()

send_thread = threading.Thread(target=client_send)
send_thread.start()