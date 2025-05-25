from socket import *
import socket
import threading
import logging
import time
import sys
import os
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
if sys.platform != "win32":
    from multiprocessing import reduction
else:
    reduction = None
server_worker_stats_main = {
    "processed_tasks": 0,
    "successful_tasks": 0,
    "failed_tasks": 0,
}
main_stats_lock = threading.Lock()
from file_protocol import FileProtocol
def process_client_connection(connection_socket, client_address):
    worker_log_format = '%(asctime)s - %(levelname)s - %(processName)s (%(process)d) - %(threadName)s - WORKER - %(module)s - %(funcName)s - %(lineno)d - %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=worker_log_format, force=True if sys.version_info >= (3,8) else False)
    logger = logging.getLogger(__name__ + ".process_client_connection_worker")
    process_id = multiprocessing.current_process().pid
    fp_worker = FileProtocol()
    logger.info(f"Worker process {process_id} processing connection from {client_address}")
    command_buffer = ""
    connection_successful = True
    try:
        while True:
            buffer_size = 1048576
            data = connection_socket.recv(buffer_size)
            if data:
                try:
                    decoded_chunk = data.decode()
                except UnicodeDecodeError as ude:
                    logger.error(f"UnicodeDecodeError from {client_address} in worker {process_id}: {ude}. Raw data: {data[:60]}...")
                    handle_error_response_worker(connection_socket, client_address, "Invalid (non-UTF-8) data received.", logger)
                    connection_successful = False
                    break
                logger.debug(f"Worker {process_id} received chunk from {client_address}: {decoded_chunk[:60]}{'...' if len(decoded_chunk)>60 else ''} (length: {len(data)})")
                command_buffer += decoded_chunk
                if "\r\n\r\n" in command_buffer:
                    complete_command, _, rest_of_buffer = command_buffer.partition("\r\n\r\n")
                    command_buffer = rest_of_buffer
                    logger.info(f"Worker {process_id} processing command from {client_address}: {complete_command[:100]}{'...' if len(complete_command)>100 else ''}")
                    hasil_json_str = fp_worker.proses_string(complete_command.strip())
                    logger.debug(f"Worker {process_id}: fp_worker.proses_string returned for {client_address}: {hasil_json_str[:100]}{'...' if len(hasil_json_str)>100 else ''}")
                    if hasil_json_str is None:
                        logger.error(f"Worker {process_id}: fp_worker.proses_string returned None. Sending generic error.")
                        hasil_json_str = json.dumps({"status": "ERROR", "data": "Internal server processing error (protocol returned None)"})
                        try:
                            if json.loads(hasil_json_str).get("status") == "ERROR": connection_successful = False
                        except: connection_successful = False
                    try:
                        response_dict = json.loads(hasil_json_str)
                        if response_dict.get("status") == "ERROR":
                            connection_successful = False
                    except json.JSONDecodeError:
                        connection_successful = False
                    response_to_send = hasil_json_str + "\r\n\r\n"
                    logger.debug(f"Worker {process_id}: Sending response to {client_address}: {response_to_send[:100]}{'...' if len(response_to_send)>100 else ''}")
                    connection_socket.sendall(response_to_send.encode())
                    logger.debug(f"Worker {process_id}: Response sent to {client_address}")
            else:
                logger.info(f"Worker {process_id}: Client {client_address} disconnected (recv returned no data).")
                break
    except ConnectionResetError:
        logger.warning(f"Worker {process_id}: Connection reset by client {client_address}.")
        connection_successful = False
    except BrokenPipeError:
        logger.warning(f"Worker {process_id}: Broken pipe with client {client_address}.")
        connection_successful = False
    except Exception as e:
        logger.error(f"Worker {process_id}: Generic error processing client {client_address}: {e}", exc_info=True)
        handle_error_response_worker(connection_socket, client_address, f"Server error: {str(e)}", logger)
        connection_successful = False
    finally:
        logger.info(f"Worker {process_id}: Closing connection with {client_address}. Final success state: {connection_successful}")
        try:
            connection_socket.close()
        except Exception as e_close:
            logger.error(f"Worker {process_id}: Error closing socket for {client_address}: {e_close}")
        return connection_successful
def handle_error_response_worker(connection, address, error_message, logger_instance):
    try:
        error_response_dict = {"status": "ERROR", "data": error_message}
        error_response_json = json.dumps(error_response_dict)
        error_response_to_send = error_response_json + "\r\n\r\n"
        connection.sendall(error_response_to_send.encode())
    except Exception as send_err:
        logger_instance.error(f"Failed to send error response to {address} after error: {send_err}")
