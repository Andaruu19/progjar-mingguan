import os
import json
import base64
from glob import glob
import logging
BASE_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files')
class FileInterface:
    def __init__(self):
        self.logger = logging.getLogger(__name__ + "." + self.__class__.__name__)
        if not os.path.exists(BASE_FILES_DIR):
            try:
                os.makedirs(BASE_FILES_DIR)
                self.logger.warning(f"Created 'files' directory at: {BASE_FILES_DIR}")
            except OSError as e:
                self.logger.critical(f"Could not create 'files' directory at {BASE_FILES_DIR}: {e}")
        self.logger.info(f"FileInterface initialized. Using base directory: {BASE_FILES_DIR}")
    def _get_full_path(self, filename):
        base_path = os.path.abspath(BASE_FILES_DIR)
        target_path = os.path.abspath(os.path.join(base_path, filename))
        if os.path.commonprefix([target_path, base_path]) != base_path:
            self.logger.warning(f"Potential directory traversal attempt blocked for filename: {filename}")
            return None
        return target_path
    def list(self,params=[]):
        try:
            filelist = [os.path.basename(f) for f in glob(os.path.join(BASE_FILES_DIR, '*.*'))]
            self.logger.info(f"Listing files in {BASE_FILES_DIR}: {filelist}")
            return dict(status='OK',data=filelist)
        except Exception as e:
            self.logger.error(f"Error in list: {e}")
            return dict(status='ERROR',data=str(e))
    def get(self,params=[]):
        if not params:
            self.logger.warning("Get request with no filename parameter.")
            return dict(status='ERROR', data='Filename parameter is required for GET.')
        try:
            filename = params[0]
            if not filename:
                self.logger.warning("Get request with empty filename.")
                return dict(status='ERROR',data='Filename cannot be empty')
            full_path = self._get_full_path(filename)
            if not full_path:
                 return dict(status='ERROR', data='Invalid filename (path traversal suspected).')
            self.logger.info(f"Attempting to get file: {full_path}")
            with open(full_path, 'rb') as fp:
                isifile = base64.b64encode(fp.read()).decode()
            self.logger.info(f"File {filename} retrieved and encoded from {full_path}.")
            return dict(status='OK',data_namafile=filename,data_file=isifile)
        except FileNotFoundError:
            self.logger.error(f"File not found: {filename} (expected at {full_path if 'full_path' in locals() else 'N/A'})")
            return dict(status='ERROR',data=f'File {filename} not found')
        except IndexError:
            self.logger.warning("Get request with no filename parameter (IndexError).")
            return dict(status='ERROR', data='Filename parameter is required for GET.')
        except Exception as e:
            self.logger.error(f"Error in get for {filename}: {e}")
            return dict(status='ERROR',data=str(e))
    def upload(self, params=[]):
        if len(params) < 2:
            self.logger.warning("Upload request with insufficient parameters.")
            return dict(status='ERROR', data='UPLOAD command requires filename and content_base64')
        filename = params[0]
        file_content_base64 = params[1]
        if not filename:
            self.logger.warning("Upload request with empty filename.")
            return dict(status='ERROR', data='Filename for upload cannot be empty.')
        full_path = self._get_full_path(filename)
        if not full_path:
            return dict(status='ERROR', data='Invalid filename for upload (path traversal suspected).')
        try:
            self.logger.info(f"Attempting to upload file to: {full_path}")
            file_content_bytes = base64.b64decode(file_content_base64)
            with open(full_path, 'wb') as fp:
                fp.write(file_content_bytes)
            self.logger.info(f"File {filename} uploaded successfully to {full_path}.")
            return dict(status='OK', data=f"File {filename} uploaded successfully.")
        except base64.binascii.Error:
            self.logger.error(f"Error decoding base64 for {filename}.")
            return dict(status='ERROR', data='Invalid base64 content.')
        except Exception as e:
            self.logger.error(f"Error in upload for {filename} to {full_path}: {e}")
            return dict(status='ERROR', data=str(e))
    def delete(self, params=[]):
        if not params:
            self.logger.warning("Delete request with no filename parameter.")
            return dict(status='ERROR', data='Filename parameter is required for DELETE.')
        try:
            filename = params[0]
            if not filename:
                self.logger.warning("Delete request with empty filename.")
                return dict(status='ERROR', data='Filename for delete cannot be empty.')
            full_path = self._get_full_path(filename)
            if not full_path:
                return dict(status='ERROR', data='Invalid filename for delete (path traversal suspected).')
            self.logger.info(f"Attempting to delete file: {full_path}")
            os.remove(full_path)
            self.logger.info(f"File {filename} deleted successfully from {full_path}.")
            return dict(status='OK', data=f"File {filename} deleted successfully.")
        except FileNotFoundError:
            self.logger.error(f"File not found for deletion: {filename} (expected at {full_path if 'full_path' in locals() else 'N/A'})")
            return dict(status='ERROR',data=f'File {filename} not found, cannot delete.')
        except IndexError:
             self.logger.warning("Delete request with no filename parameter (IndexError).")
             return dict(status='ERROR', data='Filename parameter is required for DELETE.')
        except Exception as e:
            self.logger.error(f"Error in delete for {filename}: {e}")
            return dict(status='ERROR',data=str(e))
if __name__=='__main__':
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')
    print(f"FileInterface standalone test. Base directory: {BASE_FILES_DIR}")
    f = FileInterface()
    print("\nInitial list:")
    print(f.list())
    dummy_content = "This is a test file for standalone FileInterface."
    dummy_content_base64 = base64.b64encode(dummy_content.encode()).decode()
    test_filename = "standalone_test_upload.txt"
    print(f"\nTesting UPLOAD of {test_filename}:")
    print(f.upload([test_filename, dummy_content_base64]))
    print(f.list())
    print(f"\nTesting GET of {test_filename}:")
    get_result = f.get([test_filename])
    print(get_result)
    if get_result['status'] == 'OK':
        retrieved_content = base64.b64decode(get_result['data_file']).decode()
        print(f"Retrieved content: {retrieved_content}")
        assert retrieved_content == dummy_content
    print(f"\nTesting DELETE of {test_filename}:")
    print(f.delete([test_filename]))
    print(f.list())
    print(f.delete(['non_existent_file.txt']))