import json
import logging
from file_interface import FileInterface
class FileProtocol:
    def __init__(self):
        self.file = FileInterface()
    def proses_string(self, string_datamasuk=''):
        logging.info(f"Proses string dimulai untuk: {string_datamasuk[:100]}{'...' if len(string_datamasuk) > 100 else ''}")
        if not string_datamasuk.strip():
            logging.warning("String kosong diterima.")
            return json.dumps(dict(status='ERROR', data='Perintah kosong diterima'))
        try:
            parts = string_datamasuk.split(None, 2)
            if not parts:
                logging.warning("Gagal mem-parse string (split menghasilkan list kosong).")
                return json.dumps(dict(status='ERROR', data='Gagal mem-parse perintah'))
            c_request_original = parts[0]
            c_request = c_request_original.lower().strip()
            logging.info(f"Request yang diproses (setelah lower()): {c_request}")
            params = []
            if len(parts) > 1:
                params.append(parts[1])
            if len(parts) > 2:
                params.append(parts[2])
            if params:
                param_log_snippet = str(params[0])[:50] + ('...' if len(str(params[0])) > 50 else '')
                logging.info(f"Parameter untuk '{c_request}': [{param_log_snippet}{', ...' if len(params) > 1 else ''}]")
            else:
                logging.info(f"Tidak ada parameter untuk '{c_request}'")
            if hasattr(self.file, c_request):
                cl = getattr(self.file, c_request)(params)
                return json.dumps(cl)
            else:
                logging.warning(f"Request tidak dikenali: {c_request_original} (diproses sebagai {c_request})")
                return json.dumps(dict(status='ERROR', data=f"Request '{c_request_original}' tidak dikenali"))
        except IndexError:
            logging.error(f"IndexError saat memproses string: '{string_datamasuk}'. Kemungkinan format perintah salah atau parameter kurang.", exc_info=True)
            return json.dumps(dict(status='ERROR', data='Format perintah salah atau parameter kurang'))
        except Exception as e:
            logging.error(f"Exception umum saat memproses string '{string_datamasuk[:60]}...': {e}", exc_info=True)
            return json.dumps(dict(status='ERROR', data=f'Terjadi kesalahan internal: {str(e)}'))
if __name__=='__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')
    fp = FileProtocol()
    print("\n--- Testing FileProtocol ---")
    print(f"Input: 'LIST', Output: {fp.proses_string('LIST')}")
    print(f"Input: 'list', Output: {fp.proses_string('list')}")
    print(f"Input: 'GET pokijan.jpg', Output: {fp.proses_string('GET pokijan.jpg')}")
    print(f"Input: 'Get OtherFile.TXT', Output: {fp.proses_string('Get OtherFile.TXT')}")
    test_base64 = "VGhpcyBpcyBhIHRlc3QgZmlsZQ=="
    print(f"Input: 'UPLOAD newFile.txt {test_base64}', Output: {fp.proses_string(f'UPLOAD newFile.txt {test_base64}')}")
    print(f"Input: 'upload another.TXT {test_base64}', Output: {fp.proses_string(f'upload another.TXT {test_base64}')}")
    print(f"Input: 'UNKNOWNCOMMAND param1 param2', Output: {fp.proses_string('UNKNOWNCOMMAND param1 param2')}")
    print(f"Input: ' ', Output: {fp.proses_string(' ')}")
    print(f"Input: '', Output: {fp.proses_string('')}")
    print(f"Input: 'GET', Output: {fp.proses_string('GET')}")