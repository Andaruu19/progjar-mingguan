import sys
import socket
import logging
import threading

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] (%(threadName)-10s) %(message)s')

def kirim_data(nama_thread, pesan_untuk_dikirim):
    logging.info(f"Thread {nama_thread}: memulai")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logging.debug(f"Thread {nama_thread}: membuka socket")

    server_address = ('172.16.16.101', 45000)
    logging.info(f"Thread {nama_thread}: mencoba koneksi ke {server_address}")
    
    try:
        sock.connect(server_address)
        logging.info(f"Thread {nama_thread}: koneksi berhasil")

        message = pesan_untuk_dikirim
        logging.info(f"Thread {nama_thread}: mengirim -> '{message}'")
        sock.sendall(message.encode())
        amount_received = 0
        amount_expected = len(message)
        received_data_chunks = []
        
        logging.info(f"Thread {nama_thread}: menunggu balasan, mengharapkan {amount_expected} bytes...")

        while amount_received < amount_expected:
            data = sock.recv(32)
            if not data:
                logging.warning(f"Thread {nama_thread}: koneksi ditutup oleh server sebelum semua data diterima.")
                break
            received_data_chunks.append(data)
            amount_received += len(data)
            logging.debug(f"Thread {nama_thread}: menerima partial -> {data}")
        
        full_response = b''.join(received_data_chunks).decode(errors='ignore')
        logging.info(f"Thread {nama_thread}: diterima dari server <- '{full_response}'")

    except socket.error as e:
        logging.error(f"Thread {nama_thread}: Socket error -> {e}")
    except Exception as e:
        logging.error(f"Thread {nama_thread}: Exception -> {e}")
    finally:
        logging.info(f"Thread {nama_thread}: menutup socket")
        sock.close()
    return


if __name__=='__main__':
    if len(sys.argv) < 2:
        print(f"Penggunaan: python {sys.argv[0]} \"PESAN_ANDA\"")
        sys.exit(1)

    pesan_dari_argumen = sys.argv[1]

    threads = []
    jumlah_thread = 3
    
    for i in range(jumlah_thread):
        nama_identifier_thread = f"Client-{i+1}"
        t = threading.Thread(target=kirim_data, args=(nama_identifier_thread, pesan_dari_argumen))
        threads.append(t)
        t.start()

    for thr in threads:
        thr.join()
    
    logging.info("Semua thread telah selesai.")