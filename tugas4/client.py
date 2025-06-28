import socket
import os
import sys
import logging
import uuid

# Konfigurasi logging dasar untuk menampilkan pesan error
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def make_socket(destination_address='localhost', port=8885):
    """Membuat dan menghubungkan socket ke server."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (destination_address, port)
        logging.info(f"Menghubungkan ke {destination_address}:{port}...")
        sock.connect(server_address)
        return sock
    except ConnectionRefusedError:
        logging.error(f"Koneksi ditolak. Pastikan server di {destination_address}:{port} sedang berjalan.")
    except Exception as ee:
        logging.error(f"Gagal membuat socket: {str(ee)}")
    return None

def send_request(request_bytes, server_address):
    """Mengirim request dalam bentuk bytes dan menerima response."""
    sock = make_socket(server_address[0], server_address[1])
    if not sock:
        return "Gagal terhubung ke server."
    
    try:
        sock.sendall(request_bytes)
        data_received = b""
        while True:
            # Baca response dari server
            data = sock.recv(4096)
            if data:
                data_received += data
            else:
                break
        return data_received.decode('utf-8', errors="ignore")
    except Exception as ee:
        logging.error(f"Error saat komunikasi dengan server: {str(ee)}")
        return f"Error: {str(ee)}"
    finally:
        sock.close()
        logging.info("Koneksi ditutup.")

def list_files(server_address):
    """Meminta daftar file dari server (endpoint /files)."""
    logging.info("Meminta daftar file dari server...")
    # Request selalu ke /files sesuai dengan implementasi server
    command = b"GET /files HTTP/1.0\r\n\r\n"
    result = send_request(command, server_address)
    
    # Memisahkan header dari body untuk tampilan yang lebih rapi
    try:
        header, body = result.split('\r\n\r\n', 1)
        print("--- SERVER RESPONSE HEADER ---")
        print(header)
        print("\n--- SERVER RESPONSE BODY ---")
        print(body.strip())
    except ValueError:
        print("--- RAW SERVER RESPONSE ---")
        print(result)

def upload_file(server_address, local_filepath):
    """Mengupload file ke server menggunakan format multipart/form-data."""
    if not os.path.exists(local_filepath):
        logging.error(f"File lokal '{local_filepath}' tidak ditemukan.")
        return
        
    logging.info(f"Mempersiapkan untuk mengupload '{local_filepath}'...")
    filename = os.path.basename(local_filepath)
    
    try:
        with open(local_filepath, "rb") as f:
            file_content = f.read()
    except Exception as e:
        logging.error(f"Tidak bisa membaca file '{local_filepath}': {e}")
        return

    # Membuat request body dengan format multipart/form-data
    boundary = f"----ClientBoundary{uuid.uuid4().hex}"
    
    body = []
    body.append(f"--{boundary}".encode())
    body.append(f'Content-Disposition: form-data; name="fileToUpload"; filename="{filename}"'.encode())
    body.append(b'Content-Type: application/octet-stream')
    body.append(b'') # Baris kosong setelah header part
    body.append(file_content)
    body.append(f"--{boundary}--".encode())
    body.append(b'')
    
    body_bytes = b'\r\n'.join(body)

    # Membuat header HTTP utama
    headers = [
        "POST /upload HTTP/1.0",
        f"Host: {server_address[0]}",
        "User-Agent: Command-Line-Client/1.0",
        f"Content-Type: multipart/form-data; boundary={boundary}",
        f"Content-Length: {len(body_bytes)}"
    ]
    headers_str = "\r\n".join(headers) + "\r\n\r\n"
    
    # Menggabungkan header dan body menjadi satu request utuh
    request_bytes = headers_str.encode() + body_bytes
    
    logging.info("Mengirim request upload...")
    result = send_request(request_bytes, server_address)
    print("--- SERVER RESPONSE ---")
    print(result.strip())

def delete_file(server_address, server_filename):
    """Meminta penghapusan file di server."""
    logging.info(f"Meminta untuk menghapus file '{server_filename}' di server...")
    # URL encode mungkin diperlukan jika nama file mengandung spasi atau karakter khusus
    # Namun untuk kasus sederhana kita bisa lewatkan dulu
    command = f"DELETE /{server_filename} HTTP/1.0\r\n\r\n".encode()
    result = send_request(command, server_address)
    print("--- SERVER RESPONSE ---")
    print(result.strip())

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("\nPenggunaan:")
        print("  python client.py <host> <port> list")
        print("  python client.py <host> <port> upload <local_file_path>")
        print("  python client.py <host> <port> delete <server_filename>\n")
        sys.exit(1)

    host = sys.argv[1]
    try:
        port = int(sys.argv[2])
    except ValueError:
        logging.error("Port harus berupa angka.")
        sys.exit(1)
        
    command = sys.argv[3].lower()
    server_addr = (host, port)

    if command == 'list':
        list_files(server_addr)
    elif command == 'upload':
        if len(sys.argv) < 5:
            logging.error("Perintah 'upload' memerlukan path file lokal.")
            sys.exit(1)
        filepath = sys.argv[4]
        upload_file(server_addr, filepath)
    elif command == 'delete':
        if len(sys.argv) < 5:
            logging.error("Perintah 'delete' memerlukan nama file di server.")
            sys.exit(1)
        filename = sys.argv[4]
        delete_file(server_addr, filename)
    else:
        logging.error(f"Perintah '{command}' tidak valid. Gunakan 'list', 'upload', atau 'delete'.")
        sys.exit(1)