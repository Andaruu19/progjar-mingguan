# file_client_cli_benchmark.py
import socket
import json
import base64
import logging
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import sys
from enum import Enum

# --- Global Configuration & Functions lainnya tetap sama ---
# (send_command, remote_upload, remote_get, client_worker_task, analyze_and_print_stats, create_dummy_file_if_not_exists)
# Pastikan fungsi-fungsi tersebut adalah versi stabil Anda.
# Saya akan menyertakan kerangkanya untuk kelengkapan, Anda bisa mengisi detailnya.

server_ip_global = None
server_port_global = None
client_logger_global = None 

class OperationType(Enum):
    UPLOAD = "UPLOAD"
    GET = "GET"

raw_stats_data = [] 
stats_lock = threading.Lock()

def send_command(command_str="", task_id="N/A", operation_type="UNKNOWN_OP"):
    # ... (Implementasi send_command Anda yang sudah stabil) ...
    global server_ip_global, server_port_global, client_logger_global
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(600.0)
    current_thread_id = threading.get_ident()
    log_prefix = f"Task {task_id} ({operation_type} Thr {current_thread_id})"
    client_logger_global.debug(f"{log_prefix}: Connecting to {server_ip_global}:{server_port_global}")
    try:
        sock.connect((server_ip_global, server_port_global))
        client_logger_global.debug(f"{log_prefix}: Connected.")
        message_to_send = command_str + "\r\n\r\n"
        if client_logger_global.isEnabledFor(logging.DEBUG): client_logger_global.info(f"{log_prefix}: Sending cmd: {command_str[:60]}{'...' if len(command_str)>60 else ''}")
        client_logger_global.debug(f"{log_prefix}: Raw msg (first 60): {repr(message_to_send[:60])}")
        sock.sendall(message_to_send.encode())
        client_logger_global.debug(f"{log_prefix}: sendall completed.")
        data_received_chunks = []
        buffer_size = 1048576
        while True:
            data = sock.recv(buffer_size)
            if data:
                data_received_chunks.append(data)
                client_logger_global.debug(f"{log_prefix}: Recv chunk len: {len(data)}")
                try:
                    if b"\r\n\r\n" in data_received_chunks[-1] or \
                       (len(data_received_chunks) > 1 and b"\r\n\r\n" in data_received_chunks[-2] + data_received_chunks[-1]):
                        temp_buffer_str_check = b"".join(data_received_chunks).decode(errors='ignore')
                        if "\r\n\r\n" in temp_buffer_str_check:
                            client_logger_global.debug(f"{log_prefix}: Detected EOM.")
                            break
                except UnicodeDecodeError: client_logger_global.debug(f"{log_prefix}: Temp UnicodeDecodeError, continuing recv.")
            else: client_logger_global.warning(f"{log_prefix}: No more data (socket closed by peer?)."); break
        data_received_bytes = b"".join(data_received_chunks)
        try: data_received_str = data_received_bytes.decode()
        except UnicodeDecodeError as e: client_logger_global.error(f"{log_prefix}: Final UnicodeDecodeError: {e}. Data: {data_received_bytes[:200]}..."); return {'status': 'ERROR', 'data': 'Unicode decode error on final receive buffer'}
        if data_received_str: json_part, _, _ = data_received_str.partition("\r\n\r\n"); cleaned_data = json_part.strip()
        else: cleaned_data = ""
        client_logger_global.debug(f"{log_prefix}: Raw data from server (first 70): {repr(cleaned_data[:70])}")
        if not cleaned_data: client_logger_global.error(f"{log_prefix}: No parsable data from server."); return {'status': 'ERROR', 'data': 'No data received/parsed'}
        hasil = json.loads(cleaned_data)
        # if client_logger_global.isEnabledFor(logging.DEBUG): client_logger_global.info(f"{log_prefix}: Parsed resp: {str(hasil)[:100]}{'...' if len(str(hasil))>100 else ''}")
        return hasil
    except socket.timeout: client_logger_global.error(f"{log_prefix}: Socket op timeout."); return {'status': 'ERROR', 'data': 'Socket timeout'}
    except ConnectionRefusedError: client_logger_global.error(f"{log_prefix}: Connection refused."); return {'status': 'ERROR', 'data': 'Connection refused'}
    except json.JSONDecodeError as e: client_logger_global.error(f"{log_prefix}: Failed to decode JSON: {e}. Received: {cleaned_data[:200]}..."); return {'status': 'ERROR', 'data': f'JSON decode error: {e}'}
    except Exception as e: client_logger_global.error(f"{log_prefix}: Exception in send_command: {e}", exc_info=True); return {'status': 'ERROR', 'data': str(e)}
    finally: client_logger_global.debug(f"{log_prefix}: Closing socket."); sock.close()

