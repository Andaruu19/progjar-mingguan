from socket import *
import socket
import sys
import logging
from concurrent.futures import ProcessPoolExecutor # --- DIGANTI DARI ThreadPoolExecutor ---
from http import HttpServer

# Objek ini akan dibuat di proses utama, dan salinannya akan di-inherit oleh setiap child process.
# Ini aman karena HttpServer kita stateless.
httpserver = HttpServer()

def ProcessTheClient(connection, address):
    """
    Fungsi ini dijalankan di dalam sebuah child process.
    Logikanya sama persis dengan versi thread pool, yaitu membaca request HTTP dengan benar.
    """
    try:
        # Baca header terlebih dahulu sampai \r\n\r\n
        headers_data = b""
        while True:
            data = connection.recv(1)
            if not data:
                break
            headers_data += data
            if headers_data.endswith(b"\r\n\r\n"):
                break

        headers_str = headers_data.decode('utf-8', 'ignore')
        
        # Cari Content-Length untuk mengetahui ukuran body
        content_length = 0
        lines = headers_str.split('\r\n')
        for line in lines:
            if line.lower().startswith('content-length:'):
                try:
                    content_length = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    content_length = 0
                break
        
        # Baca body sesuai Content-Length
        body_data = b""
        if content_length > 0:
            remaining_bytes = content_length
            while remaining_bytes > 0:
                chunk = connection.recv(min(remaining_bytes, 4096))
                if not chunk:
                    break
                body_data += chunk
                remaining_bytes -= len(chunk)

        # Gabungkan header dan body menjadi satu request utuh untuk diproses
        full_request = headers_data + body_data
        
        # Proses request menggunakan objek httpserver yang ada di process ini
        hasil = httpserver.proses(full_request)
        
        # Kirim respons ke client
        connection.sendall(hasil)
    
    except Exception as e:
        # Logging error dari dalam process
        logging.error(f"Error pada process untuk client {address}: {e}")
    
    finally:
        connection.close()
        return

def Server():
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Menggunakan port yang berbeda (8889) sesuai contoh Anda untuk menghindari konflik
    server_address = ('0.0.0.0', 8889) 
    my_socket.bind(server_address)
    my_socket.listen(1)
    logging.info(f"Server (Process Pool) berjalan di http://localhost:{server_address[1]}")

    # Menggunakan ProcessPoolExecutor
    with ProcessPoolExecutor(10) as executor: # Anda bisa sesuaikan jumlah process
        while True:
            try:
                connection, client_address = my_socket.accept()
                logging.info(f"Koneksi diterima dari {client_address}, diserahkan ke process pool.")
                
                # Menyerahkan tugas memproses client ke salah satu process di pool
                executor.submit(ProcessTheClient, connection, client_address)
            except KeyboardInterrupt:
                logging.info("\nServer dihentikan oleh pengguna.")
                break
    my_socket.close()

def main():
	Server()

if __name__=="__main__":
    # Konfigurasi logging dasar
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(processName)s] - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )
    # Penggunaan `if __name__ == "__main__"` SANGAT PENTING untuk multiprocessing
    # agar child process tidak mengimpor dan menjalankan ulang kode server.
    main()