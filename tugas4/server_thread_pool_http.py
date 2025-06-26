from socket import *
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from http import HttpServer

httpserver = HttpServer()

def ProcessTheClient(connection, address):
    try:
        headers_data = b""
        while True:
            data = connection.recv(1)
            if not data:
                break
            headers_data += data
            if headers_data.endswith(b"\r\n\r\n"):
                break

        headers_str = headers_data.decode('utf-8', 'ignore')
        
        content_length = 0
        lines = headers_str.split('\r\n')
        for line in lines:
            if line.lower().startswith('content-length:'):
                try:
                    content_length = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    content_length = 0
                break
        
        body_data = b""
        if content_length > 0:
            remaining_bytes = content_length
            while remaining_bytes > 0:
                chunk = connection.recv(min(remaining_bytes, 4096))
                if not chunk:
                    break
                body_data += chunk
                remaining_bytes -= len(chunk)

        full_request = headers_data + body_data
        
        hasil = httpserver.proses(full_request)
        
        connection.sendall(hasil)
    
    except Exception as e:
        print(f"Error processing client {address}: {e}", file=sys.stderr)
    
    finally:
        connection.close()
        return

def Server():
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_address = ('0.0.0.0', 8885)
    my_socket.bind(server_address)
    my_socket.listen(1)
    print(f"Server berjalan di http://localhost:{server_address[1]}")

    with ThreadPoolExecutor(20) as executor:
        while True:
            try:
                connection, client_address = my_socket.accept()
                executor.submit(ProcessTheClient, connection, client_address)
            except KeyboardInterrupt:
                print("\nServer dihentikan.")
                break
    my_socket.close()

if __name__ == "__main__":
    Server()