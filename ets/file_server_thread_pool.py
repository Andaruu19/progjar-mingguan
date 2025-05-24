# file_server_thread_pool.py

from socket import *
import socket
import threading
import logging
import time
import sys
import json
from concurrent.futures import ThreadPoolExecutor

# --- KONFIGURASI LOGGING DI ATAS ---
log_format = '%(asctime)s - %(levelname)s - %(threadName)s - SERVER - %(module)s - %(funcName)s - %(lineno)d - %(message)s'
logging.basicConfig(level=logging.DEBUG, format=log_format, force=True if sys.version_info >= (3, 8) else False)
logging.debug("--- Top-level logging configured (Thread Pool Version) ---")

from file_protocol import FileProtocol
fp = FileProtocol()

# --- STATISTIK WORKER SERVER ---
server_worker_stats = {
    "processed_connections": 0,
    "successful_connections": 0,
    "failed_connections": 0,
}
stats_lock = threading.Lock() # Lock untuk mengamankan update statistik

def update_worker_stats(success=True):
    with stats_lock:
        server_worker_stats["processed_connections"] += 1
        if success:
            server_worker_stats["successful_connections"] += 1
        else:
            server_worker_stats["failed_connections"] += 1

# Fungsi worker yang akan dijalankan oleh thread di pool
def process_client_connection(connection, address):
    logger = logging.getLogger(__name__ + ".process_client_connection")
    logger.info(f"Worker thread {threading.get_ident()} processing connection from {address}")
    
    command_buffer = ""
    connection_successful = True # Asumsikan sukses sampai ada error
    try:
        while True:
            # ... (logika recv dan buffer sama seperti sebelumnya) ...
            buffer_size = 1048576 # 1MB buffer
            data = connection.recv(buffer_size)
            if data:
                try:
                    decoded_chunk = data.decode()
                except UnicodeDecodeError as ude:
                    logger.error(f"UnicodeDecodeError from {address}: {ude}. Raw data: {data[:60]}...")
                    handle_error_response(connection, address, "Invalid (non-UTF-8) data received.")
                    connection_successful = False # Tandai koneksi gagal
                    break 

                logger.debug(f"Received chunk from {address} by thread {threading.get_ident()}: {decoded_chunk[:60]}{'...' if len(decoded_chunk)>60 else ''} (length: {len(data)})")
                command_buffer += decoded_chunk

                if "\r\n\r\n" in command_buffer:
                    complete_command, _, rest_of_buffer = command_buffer.partition("\r\n\r\n")
                    command_buffer = rest_of_buffer 

                    logger.info(f"Processing complete command from {address} by thread {threading.get_ident()}: {complete_command[:100]}{'...' if len(complete_command)>100 else ''}")
                    
                    hasil_json_str = fp.proses_string(complete_command.strip())
                    logger.debug(f"fp.proses_string returned for {address}: {hasil_json_str[:100]}{'...' if len(hasil_json_str)>100 else ''}")
                    
                    if hasil_json_str is None: # Harusnya tidak terjadi dengan FileProtocol yang ada
                        logger.error(f"fp.proses_string returned None for command: {complete_command[:60]} from {address}. Sending generic error.")
                        hasil_json_str = json.dumps({"status": "ERROR", "data": "Internal server processing error (protocol returned None)"})
                        # Cek apakah JSON yang dikembalikan adalah error
                        try:
                            response_dict = json.loads(hasil_json_str)
                            if response_dict.get("status") == "ERROR":
                                connection_successful = False
                        except json.JSONDecodeError:
                            connection_successful = False


                    # Cek jika hasil_json_str dari fp.proses_string adalah error
                    try:
                        response_dict = json.loads(hasil_json_str)
                        if response_dict.get("status") == "ERROR":
                            logger.warning(f"Command processing for {address} resulted in ERROR: {response_dict.get('data')}")
                            connection_successful = False # Tandai gagal jika protokol mengembalikan error
                    except json.JSONDecodeError:
                        logger.error(f"Could not parse JSON from fp.proses_string for {address}: {hasil_json_str}")
                        connection_successful = False


                    response_to_send = hasil_json_str + "\r\n\r\n"
                    logger.debug(f"Sending response to {address}: {response_to_send[:100]}{'...' if len(response_to_send)>100 else ''}")
                    connection.sendall(response_to_send.encode())
                    logger.debug(f"Response sent to {address}")
                    # Asumsi client akan disconnect atau kita break jika satu perintah selesai
                    # Jika tidak break di sini, dan client mengirim perintah lain, connection_successful
                    # akan merefleksikan status operasi terakhir.
                    # Untuk benchmark di mana client disconnect setelah 1 siklus, ini cukup.
            else:
                logger.info(f"Client {address} disconnected (recv returned no data).")
                break
    except ConnectionResetError:
        logger.warning(f"Connection reset by client {address}.")
        connection_successful = False
    except BrokenPipeError:
        logger.warning(f"Broken pipe with client {address}. Client may have closed connection abruptly.")
        connection_successful = False
    except Exception as e:
        logger.error(f"Generic error processing client {address} in worker thread {threading.get_ident()}: {e}", exc_info=True)
        handle_error_response(connection, address, f"Server error: {str(e)}")
        connection_successful = False
    finally:
        logger.info(f"Closing connection with {address} by worker thread {threading.get_ident()}. Success: {connection_successful}")
        connection.close()
        update_worker_stats(connection_successful) # Update statistik global

