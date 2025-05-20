# file_server.py

from socket import *
import socket
import threading
import logging # logging imported here
import time
import sys

# --- CONFIGURE LOGGING AT THE VERY TOP ---
# This ensures logging is configured before any other part of the application,
# including module imports that might use logging or the instantiation of global objects.
log_format = '%(asctime)s - %(levelname)s - %(threadName)s - SERVER - %(module)s - %(funcName)s - %(lineno)d - %(message)s'
# Added force=True (Python 3.8+) to remove any existing handlers on the root logger and reconfigure.
# If on Python < 3.8, remove force=True. If issues persist, ensure no other library calls basicConfig.
logging.basicConfig(level=logging.DEBUG, format=log_format, force=True if sys.version_info >= (3, 8) else False)

logging.debug("--- Top-level logging configured ---")

# Import FileProtocol AFTER logging has been configured so its loggers are set up correctly
from file_protocol import FileProtocol
fp = FileProtocol() # fp is a GLOBAL instance

class ProcessTheClient(threading.Thread):
    def __init__(self, connection, address):
        self.connection = connection
        self.address = address
        # It's good practice to get a logger specific to this class or module
        self.logger = logging.getLogger(__name__ + "." + self.__class__.__name__)
        threading.Thread.__init__(self)
        self.logger.debug(f"Initialized for {self.address}")

    def run(self):
        self.logger.info(f"Thread started for {self.address}")
        command_buffer = "" # Buffer to accumulate data
        while True:
            try:
                # It's still okay to read in chunks, as long as we buffer
                data = self.connection.recv(1024) 
                if data:
                    decoded_chunk = data.decode() # Decode once
                    self.logger.debug(f"Received chunk from {self.address}: {decoded_chunk[:60]}{'...' if len(decoded_chunk)>60 else ''}")
                    command_buffer += decoded_chunk
            
                    # Check if the delimiter is in the buffer
                    if "\r\n\r\n" in command_buffer:
                        # Process the complete command (everything up to and including the first delimiter)
                        complete_command, _, rest_of_buffer = command_buffer.partition("\r\n\r\n")
                        command_buffer = rest_of_buffer # Keep any data that came after for the next command (if any)

                        self.logger.info(f"Processing complete command from {self.address}: {complete_command[:100]}{'...' if len(complete_command)>100 else ''}")
                        
                        # Strip potential whitespace from the command itself before processing
                        hasil_json_str = fp.proses_string(complete_command.strip())
                        self.logger.debug(f"fp.proses_string returned for {self.address}: {hasil_json_str[:100]}{'...' if len(hasil_json_str)>100 else ''}")
                        
                        if hasil_json_str is None:
                            self.logger.error(f"fp.proses_string returned None for command: {complete_command[:60]} from {self.address}. Sending generic error.")
                            hasil_json_str = json.dumps({"status": "ERROR", "data": "Internal server processing error (protocol returned None)"})

                        response_to_send = hasil_json_str + "\r\n\r\n" 
                        self.logger.debug(f"Sending response to {self.address}: {response_to_send[:100]}{'...' if len(response_to_send)>100 else ''}")
                        self.connection.sendall(response_to_send.encode())
                        self.logger.debug(f"Response sent to {self.address}")
                else:
                    # No data received, client likely closed connection gracefully
                    self.logger.info(f"Client {self.address} disconnected (recv returned no data).")
                    break
            except ConnectionResetError:
                self.logger.warning(f"Connection reset by client {self.address}.")
                break
            except BrokenPipeError:
                self.logger.warning(f"Broken pipe with client {self.address}. Client may have closed connection abruptly.")
                break
            except UnicodeDecodeError as ude:
                self.logger.error(f"UnicodeDecodeError from {self.address}: {ude}. Client might be sending non-UTF-8 data. Raw data: {data[:60] if 'data' in locals() else 'N/A'}")
                # Consider sending an error back to client if possible, then break
                break
            except Exception as e:
                self.logger.error(f"Generic error processing client {self.address}: {e}", exc_info=True)
                # Optionally send an error response to the client if the connection is still up
                try:
                    # Use a pre-made error JSON to avoid calling fp.proses_string which might have caused the error
                    error_response_dict = {"status": "ERROR", "data": f"Server error during processing: {str(e)}"}
                    error_response_json = json.dumps(error_response_dict)
                    error_response_to_send = error_response_json + "\r\n\r\n"
                    self.connection.sendall(error_response_to_send.encode())
                except Exception as send_err:
                    self.logger.error(f"Failed to send error response to {self.address} after another error: {send_err}")
                break # Stop processing for this client after a generic error
        
        self.logger.info(f"Closing connection with {self.address}")
        self.connection.close()

class Server(threading.Thread):
    def __init__(self,ipaddress='0.0.0.0',port=6666): # Defaulted port to 6666 as used in main
        self.ipinfo=(ipaddress,port)
        self.the_clients = []
        self.logger = logging.getLogger(__name__ + "." + self.__class__.__name__) # Specific logger
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        threading.Thread.__init__(self)
        self.logger.debug(f"Server class initialized for {self.ipinfo}")

    def run(self):
        self.logger.info(f"Server attempting to bind to IP address {self.ipinfo}")
        try:
            self.my_socket.bind(self.ipinfo)
            self.my_socket.listen(5) # Increased backlog slightly
            self.logger.info(f"Server listening on {self.ipinfo}")
        except OSError as e:
            self.logger.critical(f"SERVER FAILED TO BIND to {self.ipinfo}: {e}. Exiting.", exc_info=True)
            return # Exit if bind fails

        while True:
            try:
                self.logger.debug("Server waiting for a new connection...")
                connection, client_address = self.my_socket.accept()
                self.logger.info(f"Accepted connection from {client_address}")

                clt = ProcessTheClient(connection, client_address)
                clt.start()
                self.the_clients.append(clt)
                # Optional: Clean up dead threads from self.the_clients periodically
            except Exception as e:
                self.logger.error(f"Error accepting new connection: {e}", exc_info=True)
                # Potentially add a small delay before retrying accept if it's a persistent issue
                time.sleep(0.1)

def main():
    # logging.basicConfig is now at the top of the module.
    # This log message will use the configuration set at the top.
    main_logger = logging.getLogger(__name__) # Get a logger for the main module context
    main_logger.info("Executing main() function to start server.")
    
    # Port 6666 is used here, ensure Server class __init__ default matches or is overridden
    svr = Server(ipaddress='0.0.0.0', port=6666) 
    svr.start()
    main_logger.info("Server thread started. Main thread will now implicitly wait or could join svr.")
    # If you want the main thread to wait for the server thread (e.g., for cleaner shutdown later):
    # svr.join() 
    # main_logger.info("Server thread has finished.")

if __name__ == "__main__":
    main()