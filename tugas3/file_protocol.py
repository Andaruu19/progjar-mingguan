import json
import logging
import shlex

from file_interface import FileInterface

"""
* class FileProtocol bertugas untuk memproses 
data yang masuk, dan menerjemahkannya apakah sesuai dengan
protokol/aturan yang dibuat

* data yang masuk dari client adalah dalam bentuk bytes yang 
pada akhirnya akan diproses dalam bentuk string

* class FileProtocol akan memproses data yang masuk dalam bentuk
string
"""

class FileProtocol:
    def __init__(self):
        self.file = FileInterface()

    def proses_string(self, string_datamasuk=''):
        # Log the raw string received, but be mindful of very long strings (like base64 data)
        logging.info(f"Proses string dimulai untuk: {string_datamasuk[:100]}{'...' if len(string_datamasuk) > 100 else ''}")

        if not string_datamasuk.strip():
            logging.warning("String kosong diterima.")
            return json.dumps(dict(status='ERROR', data='Perintah kosong diterima'))

        try:
            # 1. Split the original string first (case-sensitive)
            # shlex.split is good as it handles quoted arguments if you ever need them,
            # though for this protocol, simple space splitting is likely enough.
            parts = shlex.split(string_datamasuk)
            
            if not parts: # Should not happen if string_datamasuk is not empty and stripped, but good check
                logging.warning("Gagal mem-parse string, hasil parts kosong.")
                return json.dumps(dict(status='ERROR', data='Gagal mem-parse perintah'))

            # 2. Extract the command part and convert IT ONLY to lowercase
            # The command is the first element.
            c_request_original = parts[0]
            c_request = c_request_original.lower().strip() # Command is case-insensitive
            logging.info(f"Request yang diproses (setelah lower()): {c_request}")

            # 3. The rest of the parts are parameters; keep their original case
            # These parameters will be passed to the FileInterface methods.
            # For UPLOAD, params[0] is filename, params[1] is base64data (case-sensitive)
            # For GET, params[0] is filename (might be case-sensitive depending on OS)
            params = parts[1:]
            
            # Log parameters carefully if they can be very long (like base64 data)
            if params:
                # Log only the first parameter or a snippet if it's too long
                param_log_snippet = str(params[0])[:50] + ('...' if len(str(params[0])) > 50 else '')
                logging.info(f"Parameter untuk '{c_request}': [{param_log_snippet}{', ...' if len(params) > 1 else ''}]")
            else:
                logging.info(f"Tidak ada parameter untuk '{c_request}'")


            # Check if the command (e.g., 'list', 'get', 'upload') exists as a method
            if hasattr(self.file, c_request):
                # Call the method (e.g., self.file.list(params), self.file.upload(params))
                cl = getattr(self.file, c_request)(params)
                return json.dumps(cl)
            else:
                logging.warning(f"Request tidak dikenali: {c_request_original} (diproses sebagai {c_request})")
                return json.dumps(dict(status='ERROR', data=f"Request '{c_request_original}' tidak dikenali"))

        except IndexError:
            # This can happen if shlex.split returns an empty list, or if parts[0] is accessed when parts is empty.
            # Also, if a command expects parameters but none are given, and FileInterface method tries to access params[0].
            logging.error(f"IndexError saat memproses string: '{string_datamasuk}'. Kemungkinan format perintah salah atau parameter kurang.", exc_info=True)
            return json.dumps(dict(status='ERROR', data='Format perintah salah atau parameter kurang'))
        except Exception as e:
            # Catch any other unexpected exceptions during processing
            logging.error(f"Exception umum saat memproses string '{string_datamasuk[:60]}...': {e}", exc_info=True)
            return json.dumps(dict(status='ERROR', data=f'Terjadi kesalahan internal: {str(e)}'))


if __name__=='__main__':
    # Configure logging for testing this module
    logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

    fp = FileProtocol()
    print("\n--- Testing FileProtocol ---")
    print(f"Input: 'LIST', Output: {fp.proses_string('LIST')}")
    print(f"Input: 'list', Output: {fp.proses_string('list')}") # Test case insensitivity for command
    print(f"Input: 'GET pokijan.jpg', Output: {fp.proses_string('GET pokijan.jpg')}")
    print(f"Input: 'Get OtherFile.TXT', Output: {fp.proses_string('Get OtherFile.TXT')}") # Test case for command, preserve for param

    # Simulate an UPLOAD command. Actual base64 would be much longer.
    # The important part is that "VGhpcyBpcyBhIHRlc3QgZmlsZQ==" (Base64) preserves its case.
    test_base64 = "VGhpcyBpcyBhIHRlc3QgZmlsZQ==" # "This is a test file"
    print(f"Input: 'UPLOAD newFile.txt {test_base64}', Output: {fp.proses_string(f'UPLOAD newFile.txt {test_base64}')}")
    print(f"Input: 'upload another.TXT {test_base64}', Output: {fp.proses_string(f'upload another.TXT {test_base64}')}")

    # Test with potentially problematic commands
    print(f"Input: 'UNKNOWNCOMMAND param1 param2', Output: {fp.proses_string('UNKNOWNCOMMAND param1 param2')}")
    print(f"Input: ' ', Output: {fp.proses_string(' ')}") # Empty/whitespace string
    print(f"Input: '', Output: {fp.proses_string('')}")     # Truly empty string

    # Test command that might require params but doesn't get them (FileInterface method would raise error)
    # Assuming GET requires a param. If file_interface.get handles empty params, this will be "OK"
    # otherwise it should be an error from within file_interface, or an IndexError if it expects params[0]
    print(f"Input: 'GET', Output: {fp.proses_string('GET')}")