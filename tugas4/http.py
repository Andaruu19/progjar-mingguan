import sys
import os
import os.path
from datetime import datetime
import urllib.parse

class HttpServer:
    def __init__(self):
        self.sessions = {}
        self.types = {}
        self.types['.pdf'] = 'application/pdf'
        self.types['.jpg'] = 'image/jpeg'
        self.types['.jpeg'] = 'image/jpeg'
        self.types['.png'] = 'image/png'
        self.types['.txt'] = 'text/plain'
        self.types['.html'] = 'text/html'
        self.types['.css'] = 'text/css'
        self.types['.js'] = 'application/javascript'
        
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.upload_dir = os.path.join(self.base_dir, 'uploads')

        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)

    def response(self, kode=404, message='Not Found', messagebody=b'', headers={}):
        tanggal = datetime.now().strftime('%c')
        resp = []
        resp.append(f"HTTP/1.0 {kode} {message}\r\n")
        resp.append(f"Date: {tanggal}\r\n")
        resp.append("Connection: close\r\n")
        resp.append("Server: myserver/1.0\r\n")
        resp.append(f"Content-Length: {len(messagebody)}\r\n")
        for kk in headers:
            resp.append(f"{kk}: {headers[kk]}\r\n")
        resp.append("\r\n")

        response_headers = "".join(resp)
        
        if not isinstance(messagebody, bytes):
            messagebody = messagebody.encode()

        return response_headers.encode() + messagebody

    def proses(self, data):
        request_parts = data.split(b"\r\n\r\n", 1)
        headers_bytes = request_parts[0]
        body_bytes = request_parts[1] if len(request_parts) > 1 else b''

        headers_str = headers_bytes.decode('utf-8', 'ignore')
        requests = headers_str.split("\r\n")
        
        baris = requests[0]
        all_headers = {line.split(": ", 1)[0]: line.split(": ", 1)[1] for line in requests[1:] if ": " in line}

        try:
            method, object_address, _ = baris.split(" ", 2)
            method = method.upper().strip()
            object_address = object_address.strip()
        except ValueError:
            return self.response(400, 'Bad Request', b'Malformed request line', {})

        if method == 'GET':
            return self.http_get(object_address, all_headers)
        if method == 'POST':
            return self.http_post(object_address, all_headers, body_bytes)
        if method == 'DELETE':
            return self.http_delete(object_address, all_headers)
        
        return self.response(400, 'Bad Request', b'Unsupported method', {})

    def http_get(self, object_address, headers):
        if object_address == '/':
             return self.response(302, 'Found', b'', {'Location': '/index.html'})

        if object_address == '/files':
            files = sorted(os.listdir(self.upload_dir))
            file_list_html = "<h2>Daftar File di 'uploads'</h2><ul>"
            if not files:
                file_list_html += "<li><i>Tidak ada file yang diupload.</i></li>"
            else:
                for f in files:
                    file_list_html += f"<li><a href='/uploads/{f}' target='_blank'>{f}</a> <button class='delete-btn' data-filename='{f}'>Hapus</button></li>"
            file_list_html += "</ul>"
            
            return self.response(200, 'OK', file_list_html, {'Content-Type': 'text/html'})

        safe_path = os.path.normpath(os.path.join(self.base_dir, object_address.lstrip('/')))
        
        if not safe_path.startswith(self.base_dir):
            return self.response(403, 'Forbidden', b'Access denied', {})

        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            with open(safe_path, 'rb') as fp:
                isi = fp.read()
            
            fext = os.path.splitext(safe_path)[1].lower()
            content_type = self.types.get(fext, 'application/octet-stream')
            
            return self.response(200, 'OK', isi, {'Content-Type': content_type})
        
        return self.response(404, 'Not Found', b'File or resource not found', {})

    def http_post(self, object_address, headers, body):
        if object_address == '/upload':
            try:
                content_type = headers.get('Content-Type', '')
                if 'multipart/form-data' not in content_type:
                    return self.response(400, 'Bad Request', b'Content-Type must be multipart/form-data', {})

                boundary = content_type.split('boundary=')[1]
                boundary_bytes = b'--' + boundary.encode('utf-8')
                parts = body.split(boundary_bytes)
                
                for part in parts:
                    if b'Content-Disposition: form-data;' in part and b'filename="' in part:
                        headers_part, content = part.split(b'\r\n\r\n', 1)
                        content = content.rstrip(b'\r\n--\r\n')
                        
                        header_str = headers_part.decode('utf-8', 'ignore')
                        filename_part = header_str.split('filename="')[1]
                        filename = filename_part.split('"')[0]
                        
                        if filename:
                            filename = os.path.basename(filename)
                            save_path = os.path.join(self.upload_dir, filename)
                            with open(save_path, 'wb') as f:
                                f.write(content)
                
                return self.response(200, 'OK', b'Upload successful', {'Location': '/index.html'})
            
            except Exception as e:
                print(f"Error during upload: {e}", file=sys.stderr)
                return self.response(500, 'Internal Server Error', b'Failed to process upload', {})
        
        return self.response(404, 'Not Found', b'', {})

    def http_delete(self, object_address, headers):
        filename_to_delete = urllib.parse.unquote(object_address.lstrip('/'))
        
        safe_path = os.path.normpath(os.path.join(self.upload_dir, filename_to_delete))
        
        if not safe_path.startswith(os.path.abspath(self.upload_dir)):
            return self.response(403, 'Forbidden', b'Access denied', {})

        if not os.path.exists(safe_path) or not os.path.isfile(safe_path):
            return self.response(404, 'Not Found', b'File not found', {})

        try:
            os.remove(safe_path)
            return self.response(200, 'OK', b'File deleted successfully', {})
        except Exception as e:
            print(f"Error deleting file: {e}", file=sys.stderr)
            return self.response(500, 'Internal Server Error', b'Failed to delete file', {})