def remote_upload(local_filepath, server_filename, task_id="N/A"):
    # ... (Implementasi remote_upload Anda yang sudah stabil) ...
    global client_logger_global
    log_prefix = f"Task {task_id} (UPLOAD)"
    if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info(f"{log_prefix}: Starting: {local_filepath} -> {server_filename}")
    start_time = time.perf_counter(); bytes_processed = 0; success = False
    if not os.path.exists(local_filepath): client_logger_global.error(f"{log_prefix}: Local file {local_filepath} not found."); return success, time.perf_counter() - start_time, bytes_processed
    try:
        file_size = os.path.getsize(local_filepath)
        client_logger_global.debug(f"{log_prefix}: Reading local file '{local_filepath}' (size: {file_size} bytes)...")
        with open(local_filepath, 'rb') as f: file_content_bytes = f.read()
        client_logger_global.debug(f"{log_prefix}: Read {len(file_content_bytes)} bytes. Encoding Base64...")
        file_content_base64 = base64.b64encode(file_content_bytes).decode()
        client_logger_global.debug(f"{log_prefix}: Base64 len: {len(file_content_base64)}. Sending UPLOAD...")
        command_str = f"UPLOAD {server_filename} {file_content_base64}"
        del file_content_bytes, file_content_base64 
        hasil = send_command(command_str, task_id, OperationType.UPLOAD.value)
        if hasil and hasil.get('status') == 'OK': success = True; bytes_processed = file_size
        if success and client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info(f"{log_prefix}: SUCCESS. Server: {hasil.get('data')}")
        elif not success: client_logger_global.error(f"{log_prefix}: FAILED. Server: {hasil.get('data', 'No/Bad Resp') if hasil else 'No Resp'}")
    except MemoryError: client_logger_global.critical(f"{log_prefix}: MemoryError for {local_filepath}.")
    except Exception as e: client_logger_global.error(f"{log_prefix}: Exception: {e}", exc_info=True)
    duration = time.perf_counter() - start_time
    client_logger_global.debug(f"{log_prefix}: Finished in {duration:.3f}s. Success: {success}")
    return success, duration, bytes_processed

