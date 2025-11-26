"""
Test script for authentication system
Run this after starting the server with: python -m server.main
"""
import socket
import json
import time

def test_auth():
    print("=== Testing Authentication System ===\n")

    # Test 1: Signup
    print("Test 1: Creating new account...")
    s1 = socket.socket()
    try:
        s1.connect(('127.0.0.1', 59394))

        signup_data = {
            'type': 'signup',
            'username': 'alice',
            'password': 'alice123',
            'timezone': 'UTC+02:00'
        }
        s1.send((json.dumps(signup_data) + '\n').encode())
        time.sleep(0.5)

        response = s1.recv(4096).decode()
        print(f"Signup response: {response.strip()}\n")
        s1.close()
    except Exception as e:
        print(f"Signup test failed: {e}\n")

    time.sleep(1)

    # Test 2: Login with correct credentials
    print("Test 2: Login with correct credentials...")
    s2 = socket.socket()
    try:
        s2.connect(('127.0.0.1', 59394))

        login_data = {
            'type': 'login',
            'username': 'alice',
            'password': 'alice123'
        }
        s2.send((json.dumps(login_data) + '\n').encode())
        time.sleep(0.5)

        response = s2.recv(4096).decode()
        print(f"Login response: {response.strip()}\n")
        s2.close()
    except Exception as e:
        print(f"Login test failed: {e}\n")

    time.sleep(1)

    # Test 3: Login with wrong password
    print("Test 3: Login with wrong password...")
    s3 = socket.socket()
    try:
        s3.connect(('127.0.0.1', 59394))

        login_data = {
            'type': 'login',
            'username': 'alice',
            'password': 'wrongpass'
        }
        s3.send((json.dumps(login_data) + '\n').encode())
        time.sleep(0.5)

        response = s3.recv(4096).decode()
        print(f"Login response: {response.strip()}\n")
        s3.close()
    except Exception as e:
        print(f"Wrong password test failed: {e}\n")

    print("=== Tests Complete ===")

if __name__ == '__main__':
    test_auth()

