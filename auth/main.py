from flask import Flask, request, jsonify, render_template, redirect, url_for, make_response
import jwt
import datetime
import os
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'db')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', 'password')
app.config['MYSQL_DB'] = os.getenv('CREDENTIALS_DB','credentials')

mysql = MySQL(app)

def verify_token(token):
    """Decodes and verifies JWT token"""
    try:
        decoded_token = jwt.decode(token, app.secret_key, algorithms=['HS256'])
        return decoded_token.get('username')
    except jwt.ExpiredSignatureError:
        return None  # Token expired
    except jwt.InvalidTokenError:
        return None  # Invalid token
    
@app.route('/auth')
def home():
    token = request.cookies.get('token')
    if token and verify_token(token):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/auth/register', methods=['GET', 'POST'])
def register():
    message = request.args.get('message', '')
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()

        if existing_user:
            cur.close()
            return render_template('register.html', message="Username already exists.", show_alert=True)

        try:
            cur.execute("INSERT INTO users (username, password, user_dir) VALUES (%s, %s, %s)", 
                        (username, password, f"/media-data/{username}"))
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('login', message="Registration successful. Please log in."))
        except Exception as e:
            return render_template('register.html', message="Registration failed.", show_alert=True)

    return render_template('register.html', message=message, show_alert=False)

@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    token = request.cookies.get('token')
    if token and verify_token(token):
        return redirect(url_for('dashboard'))
    
    message = request.args.get('message', '')

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[2], password):
            token = jwt.encode(
                {'username': username, 'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)},
                app.config['SECRET_KEY'], algorithm='HS256'
            )

            # Check if request is an API request (JSON or curl)
            if request.headers.get('Accept') == 'application/json' or request.content_type == 'application/json':
                return jsonify({'token': token})  # API clients get the token

            # Otherwise, redirect to dashboard (for web users)
            response = make_response(redirect(url_for('dashboard')))
            response.set_cookie('token', token, httponly=True, samesite='Lax', secure=False)
            return response

        else:
            return render_template('login.html', message="Invalid credentials. Please try again.")

    return render_template('login.html', message=message)

@app.route('/auth/dashboard')
def dashboard():
    token = request.cookies.get('token')  # Get token from cookies
    if not token:
        return redirect(url_for('login', message="Please log in first."))  # Redirect if no token

    username = verify_token(token)  # Verify token
    if not username:
        return redirect(url_for('login', message="Session expired. Please log in again."))

    return render_template('dashboard.html', username=username)  # Show dashboard


@app.route('/auth/logout')
def logout():
    response = make_response(redirect(url_for('login', message="You have been logged out.")))
    response.set_cookie('token', '', expires=0, httponly=True, secure=True, samesite='Lax')
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
