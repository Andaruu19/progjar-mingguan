import sys
import os
import os.path
import logging  # 1. Impor modul logging
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
        # (Fungsi ini tidak perlu diubah)
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
            # 2. Tambahkan log untuk setiap request yang masuk
            logging.info(f"Request diterima: {method} {object_address}")
        except ValueError:
            logging.warning("Menerima request dengan format baris pertama yang salah.")
            return self.response(400, 'Bad Request', b'Malformed request line', {})

        if method == 'GET':
            return self.http_get(object_address, all_headers)
        if method == 'POST':
            return self.http_post(object_address, all_headers, body_bytes)
        if method == 'DELETE':
            return self.http_delete(object_address, all_headers)
        
        logging.warning(f"Metode tidak didukung: '{method}'")
        return self.response(400, 'Bad Request', b'Unsupported method', {})

    def http_get(self, object_address, headers):
        if object_address == '/files':
            # 3. Log untuk operasi LIST
            logging.info("Operasi LIST: Menyajikan daftar file.")
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
            logging.warning(f"Akses terlarang ke path: {safe_path}")
            return self.response(403, 'Forbidden', b'Access denied', {})

        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            with open(safe_path, 'rb') as fp:
                isi = fp.read()
            fext = os.path.splitext(safe_path)[1].lower()
            content_type = self.types.get(fext, 'application/octet-stream')
            return self.response(200, 'OK', isi, {'Content-Type': content_type})
        
        logging.warning(f"GET: File tidak ditemukan di '{safe_path}'")
        return self.response(404, 'Not Found', b'File or resource not found', {})

    def http_post(self, object_address, headers, body):
        if object_address == '/upload':
            try:
                content_type = headers.get('Content-Type', '')
                if 'multipart/form-data' not in content_type:
                    logging.warning("UPLOAD GAGAL: Content-Type bukan multipart/form-data.")
                    return self.response(400, 'Bad Request', b'Content-Type must be multipart/form-data', {})

                boundary = content_type.split('boundary=')[1]
                # ... (sisa kode parsing tidak berubah)
                boundary_bytes = b'--' + boundary.encode('utf-8')
                parts = body.split(boundary_bytes)
                
                for part in parts:
                    if b'Content-Disposition: form-data;' in part and b'filename="' in part:
                        header_str = part.split(b'\r\n\r\n', 1)[0].decode('utf-8', 'ignore')
                        filename = header_str.split('filename="')[1].split('"')[0]
                        
                        if filename:
                            # 4. Log untuk operasi UPLOAD
                            logging.info(f"Operasi UPLOAD: Menerima file '{filename}'")
                            filename = os.path.basename(filename)
                            save_path = os.path.join(self.upload_dir, filename)
                            
                            content = part.split(b'\r\n\r\n', 1)[1].rstrip(b'\r\n--\r\n')
                            with open(save_path, 'wb') as f:
                                f.write(content)
                            logging.info(f"UPLOAD BERHASIL: File disimpan di '{save_path}'")
                
                return self.response(200, 'OK', b'Upload successful', {'Location': '/index.html'})
            
            except Exception as e:
                # Ganti print dengan logging.error
                logging.error(f"UPLOAD GAGAL: Terjadi error saat proses upload: {e}")
                return self.response(500, 'Internal Server Error', b'Failed to process upload', {})
        
        return self.response(404, 'Not Found', b'', {})

    def http_delete(self, object_address, headers):
        filename_to_delete = urllib.parse.unquote(object_address.lstrip('/'))
        # 5. Log untuk operasi DELETE
        logging.info(f"Operasi DELETE: Mencoba menghapus file '{filename_to_delete}'")
        
        safe_path = os.path.normpath(os.path.join(self.upload_dir, filename_to_delete))
        
        if not safe_path.startswith(os.path.abspath(self.upload_dir)):
            logging.warning(f"DELETE GAGAL: Akses terlarang ke path '{safe_path}'")
            return self.response(403, 'Forbidden', b'Access denied', {})

        if not os.path.exists(safe_path) or not os.path.isfile(safe_path):
            logging.warning(f"DELETE GAGAL: File tidak ditemukan di '{safe_path}'")
            return self.response(404, 'Not Found', b'File not found', {})

        try:
            os.remove(safe_path)
            logging.info(f"DELETE BERHASIL: File '{safe_path}' telah dihapus.")
            return self.response(200, 'OK', b'File deleted successfully', {})
        except Exception as e:
            # Ganti print dengan logging.error
            logging.error(f"DELETE GAGAL: Terjadi error saat menghapus file '{safe_path}': {e}")
            return self.response(500, 'Internal Server Error', b'Failed to delete file', {})