def remote_get(filename_on_server, local_save_dir, task_id="N/A"):
    # ... (Implementasi remote_get Anda yang sudah stabil) ...
    global client_logger_global
    log_prefix = f"Task {task_id} (GET)"
    if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info(f"{log_prefix}: Starting for {filename_on_server}")
    start_time = time.perf_counter(); bytes_processed = 0; success = False
    command_str = f"GET {filename_on_server}"
    hasil = send_command(command_str, task_id, OperationType.GET.value)
    if hasil and hasil.get('status') == 'OK':
        namafile_server = hasil.get('data_namafile'); isifile_base64 = hasil.get('data_file')
        if not namafile_server or not isifile_base64: client_logger_global.error(f"{log_prefix}: FAILED. Incomplete GET response.")
        else:
            if not os.path.exists(local_save_dir):
                try: os.makedirs(local_save_dir)
                except OSError as e: client_logger_global.error(f"{log_prefix}: FAILED to create dir {local_save_dir}: {e}"); return success, time.perf_counter() - start_time, bytes_processed
            local_filepath = os.path.join(local_save_dir, namafile_server)
            try:
                client_logger_global.debug(f"{log_prefix}: Decoding Base64 (len: {len(isifile_base64)}) for {namafile_server}...")
                isifile_bytes = base64.b64decode(isifile_base64); bytes_processed = len(isifile_bytes)
                client_logger_global.debug(f"{log_prefix}: Writing {bytes_processed} bytes to {local_filepath}...")
                with open(local_filepath, 'wb') as fp: fp.write(isifile_bytes)
                success = True
                if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info(f"{log_prefix}: SUCCESS to {local_filepath}.")
            except base64.binascii.Error as e: client_logger_global.error(f"{log_prefix}: FAILED Base64 decode: {e}")
            except Exception as e: client_logger_global.error(f"{log_prefix}: FAILED saving file: {e}", exc_info=True)
    else: client_logger_global.error(f"{log_prefix}: FAILED. Server: {hasil.get('data', 'No/Bad Resp') if hasil else 'No Resp'}")
    duration = time.perf_counter() - start_time
    client_logger_global.debug(f"{log_prefix}: Finished in {duration:.3f}s. Success: {success}")
    return success, duration, bytes_processed

def remote_delete(filename_on_server, task_id="N/A_DEL_DUMMY"): # Tambahkan task_id
    global client_logger_global # Pastikan logger global bisa diakses
    log_prefix = f"Task {task_id} (DELETE_FN)"
    # Implementasi lengkap remote_delete Anda di sini
    # Contoh sederhana:
    if not filename_on_server:
        client_logger_global.error(f"{log_prefix}: Filename cannot be empty for delete.")
        return False, 0 # success, duration

    command_str = f"DELETE {filename_on_server}"
    start_time = time.perf_counter()
    hasil = send_command(command_str, task_id, "DELETE_OP") # Pastikan OperationType.DELETE jika ada
    duration = time.perf_counter() - start_time

    if hasil and hasil.get('status') == 'OK':
        if client_logger_global.isEnabledFor(logging.INFO):
            client_logger_global.info(f"{log_prefix}: SUCCESS for {filename_on_server}. Server: {hasil.get('data')}")
        return True, duration
    else:
        error_msg = hasil.get('data', 'Unknown error') if hasil else "No response"
        client_logger_global.error(f"{log_prefix}: FAILED for {filename_on_server}. Server: {error_msg}")
        return False, duration

