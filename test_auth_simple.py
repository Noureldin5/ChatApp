"""
Quick test to verify authentication is working
"""
import socket
import json
import time
import threading

def receive_messages(sock):
    """Receive and print server responses"""
    buffer = b""
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break

            buffer += data
            parts = buffer.split(b'\n')
            buffer = parts.pop()

            for msg in parts:
                if msg.strip():
                    try:
                        obj = json.loads(msg.decode())
                        print(f"[SERVER]: {json.dumps(obj, indent=2)}")
                    except:
                        print(f"[RAW]: {msg.decode()}")
        except Exception as e:
            print(f"[RECV ERROR]: {e}")
            break

print("=" * 50)
print("Testing Authentication System")
print("=" * 50)

# Test 1: Signup
print("\n[TEST 1] Creating new account...")
s1 = socket.socket()
s1.connect(('127.0.0.1', 59394))

# Start receiver
t1 = threading.Thread(target=receive_messages, args=(s1,), daemon=True)
t1.start()

signup_msg = json.dumps({
    'type': 'signup',
    'username': 'alice123',
    'password': 'alice123',
    'timezone': 'UTC+02:00'
}) + '\n'

s1.send(signup_msg.encode())
print("[SENT]: Signup request for 'alice123'")
time.sleep(2)
s1.close()

print("\n" + "=" * 50)

# Test 2: Login with correct password
print("\n[TEST 2] Login with correct credentials...")
s2 = socket.socket()
s2.connect(('127.0.0.1', 59394))

t2 = threading.Thread(target=receive_messages, args=(s2,), daemon=True)
t2.start()

login_msg = json.dumps({
    'type': 'login',
    'username': 'alice123',
    'password': 'alice123'
}) + '\n'

s2.send(login_msg.encode())
print("[SENT]: Login request for 'alice123'")
time.sleep(2)
s2.close()

print("\n" + "=" * 50)

# Test 3: Login with wrong password
print("\n[TEST 3] Login with WRONG password...")
s3 = socket.socket()
s3.connect(('127.0.0.1', 59394))

t3 = threading.Thread(target=receive_messages, args=(s3,), daemon=True)
t3.start()

wrong_login = json.dumps({
    'type': 'login',
    'username': 'alice123',
    'password': 'wrongpass'
}) + '\n'

s3.send(wrong_login.encode())
print("[SENT]: Login with wrong password")
time.sleep(2)
s3.close()

print("\n" + "=" * 50)
print("Tests complete!")
print("=" * 50)

