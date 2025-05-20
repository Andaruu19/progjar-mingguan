import os
import json
import base64
from glob import glob
import logging # Added for better debugging

class FileInterface:
    def __init__(self):
        # Ensure the 'files' directory exists, create if not
        if not os.path.exists('files'):
            os.makedirs('files')
            logging.warning("Created 'files' directory.")
        os.chdir('files/')
        logging.info(f"Working directory changed to: {os.getcwd()}")

    def list(self,params=[]):
        try:
            filelist = glob('*.*')
            logging.info(f"Listing files: {filelist}")
            return dict(status='OK',data=filelist)
        except Exception as e:
            logging.error(f"Error in list: {e}")
            return dict(status='ERROR',data=str(e))

    def get(self,params=[]):
        try:
            filename = params[0]
            if (filename == ''):
                logging.warning("Get request with empty filename.")
                return dict(status='ERROR',data='Filename cannot be empty')
            
            # Basic security: prevent directory traversal
            if ".." in filename or "/" in filename or "\\" in filename:
                logging.warning(f"Potential directory traversal attempt: {filename}")
                return dict(status='ERROR', data='Invalid filename.')

            logging.info(f"Attempting to get file: {filename}")
            with open(filename, 'rb') as fp:
                isifile = base64.b64encode(fp.read()).decode()
            logging.info(f"File {filename} retrieved and encoded.")
            return dict(status='OK',data_namafile=filename,data_file=isifile)
        except FileNotFoundError:
            logging.error(f"File not found: {filename}")
            return dict(status='ERROR',data=f'File {filename} not found')
        except Exception as e:
            logging.error(f"Error in get for {filename}: {e}")
            return dict(status='ERROR',data=str(e))

    def upload(self, params=[]):
        if len(params) < 2:
            logging.warning("Upload request with insufficient parameters.")
            return dict(status='ERROR', data='UPLOAD command requires filename and content_base64')
        
        filename = params[0]
        file_content_base64 = params[1]

        # Basic security: prevent directory traversal for filename
        if ".." in filename or "/" in filename or "\\" in filename:
            logging.warning(f"Potential directory traversal attempt on upload: {filename}")
            return dict(status='ERROR', data='Invalid filename for upload.')
            
        try:
            logging.info(f"Attempting to upload file: {filename}")
            # Decode base64 content
            file_content_bytes = base64.b64decode(file_content_base64)
            
            # Write to file in binary mode
            with open(filename, 'wb') as fp:
                fp.write(file_content_bytes)
            
            logging.info(f"File {filename} uploaded successfully.")
            return dict(status='OK', data=f"File {filename} uploaded successfully.")
        except base64.binascii.Error:
            logging.error(f"Error decoding base64 for {filename}.")
            return dict(status='ERROR', data='Invalid base64 content.')
        except Exception as e:
            logging.error(f"Error in upload for {filename}: {e}")
            return dict(status='ERROR', data=str(e))

    def delete(self, params=[]):
        if len(params) < 1:
            logging.warning("Delete request with no filename.")
            return dict(status='ERROR', data='DELETE command requires a filename')
        
        filename = params[0]

        # Basic security: prevent directory traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            logging.warning(f"Potential directory traversal attempt on delete: {filename}")
            return dict(status='ERROR', data='Invalid filename for delete.')

        try:
            logging.info(f"Attempting to delete file: {filename}")
            os.remove(filename)
            logging.info(f"File {filename} deleted successfully.")
            return dict(status='OK', data=f"File {filename} deleted successfully.")
        except FileNotFoundError:
            logging.error(f"File not found for deletion: {filename}")
            return dict(status='ERROR', data=f'File {filename} not found, cannot delete.')
        except Exception as e:
            logging.error(f"Error in delete for {filename}: {e}")
            return dict(status='ERROR', data=str(e))


if __name__=='__main__':
    f = FileInterface()
    print(f.list())
    # print(f.get(['pokijan.jpg'])) # Assuming pokijan.jpg exists in files/
    
    # Test upload (create a dummy file to upload)
    # For this to work, you'd need a base64 string of a file.
    # Let's simulate the client's action:
    try:
        # Simulate creating a file to upload from the client's perspective
        # This file would be outside the 'files' directory initially.
        # For testing file_interface directly, we'll create dummy base64 content
        dummy_content = "This is a test file for upload."
        dummy_content_base64 = base64.b64encode(dummy_content.encode()).decode()
        print("\nTesting UPLOAD:")
        print(f.upload(['test_upload.txt', dummy_content_base64]))
        print(f.list()) # Check if uploaded

        print("\nTesting GET uploaded file:")
        get_result = f.get(['test_upload.txt'])
        if get_result['status'] == 'OK':
            retrieved_content = base64.b64decode(get_result['data_file']).decode()
            print(f"Retrieved content: {retrieved_content}")
            assert retrieved_content == dummy_content
        else:
            print(f"GET failed: {get_result['data']}")


        print("\nTesting DELETE:")
        print(f.delete(['test_upload.txt']))
        print(f.list()) # Check if deleted
        print(f.delete(['non_existent_file.txt'])) # Test deleting non-existent file

    except Exception as e:
        print(f"Error in main test block: {e}")
    
    # Change back to original directory if you ran this standalone
    # This is important if file_interface.py is in the parent directory of 'files'
    # and you ran it directly.
    current_dir = os.getcwd()
    if current_dir.endswith('files'):
        os.chdir('..')
        logging.info(f"Working directory changed back to: {os.getcwd()}")