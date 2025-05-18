import sys
import socket
import logging

#set basic logging
logging.basicConfig(level=logging.INFO)

# Nama file yang akan dikirim
file_to_send = 'teks.txt'

try:
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Connect the socket to the port where the server is listening
    server_address = ('172.16.16.101', 32444)
    logging.info(f"connecting to {server_address}")
    sock.connect(server_address)

    # Membaca isi file
    try:
        with open(file_to_send, 'r') as f:
            message = f.read()
        logging.info(f"successfully read file: {file_to_send}")
    except FileNotFoundError:
        logging.error(f"Error: File not found: {file_to_send}")
        sys.exit(1) # Keluar jika file tidak ditemukan

    # Mengirim data dari file
    logging.info(f"sending content of {file_to_send} ({len(message)} bytes)")
    sock.sendall(message.encode())

    # Kode untuk menerima balasan dari server
    logging.info("waiting for response (if any)...")
    received_data = b''
    sock.settimeout(5)
    while True:
        data = sock.recv(1024)
        if not data:
            logging.info("server finished sending data or disconnected")
            break
        received_data += data
        logging.info(f"received chunk: {data.decode()}")

    if received_data:
         logging.info(f"Received complete response: {received_data.decode()}")
    else:
         logging.info("No response received from server.")


except Exception as ee:
    logging.info(f"ERROR: {str(ee)}")
    #exit(0)
finally:
    logging.info("closing socket")
    sock.close()