class Server(threading.Thread):
    def __init__(self, ipaddress='0.0.0.0', port=6677, max_workers=2):
        self.main_logger = logging.getLogger(__name__ + "." + self.__class__.__name__)
        self.ipinfo = (ipaddress, port)
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.process_pool = ProcessPoolExecutor(max_workers=max_workers)
        threading.Thread.__init__(self)
        self.main_logger.debug(f"Server class initialized for {self.ipinfo} with {max_workers} max worker processes.")
        self.running = True
        self.submitted_futures = []
    def run(self):
        self.main_logger.info(f"Server (PID {os.getpid()}) attempting to bind to IP address {self.ipinfo}")
        try:
            self.my_socket.bind(self.ipinfo)
            self.my_socket.listen(10 + (self.process_pool._max_workers * 2))
            self.main_logger.info(f"Server listening on {self.ipinfo}")
        except OSError as e:
            self.main_logger.critical(f"SERVER FAILED TO BIND to {self.ipinfo}: {e}. Exiting.", exc_info=True)
            self.running = False; return
        while self.running:
            try:
                self.main_logger.debug("Server main process waiting for a new connection...")
                connection, client_address = self.my_socket.accept()
                self.main_logger.info(f"Accepted connection from {client_address} (socket fd: {connection.fileno()})")
                future = self.process_pool.submit(process_client_connection, connection, client_address)
                self.submitted_futures.append(future)
            except OSError as e:
                 if self.running: self.main_logger.error(f"Socket error during accept: {e}", exc_info=True)
                 break
            except Exception as e:
                if self.running: self.main_logger.error(f"Error accepting new connection: {e}", exc_info=True)
                time.sleep(0.1)
        self.main_logger.info("Server run loop terminated.")
        self.shutdown_pool_and_collect_stats()
    def shutdown_pool_and_collect_stats(self):
        global server_worker_stats_main, main_stats_lock
        self.main_logger.info("Processing results from worker tasks...")
        self.main_logger.info("Shutting down process pool... (waiting for tasks to complete)")
        self.process_pool.shutdown(wait=True)
        self.main_logger.info("Process pool shut down.")
        for future in self.submitted_futures:
            if future.done():
                try:
                    task_successful = future.result(timeout=0.1)
                    with main_stats_lock:
                        server_worker_stats_main["processed_tasks"] += 1
                        if task_successful:
                            server_worker_stats_main["successful_tasks"] += 1
                        else:
                            server_worker_stats_main["failed_tasks"] += 1
                except Exception as e:
                    self.main_logger.error(f"Error retrieving result from completed future: {e}")
                    with main_stats_lock:
                        server_worker_stats_main["processed_tasks"] += 1
                        server_worker_stats_main["failed_tasks"] += 1
            else:
                self.main_logger.warning("Found a future that was not done after pool shutdown!")
                with main_stats_lock:
                    server_worker_stats_main["processed_tasks"] += 1
                    server_worker_stats_main["failed_tasks"] += 1
        self.main_logger.info("=" * 30 + " SERVER WORKER STATISTICS (PROCESS POOL) " + "=" * 30)
        with main_stats_lock:
            self.main_logger.info(f"Total Tasks Submitted to Workers: {len(self.submitted_futures)}")
            self.main_logger.info(f"Total Tasks Processed (results retrieved): {server_worker_stats_main['processed_tasks']}")
            self.main_logger.info(f"  Successful Tasks: {server_worker_stats_main['successful_tasks']}")
            self.main_logger.info(f"  Failed Tasks: {server_worker_stats_main['failed_tasks']}")
        self.main_logger.info("=" * 88)
    def stop_server(self):
        self.main_logger.info("Stop server called in main process.")
        self.running = False
        try:
            dummy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dummy_socket.settimeout(0.5)
            dummy_socket.connect(self.ipinfo)
            dummy_socket.close()
            self.main_logger.debug("Dummy connection made to unblock accept().")
        except Exception as e:
            self.main_logger.warning(f"Could not make dummy connection to unblock accept(): {e}")
        if self.my_socket:
            self.main_logger.info("Closing server main socket.")
            try:
                self.my_socket.close()
            except Exception as e_sock_close:
                self.main_logger.error(f"Error closing main server socket: {e_sock_close}")
def main():
    main_script_logger = logging.getLogger(__name__)
    main_script_logger.info("Executing main() function to start server (Process Pool Version).")
    num_workers = 50
    main_script_logger.info(f"Setting num_workers to {num_workers} (CPU cores: {os.cpu_count()}).")
    svr = Server(ipaddress='0.0.0.0', port=6677, max_workers=num_workers)
    svr.start()
    main_script_logger.info(f"Server thread started with a process pool of {num_workers} workers.")
    try:
        while svr.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        main_script_logger.info("KeyboardInterrupt received, initiating server shutdown...")
    finally:
        main_script_logger.info("Starting final shutdown sequence...")
        if svr.is_alive():
            svr.stop_server()
            svr.join(timeout=15)
            if svr.is_alive():
                main_script_logger.warning("Server main thread did not terminate gracefully after timeout.")
        main_script_logger.info("Server shutdown process complete.")
if __name__ == "__main__":
    multiprocessing.freeze_support()
    log_format_main = '%(asctime)s - %(levelname)s - %(processName)s (%(process)d) - %(threadName)s - SERVER_MAIN - %(module)s - %(funcName)s - %(lineno)d - %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=log_format_main, force=True if sys.version_info >= (3,8) else False)
    logging.debug("--- Top-level logging configured (Process Pool Main Guard) ---")
    main()