def client_worker_task(task_id, local_file_path, server_filename_for_this_task, operations_to_run): # server_filename_base diubah jadi server_filename_for_this_task
    global client_logger_global, raw_stats_data, stats_lock
    if client_logger_global.isEnabledFor(logging.INFO):
        client_logger_global.info(f"Task {task_id}: Starting worker for file {local_file_path} -> server file {server_filename_for_this_task}")
    
    if not os.path.exists(local_file_path):
        client_logger_global.error(f"Task {task_id}: Local file {local_file_path} missing. Aborting.")
        with stats_lock: raw_stats_data.append({"task_id": task_id, "operation": "PREP_FAIL", "file_size": 0, "status": "FAILED", "duration": 0, "bytes_processed": 0})
        return
        
    actual_file_size_bytes = os.path.getsize(local_file_path)
    file_size_mb = actual_file_size_bytes / (1024 * 1024)

    if OperationType.UPLOAD in operations_to_run:
        if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info(f"Task {task_id}: === UPLOAD PHASE ({file_size_mb:.0f}MB) ===")
        upload_ok, up_time, up_bytes = remote_upload(local_file_path, server_filename_for_this_task, task_id)
        with stats_lock: raw_stats_data.append({"task_id": task_id, "operation": OperationType.UPLOAD.value, "file_size": actual_file_size_bytes, "status": "SUCCESS" if upload_ok else "FAILED", "duration": up_time, "bytes_processed": up_bytes if upload_ok else 0})
        
        if upload_ok and OperationType.GET in operations_to_run:
            if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info(f"Task {task_id}: === GET PHASE ({file_size_mb:.0f}MB) ===")
            download_dir_for_task = f"bm_downloads_task_{task_id}" # Unik per task
            if os.path.exists(download_dir_for_task):
                try:
                    for f_name in os.listdir(download_dir_for_task): os.remove(os.path.join(download_dir_for_task, f_name))
                    os.rmdir(download_dir_for_task)
                except OSError as e: client_logger_global.warning(f"Task {task_id}: Could not clean up download dir '{download_dir_for_task}': {e}")
            get_ok, get_time, get_bytes = remote_get(server_filename_for_this_task, download_dir_for_task, task_id)
            with stats_lock: raw_stats_data.append({"task_id": task_id, "operation": OperationType.GET.value, "file_size": get_bytes, "status": "SUCCESS" if get_ok else "FAILED", "duration": get_time, "bytes_processed": get_bytes if get_ok else 0})
    
    elif OperationType.GET in operations_to_run: # Hanya GET
        if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info(f"Task {task_id}: === GET PHASE (standalone, {file_size_mb:.0f}MB) using {server_filename_for_this_task} ===")
        download_dir_for_task = f"bm_downloads_task_{task_id}"
        # ... (logika pembersihan direktori download sama) ...
        get_ok, get_time, get_bytes = remote_get(server_filename_for_this_task, download_dir_for_task, task_id)
        with stats_lock: raw_stats_data.append({"task_id": task_id, "operation": OperationType.GET.value, "file_size": get_bytes, "status": "SUCCESS" if get_ok else "FAILED", "duration": get_time, "bytes_processed": get_bytes if get_ok else 0})
    
    if client_logger_global.isEnabledFor(logging.INFO):
        client_logger_global.info(f"Task {task_id}: Worker finished.")

# ... (analyze_and_print_stats dan create_dummy_file_if_not_exists sama)
def analyze_and_print_stats(config_description, overall_config_start_time):
    global client_logger_global, raw_stats_data
    overall_duration = time.perf_counter() - overall_config_start_time
    if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info(f"Analyzing benchmark statistics for: {config_description}")
    successful_client_worker_tasks = 0; failed_client_worker_tasks = 0
    worker_task_success_status = {}
    for record in raw_stats_data:
        task_id = record["task_id"]
        if record["status"] != "SUCCESS" and record["operation"] != "PREP_FAIL": worker_task_success_status[task_id] = False
        elif task_id not in worker_task_success_status: worker_task_success_status[task_id] = True
    for status in worker_task_success_status.values():
        if status: successful_client_worker_tasks +=1
        else: failed_client_worker_tasks +=1
    op_stats = {}
    for record in raw_stats_data:
        op = record["operation"]
        if op == "PREP_FAIL": continue
        if op not in op_stats: op_stats[op] = {"success_count": 0, "fail_count": 0, "total_duration": 0, "total_bytes": 0, "durations": [], "throughputs_mb_s": []}
        op_stats[op]["total_duration"] += record["duration"]
        if record["status"] == "SUCCESS":
            op_stats[op]["success_count"] += 1; op_stats[op]["total_bytes"] += record["bytes_processed"]; op_stats[op]["durations"].append(record["duration"])
            if record["duration"] > 1e-9 and record["bytes_processed"] > 0: op_stats[op]["throughputs_mb_s"].append((record["bytes_processed"] / (1024*1024)) / record["duration"])
        else: op_stats[op]["fail_count"] += 1
    print("\n" + "="*15 + f" BENCHMARK RESULTS FOR: {config_description} " + "="*15)
    print(f"Total Duration for this Configuration: {overall_duration:.3f} seconds")
    print("-" * 70); print("Client Worker Task Summary:")
    print(f"  Total Client Worker Tasks Processed: {len(worker_task_success_status)}")
    print(f"  Successful Client Worker Tasks (all ops OK): {successful_client_worker_tasks}")
    print(f"  Failed Client Worker Tasks (at least one op FAILED): {failed_client_worker_tasks}")
    print("-" * 70); print("Operational Statistics:")
    for op_name_val, stats in op_stats.items():
        print(f"  Operation: {op_name_val}")
        print(f"    Successful Ops: {stats['success_count']}; Failed Ops: {stats['fail_count']}")
        if stats['success_count'] > 0:
            avg_duration_op = sum(stats['durations']) / len(stats['durations'])
            print(f"    Avg Duration per Successful Op: {avg_duration_op:.3f} s")
            if stats['throughputs_mb_s']:
                 avg_throughput_op_mb_s = sum(stats['throughputs_mb_s']) / len(stats['throughputs_mb_s'])
                 print(f"    Avg Throughput per Successful Op: {avg_throughput_op_mb_s:.2f} MB/s")
            if stats['total_duration'] > 1e-9:
                aggregate_op_throughput_mb_s = (stats['total_bytes'] / (1024*1024)) / stats['total_duration']
                print(f"    Aggregate Throughput for {op_name_val} (Successful Bytes / Total Op Duration): {aggregate_op_throughput_mb_s:.2f} MB/s")
        print("-" * 40)
    print("=" * (30 + len(f" BENCHMARK RESULTS FOR: {config_description} ") + 30))
    if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info("Benchmark analysis complete for this configuration.")

