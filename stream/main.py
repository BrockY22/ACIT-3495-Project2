import os
import requests
import jwt
import logging
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_mysqldb import MySQL  # ✅ Import MySQLdb

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://auth:5000')
FILE_SYSTEM_URL = os.getenv('FILE_SYSTEM_URL', 'http://filesystem:5001')  # ✅ Fix incorrect service name

# ✅ Add MySQL configuration
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'db')  # MySQL container name
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', 'password')
app.config['MYSQL_DB'] = os.getenv('MEDIA_DB','uploads')  # Ensure this matches your MySQL database

mysql = MySQL(app)  # ✅ Initialize MySQL

logging.basicConfig(level=logging.INFO)

def verify_token(token):
    """Decodes and verifies JWT token"""
    try:
        decoded_token = jwt.decode(token, app.secret_key, algorithms=['HS256'])
        return decoded_token.get('username')
    except jwt.ExpiredSignatureError:
        return None  # Token expired
    except jwt.InvalidTokenError:
        return None  # Invalid token
@app.route('/')
def home():
    token = request.cookies.get('token')
    if not token or not verify_token(token):
        return redirect(f"{AUTH_SERVICE_URL}/login?message=Please log in first.")
    
    return redirect(url_for('browse_files'))
@app.route('/browse', methods=['GET'])
def browse_files():
    token = request.cookies.get('token')
    if not token:
        return redirect(f"{AUTH_SERVICE_URL}/login?message=Please log in first.")

    # Verify token
    username = verify_token(token)
    if not username:
        return redirect(f"{AUTH_SERVICE_URL}/login?message=Session expired. Please log in again.")

    # ✅ Fetch all videos from the database (not just the current user)
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT filename, username FROM files")  # ✅ Remove 'uploads.' prefix
        files = [{"filename": row[0], "uploaded_by": row[1]} for row in cur.fetchall()]
        cur.close()
    except Exception as e:
        logging.error(f"Database error: {e}")
        return jsonify({'message': 'Could not fetch files'}), 500

    return render_template('browse.html', files=files, username=username)

@app.route('/media/<filename>', methods=['GET'])
def view_media(filename):
    token = request.cookies.get('token')
    if not token:
        return redirect(f"{AUTH_SERVICE_URL}/login?message=Please log in first.")

    # Verify token
    username = verify_token(token)
    if not username:
        return redirect(f"{AUTH_SERVICE_URL}/login?message=Session expired. Please log in again.")

    # ✅ Fix incorrect media URL (no need to include `username`)
    media_url = f"http://filesystem:5001/files/{filename}"

    return render_template('video_player.html', filename=filename, media_url=media_url, username=username)

if __name__ == '__main__':
    app.run(debug=True, port=8090, host='0.0.0.0')
