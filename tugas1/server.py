import sys
import socket
import logging

logging.basicConfig(level=logging.INFO)

try:
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #sock.settimeout(10)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1 )

    # Bind the socket to the port
    server_address = ('0.0.0.0', 32444)

    logging.info(f"starting up on {server_address}")
    sock.bind(server_address)
    # Listen for incoming connections
    sock.listen(1)
    #1 = backlog, merupakan jumlah dari koneksi yang belum teraccept/dilayani yang bisa ditampung, diluar jumlah
    #             tsb, koneks akan direfuse
    while True:
        # Wait for a connection
        logging.info("waiting for a connection")
        connection, client_address = sock.accept()
        logging.info(f"connection from {client_address}")

        # ----- MULAI PENERIMAAN DATA DARI FILE -----
        logging.info(f"receiving data from client {client_address}...")
        received_file_content = b'' # Menggunakan byte string untuk menampung data
        while True:
            data = connection.recv(1024) # Menggunakan buffer size yang lebih besar
            if data:
                received_file_content += data
                # logging.info(f"received chunk: {data}") # Opsional: log setiap chunk yang diterima
            else:
                # Data kosong diterima, ini menandakan client telah menutup koneksi setelah mengirim semua data.
                logging.info(f"finished receiving data from {client_address}")
                break
        # ----- AKHIR PENERIMAAN DATA DARI FILE -----

        # --- MENAMPILKAN ISI FILE SETELAH MENERIMA SELURUH DATA ---
        # Logic penampilan dipindahkan ke sini, setelah loop penerimaan selesai
        logging.info(f"\n--- START OF RECEIVED FILE CONTENT ---")
        try:
            # Mendecode data biner menjadi string teks
            logging.info(received_file_content.decode('utf-8'))
        except UnicodeDecodeError:
            logging.warning("Could not decode received data as UTF-8. Displaying raw bytes.")
            logging.info(received_file_content)
        logging.info(f"--- END OF RECEIVED FILE CONTENT ---\n")
        # --- AKHIR MENAMPILKAN ISI FILE ---


        # Clean up the connection
        connection.close()
except Exception as ee:
    logging.info(f"ERROR: {str(ee)}")
finally:
    logging.info('closing server socket')
    sock.close()