def create_dummy_file_if_not_exists(filename, size_in_mb):
    global client_logger_global
    if not os.path.exists(filename):
        print(f"File '{filename}' tidak ditemukan. Mencoba membuat ({size_in_mb}MB)...")
        if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info(f"Benchmark file '{filename}' not found. Attempting to create.")
        try:
            chunk_size = 1024 * 1024; os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
            with open(filename, 'wb') as f:
                for _ in range(size_in_mb): f.write(os.urandom(chunk_size)) 
            print(f"Berhasil membuat file '{filename}'.")
            if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info(f"Auto-created dummy file '{filename}'.")
            return True
        except Exception as e_create:
            print(f"Gagal membuat file '{filename}': {e_create}")
            client_logger_global.error(f"Failed to auto-create '{filename}': {e_create}. Skipping.")
            return False
    return True

def main():
    global server_ip_global, server_port_global, client_logger_global, raw_stats_data

    parser = argparse.ArgumentParser(description="Automated File Client Benchmark Tool")
    parser.add_argument("server_ip", help="IP address of the file server")
    parser.add_argument("server_port", type=int, help="Port number of the file server")
    
    # Argumen -c dan -s akan menentukan list konfigurasi yang diiterasi
    parser.add_argument("-c", "--client_workers_list", nargs='+', type=int, default=[1, 5, 50], 
                        help="Space-separated list of concurrent client worker counts to test (default: 1 5 50)")
    parser.add_argument("-s", "--file_sizes_mb_list", nargs='+', type=int, default=[10, 50, 100], 
                        help="Space-separated list of file sizes in MB to test (default: 10 50 100). Files dummy_{size}mb.bin must exist/will be created.")
    
    parser.add_argument("-o", "--operations", nargs='+', choices=[op.value for op in OperationType], default=["UPLOAD", "GET"],
                        help=f"Space-separated list of operations (default: UPLOAD GET). Choices: {[op.value for op in OperationType]}")
    
    # Argumen -n sekarang akan diabaikan karena jumlah task = jumlah worker
    # parser.add_argument("-n", "--num_tasks_per_config", type=int, default=5, 
    #                     help="Number of tasks (cycles) for EACH configuration (default: 5)")
    
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG level logging (overrides -q)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress INFO and DEBUG logs, show only benchmark results and errors/warnings.")
    parser.add_argument("--log_file", type=str, default=None, help="Path to save client log output")
    
    cli_args = parser.parse_args()

    if cli_args.quiet and not cli_args.verbose: log_level = logging.WARNING
    elif cli_args.verbose: log_level = logging.DEBUG
    else: log_level = logging.INFO
    handlers = [logging.StreamHandler(sys.stdout)]
    if cli_args.log_file:
        log_dir = os.path.dirname(cli_args.log_file)
        if log_dir and not os.path.exists(log_dir): os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(cli_args.log_file, mode='w'))
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(threadName)s - CLIENT - %(funcName)s:%(lineno)d - %(message)s', handlers=handlers)
    client_logger_global = logging.getLogger(__name__)

    server_ip_global = cli_args.server_ip
    server_port_global = cli_args.server_port
    
    try: operations_to_run_enums = [OperationType(op_str) for op_str in cli_args.operations]
    except ValueError as e: client_logger_global.critical(f"Invalid operation: {e}. Choices: {[op.value for op in OperationType]}"); sys.exit(1)

    client_worker_configs_cli = cli_args.client_workers_list
    file_size_configs_mb_cli = cli_args.file_sizes_mb_list

    print("="*10 + " Starting Benchmark Suite " + "="*10)
    if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info("="*10 + " Starting Benchmark Suite " + "="*10)

    for file_size_mb in file_size_configs_mb_cli:
        for num_workers in client_worker_configs_cli: 
            local_file_to_use = f"dummy_{file_size_mb}mb.bin"
            # server_filename_base sudah unik per konfigurasi worker & ukuran file
            server_filename_base_for_config = f"bm_s{file_size_mb}mb_w{num_workers}" 

            if not create_dummy_file_if_not_exists(local_file_to_use, file_size_mb):
                client_logger_global.error(f"Cannot proceed: Workers={num_workers}, FileSize={file_size_mb}MB. Dummy file missing/creation failed.")
                continue 

            # Jumlah task sekarang sama dengan jumlah worker untuk konfigurasi ini
            actual_num_tasks_for_this_config = num_workers

            config_desc = f"FileSize={file_size_mb}MB, Workers={num_workers}, Ops={cli_args.operations}, Tasks={actual_num_tasks_for_this_config}"
            print(f"\n>>> RUNNING BENCHMARK: {config_desc} <<<")
            if client_logger_global.isEnabledFor(logging.INFO):
                 client_logger_global.info(f"\n>>> BENCHMARKING CONFIGURATION: {config_desc} <<<")
            
            raw_stats_data = [] 
            overall_config_start_time = time.perf_counter()

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = []
                for i in range(actual_num_tasks_for_this_config): # Loop sebanyak num_workers
                    # ID task untuk logging dan nama file server unik per worker/task
                    task_id_str = f"S{file_size_mb}-W{num_workers}-Task{i+1}" 
                    # Nama file di server dibuat unik untuk setiap task/worker
                    server_file_for_this_task = f"{server_filename_base_for_config}_task{i+1}"

                    futures.append(executor.submit(client_worker_task, 
                                                  task_id_str, 
                                                  local_file_to_use, 
                                                  server_file_for_this_task, 
                                                  operations_to_run_enums))
                
                num_completed_futures = 0
                for future in as_completed(futures):
                    num_completed_futures +=1
                    client_logger_global.debug(f"Future {num_completed_futures}/{len(futures)} completed for config: {config_desc}.")
                    try: future.result() 
                    except Exception as e_task: client_logger_global.error(f"Task (from config {config_desc}) raised an unhandled exception in future: {e_task}", exc_info=False)
            
            analyze_and_print_stats(config_desc, overall_config_start_time)

    print("="*10 + " Benchmark Suite Finished " + "="*10)
    if client_logger_global.isEnabledFor(logging.INFO): client_logger_global.info("="*10 + " Benchmark Suite Finished " + "="*10)

if __name__ == '__main__':
    main()