from socket import *
import socket
import sys
import logging  # 1. Impor modul logging
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
        
        # Di sini, `server_thread_pool_http.py` hanya menyerahkan request
        # ke `http.py` tanpa tahu isinya.
        hasil = httpserver.proses(full_request)
        
        connection.sendall(hasil)
    
    except Exception as e:
        # 4. Catat error jika terjadi masalah saat menangani koneksi
        logging.error(f"Error saat memproses client {address}: {e}")
    
    finally:
        connection.close()
        return

def Server():
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_address = ('0.0.0.0', 8885)
    my_socket.bind(server_address)
    my_socket.listen(1)
    # 3. Ganti print() dengan logging.info()
    logging.info(f"Server (Thread Pool) berjalan di http://localhost:{server_address[1]}")

    with ThreadPoolExecutor(20) as executor:
        while True:
            try:
                connection, client_address = my_socket.accept()
                # 4. Catat setiap koneksi yang masuk
                logging.info(f"Koneksi diterima dari {client_address}")
                executor.submit(ProcessTheClient, connection, client_address)
            except KeyboardInterrupt:
                # 4. Catat saat server dihentikan
                logging.info("\nServer dihentikan oleh pengguna.")
                break
    my_socket.close()

if __name__ == "__main__":
    # 2. Konfigurasikan logging
    logging.basicConfig(
        level=logging.INFO,
        # Format ini akan menampilkan waktu, nama thread, level log, dan pesan
        format='%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )
    Server()