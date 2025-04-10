from flask import Flask, request, jsonify, send_file, Response
import os
import requests
import jwt
import logging
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/media-data')
AUTH_SERVICE_URL = "http://172.179.66.50"
SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key')  

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

logging.basicConfig(level=logging.INFO)

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'mkv', 'avi', 'jpg', 'png', 'gif'}

def verify_token(token):
    """Extracts and verifies JWT token"""
    try:
        if not token:
            logging.error("Token is missing")
            return None

        if token.startswith("Bearer "):
            token = token.split(" ")[1]  # Extract actual token part

        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        logging.info(f"Decoded token: {decoded_token}")  # Debugging

        return decoded_token.get('username')
    except jwt.ExpiredSignatureError:
        logging.error("Token expired")  # Debugging
        return None
    except jwt.InvalidTokenError:
        logging.error("Invalid token")  # Debugging
        return None

@app.route('/filesystem/')
def home():
    return jsonify({'message': 'Welcome to the File System Service. API is running.'})

def allowed_file(filename):
    """Check if file has a valid extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/filesystem/create_user_directory', methods=['POST'])
def create_user_directory():
    data = request.json
    username = data.get('username')
    user_upload_path = os.path.join(UPLOAD_FOLDER, username)
    os.makedirs(user_upload_path, exist_ok=True)
    return jsonify({'message': 'User directory created'}), 201

@app.route('/filesystem/upload', methods=['POST'])
def upload_file():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Token is missing'}), 401
    
    username = verify_token(token)
    if not username:
        return jsonify({'message': 'Unauthorized'}), 401

    user_upload_path = os.path.join(UPLOAD_FOLDER, username)
    os.makedirs(user_upload_path, exist_ok=True)
    
    if 'file' not in request.files:
        return jsonify({'message': 'No file uploaded'}), 400
    
    file = request.files['file']
    filename = secure_filename(file.filename)

    if not filename or not allowed_file(filename):
        return jsonify({'message': 'Invalid file type'}), 400

    file_path = os.path.join(user_upload_path, filename)
    file.save(file_path)
    
    logging.info(f"File uploaded: {file_path}")
    
    return jsonify({'message': 'File uploaded successfully', 'file_path': file_path}), 201

@app.route('/filesystem/files', methods=['GET'])
def list_files():
    """Return all files (Global visibility for all users)"""
    token = request.headers.get('Authorization') or request.cookies.get('token')  # Support both headers and cookies

    if not token:
        logging.error("Token is missing")
        return jsonify({'message': 'Token is missing'}), 401

    username = verify_token(token)

    if not username:
        logging.error("Failed token verification")  # Debugging
        return jsonify({'message': 'Unauthorized'}), 401

    # List all video files across all user directories
    all_files = []
    for root, _, files in os.walk(UPLOAD_FOLDER):
        for file in files:
            if allowed_file(file):
                file_path = os.path.relpath(os.path.join(root, file), UPLOAD_FOLDER)
                file_url = f"/filesystem/files/{file}" 
                all_files.append({"filename": file, "url": file_url})

    return jsonify({'files': all_files})

@app.route('/filesystem/files/<filename>', methods=['GET'])
def get_file(filename):
    """Stream the requested file with Range support."""
    # Remove token requirement for video streaming
    filename = secure_filename(filename)

    # Find the file in any user directory
    file_path = None
    for root, _, files in os.walk(UPLOAD_FOLDER):
        if filename in files:
            file_path = os.path.join(root, filename)
            break

    if not file_path or not os.path.exists(file_path):
        return jsonify({'message': 'File not found'}), 404

    # Support video streaming with Range headers
    range_header = request.headers.get('Range')
    file_size = os.path.getsize(file_path)

    if range_header:
        try:
            start_byte, end_byte = range_header.replace("bytes=", "").split("-")
            start_byte = int(start_byte)
            end_byte = int(end_byte) if end_byte else file_size - 1
            length = end_byte - start_byte + 1

            with open(file_path, "rb") as f:
                f.seek(start_byte)
                data = f.read(length)

            response = Response(data, 206, mimetype="video/mp4",
                                content_type="video/mp4",
                                direct_passthrough=True)
            response.headers.add("Content-Range", f"bytes {start_byte}-{end_byte}/{file_size}")
            response.headers.add("Accept-Ranges", "bytes")
            return response
        except Exception as e:
            logging.error(f"Error streaming file: {e}")
            return jsonify({'message': 'Error streaming file'}), 500
    else:
        return send_file(file_path, mimetype='video/mp4')

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
