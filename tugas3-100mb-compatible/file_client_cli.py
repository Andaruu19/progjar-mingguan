# file_client_cli.py
import socket
import json
import base64
import logging
import os # for checking local file existence

# Configure logging for the client
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - CLIENT: %(message)s')

server_address=('172.16.16.101', 6666)

def send_command(command_str=""):
    global server_address
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logging.info(f"Attempting to connect to {server_address}")
    try:
        sock.connect(server_address)
        logging.info(f"Connected to {server_address}")
        
        # --- THIS IS THE CRITICAL FIX ---
        # The command_str from functions like remote_list() is just "LIST"
        # We need to append the protocol's terminator here.
        message_to_send = command_str + "\r\n\r\n"
        # --- END CRITICAL FIX ---
        sock.settimeout(30000.0)

        logging.info(f"Client sending command: {command_str[:100]}{'...' if len(command_str)>100 else ''}") # Log original command
        logging.debug(f"Client raw message being sent: {repr(message_to_send)}") # Log actual message with terminator
        sock.sendall(message_to_send.encode())
        
        data_received=""
        while True:
            data = sock.recv(1048576)
            if data:
                data_received += data.decode()
                # Log chunks received by client for debugging
                logging.debug(f"Client received chunk: {repr(data.decode())}")
                if "\r\n\r\n" in data_received:
                    logging.debug("Client detected end of server message.")
                    break
            else:
                logging.warning("Client: No more data from server (socket closed by peer?).")
                break
        
        # Remove the trailing CRLFCRLF before parsing JSON
        # Ensure data_received is not empty before stripping
        if data_received:
            # Partition to get only the first message if multiple were somehow received (unlikely with this client)
            json_part, _, _ = data_received.partition("\r\n\r\n")
            cleaned_data = json_part.strip() # strip any extra whitespace around the JSON itself
        else:
            cleaned_data = ""
            
        logging.debug(f"Client raw data received from server (before JSON parse): {repr(cleaned_data)}")
        
        if not cleaned_data:
            logging.error("Client received no parsable data from server.")
            return {'status': 'ERROR', 'data': 'No data received from server'}

        hasil = json.loads(cleaned_data)
        logging.info(f"Data received and parsed from server: {hasil}")
        return hasil
    except ConnectionRefusedError:
        logging.error(f"Connection refused by server at {server_address}. Is the server running?")
        return {'status': 'ERROR', 'data': 'Connection refused'}
    except socket.timeout:
        logging.error(f"Connection to {server_address} timed out.")
        return {'status': 'ERROR', 'data': 'Connection timed out'}
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON from server: {e}. Received: {cleaned_data}")
        return {'status': 'ERROR', 'data': f'JSON decode error: {e}. Received: {cleaned_data}'}
    except Exception as e:
        logging.error(f"Error during client communication: {e}", exc_info=True)
        return {'status': 'ERROR', 'data': str(e)}
    finally:
        logging.debug("Client closing socket.")
        sock.close()


def remote_list():
    command_str="LIST"
    hasil = send_command(command_str)
    if hasil and hasil.get('status') == 'OK':
        print("Daftar file di server:")
        if hasil.get('data'):
            for nmfile in hasil['data']:
                print(f"- {nmfile}")
        else:
            print("Tidak ada file.")
        return True
    else:
        error_msg = hasil.get('data', 'Unknown error') if hasil else "No response from server"
        print(f"Gagal menampilkan daftar file: {error_msg}")
        return False

def remote_get(filename="", destination_folder="downloaded_files"):
    command_str=f"GET {filename}"
    hasil = send_command(command_str)
    if hasil and hasil.get('status') == 'OK':
        namafile_server = hasil.get('data_namafile')
        isifile_base64 = hasil.get('data_file')
        
        if not namafile_server or not isifile_base64:
            print("Gagal: Respons server tidak lengkap.")
            return False
            
        # Create destination folder if it doesn't exist
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)
            
        local_filepath = os.path.join(destination_folder, namafile_server)
        
        try:
            isifile_bytes = base64.b64decode(isifile_base64)
            with open(local_filepath, 'wb+') as fp:
                fp.write(isifile_bytes)
            print(f"File {namafile_server} berhasil diunduh ke {local_filepath}")
            return True
        except base64.binascii.Error:
            print("Gagal: Error decoding base64 content dari server.")
            return False
        except Exception as e:
            print(f"Gagal menyimpan file: {e}")
            return False
    else:
        error_msg = hasil.get('data', 'Unknown error') if hasil else "No response from server"
        print(f"Gagal mendapatkan file {filename}: {error_msg}")
        return False

def remote_upload(local_filepath, server_filename=""):
    if not os.path.exists(local_filepath):
        print(f"Gagal: File lokal {local_filepath} tidak ditemukan.")
        return False

    if not server_filename:
        server_filename = os.path.basename(local_filepath) # Use local filename if server_filename not provided

    try:
        with open(local_filepath, 'rb') as f:
            file_content_bytes = f.read()
        
        file_content_base64 = base64.b64encode(file_content_bytes).decode()
        
        command_str = f"UPLOAD {server_filename} {file_content_base64}"
        hasil = send_command(command_str)
        
        if hasil and hasil.get('status') == 'OK':
            print(f"File {local_filepath} berhasil diupload ke server sebagai {server_filename}: {hasil.get('data')}")
            return True
        else:
            error_msg = hasil.get('data', 'Unknown error') if hasil else "No response from server"
            print(f"Gagal mengupload file {local_filepath}: {error_msg}")
            return False
            
    except Exception as e:
        print(f"Error saat proses upload: {e}")
        return False

def remote_delete(filename_on_server):
    if not filename_on_server:
        print("Gagal: Nama file di server tidak boleh kosong untuk dihapus.")
        return False
        
    command_str = f"DELETE {filename_on_server}"
    hasil = send_command(command_str)
    
    if hasil and hasil.get('status') == 'OK':
        print(f"File {filename_on_server} berhasil dihapus dari server: {hasil.get('data')}")
        return True
    else:
        error_msg = hasil.get('data', 'Unknown error') if hasil else "No response from server"
        print(f"Gagal menghapus file {filename_on_server}: {error_msg}")
        return False

if __name__=='__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - CLIENT: %(message)s')

    server_address=('172.16.16.101', 6666) 
    
    uploadfilename = "dummy_100mb.bin"
    serverfilename = "dummy100mb.bin"

    if not os.path.exists(uploadfilename):
        print(f"ERROR: File lokal '{uploadfilename}' tidak ditemukan. Silakan periksa path.")
        print("Skipping JPEG upload tests.")
    else:
        print(f"File lokal '{uploadfilename}' ditemukan.")

        # 1. List files on server (initial state)
        print("\n1. LIST file di server:")
        remote_list()

        # 2. Upload file
        print(f"\n2. UPLOAD file '{uploadfilename}' ke server sebagai '{serverfilename}':")
        remote_upload(uploadfilename, serverfilename)

        # 3. List files again to see
        print("\n3. LIST file di server:")
        remote_list()

        # 4. Delete
        print(f"\n5. DELETE file '{serverfilename}' dari server:")
        remote_delete(serverfilename)

        # 5. List files again to confirm deletion
        print("\n6. LIST file di server:")
        remote_list()