# ... (handle_error_response sama) ...
def handle_error_response(connection, address, error_message):
    logger = logging.getLogger(__name__ + ".handle_error_response")
    try:
        error_response_dict = {"status": "ERROR", "data": error_message}
        error_response_json = json.dumps(error_response_dict)
        error_response_to_send = error_response_json + "\r\n\r\n"
        connection.sendall(error_response_to_send.encode())
    except Exception as send_err:
        logger.error(f"Failed to send error response to {address} after error: {send_err}")

class Server(threading.Thread):
    def __init__(self, ipaddress='0.0.0.0', port=6677, max_workers=5): # Default max_workers
        # ... (inisialisasi sama seperti sebelumnya) ...
        self.ipinfo = (ipaddress, port)
        self.logger = logging.getLogger(__name__ + "." + self.__class__.__name__)
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        threading.Thread.__init__(self)
        self.logger.debug(f"Server class initialized for {self.ipinfo} with {max_workers} max worker threads.")
        self.running = True

    def run(self):
        # ... (logika bind dan listen sama) ...
        self.logger.info(f"Server attempting to bind to IP address {self.ipinfo}")
        try:
            self.my_socket.bind(self.ipinfo)
            self.my_socket.listen(10 + (self.thread_pool._max_workers * 2)) # Backlog disesuaikan
            self.logger.info(f"Server listening on {self.ipinfo}")
        except OSError as e:
            self.logger.critical(f"SERVER FAILED TO BIND to {self.ipinfo}: {e}. Exiting.", exc_info=True)
            self.running = False
            return

        while self.running:
            try:
                self.logger.debug("Server waiting for a new connection...")
                connection, client_address = self.my_socket.accept()
                self.logger.info(f"Accepted connection from {client_address}")
                
                # Serahkan penanganan koneksi ke thread pool
                self.thread_pool.submit(process_client_connection, connection, client_address)
                
            # ... (penanganan error accept sama) ...
            except OSError as e:
                 if self.running:
                    self.logger.error(f"Socket error during accept: {e}", exc_info=True)
                 break 
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error accepting new connection: {e}", exc_info=True)
                time.sleep(0.1)

        self.logger.info("Server run loop terminated.")
        self.shutdown_pool()

    def shutdown_pool(self):
        self.logger.info("Shutting down thread pool...")
        self.thread_pool.shutdown(wait=True)
        self.logger.info("Thread pool shut down.")
        
        # --- TAMPILKAN STATISTIK DI SINI ---
        self.logger.info("=" * 30 + " SERVER WORKER STATISTICS " + "=" * 30)
        with stats_lock: # Amankan akses saat membaca
            self.logger.info(f"Total Connections Processed by Workers: {server_worker_stats['processed_connections']}")
            self.logger.info(f"  Successful Connections: {server_worker_stats['successful_connections']}")
            self.logger.info(f"  Failed Connections: {server_worker_stats['failed_connections']}")
        self.logger.info("=" * 78)
        
    def stop_server(self):
        # ... (logika stop_server sama, pastikan shutdown_pool dipanggil setelah loop berhenti) ...
        self.logger.info("Stop server called.")
        self.running = False
        try:
            # Membuat koneksi dummy untuk membuka blokir accept()
            dummy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dummy_socket.settimeout(0.5)
            dummy_socket.connect(self.ipinfo)
            dummy_socket.close()
            self.logger.debug("Dummy connection made to unblock accept().")
        except Exception as e:
            self.logger.warning(f"Could not make dummy connection to unblock accept(): {e}")

        # Menutup socket tidak akan menghentikan accept() jika sudah memblokir.
        # Loop while self.running akan berhenti, lalu shutdown_pool() akan dipanggil.
        # Penutupan socket utama bisa dilakukan setelah pool di-shutdown jika diperlukan,
        # atau jika accept() gagal karena socket ditutup.
        if self.my_socket:
            self.logger.info("Closing server main socket (will happen after accept unblocks or errors).")
            try:
                # Shutdown dulu untuk memberi tahu peer
                self.my_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass # Socket mungkin sudah ditutup atau tidak bisa di-shutdown
            finally:
                self.my_socket.close()
            self.logger.info("Server main socket closed.")


def main():
    # ... (main sama seperti sebelumnya, atur num_workers jika perlu) ...
    main_logger = logging.getLogger(__name__)
    main_logger.info("Executing main() function to start server (Thread Pool Version).")
    
    num_workers = 50
    svr = Server(ipaddress='0.0.0.0', port=6677, max_workers=num_workers)
    svr.start()
    main_logger.info(f"Server thread started with a pool of {num_workers} workers.")
    
    try:
        while svr.is_alive(): # Loop selama server thread masih hidup
            time.sleep(1)
    except KeyboardInterrupt:
        main_logger.info("KeyboardInterrupt received, initiating server shutdown...")
    finally:
        main_logger.info("Starting final shutdown sequence...")
        if svr.is_alive():
            svr.stop_server() # Memberi sinyal server untuk berhenti
            svr.join(timeout=10) # Tunggu thread server utama selesai, termasuk shutdown_pool
            if svr.is_alive():
                main_logger.warning("Server main thread did not terminate gracefully after timeout.")
        main_logger.info("Server shutdown complete.")

if __name__ == "__main__":
    main()