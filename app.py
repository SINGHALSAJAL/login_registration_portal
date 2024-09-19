import psycopg2
from dotenv import load_dotenv
import os
from flask import Flask, request, render_template, redirect, url_for
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Config for Gmail SMTP server
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')  # Your email
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')  # Your email password or app-specific password
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')  # Your email
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')  # Secret key for generating tokens

mail = Mail(app)

# DB VARIABLES
database = os.environ.get('DATABASE')
user = os.environ.get('PGUSER')
password = os.environ.get('PGPASSWORD')
host = os.environ.get('PGHOST')
port = os.environ.get('PGPORT')

# DB CONNECTIVITY
conn = psycopg2.connect(database=database, user=user, password=password, host=host, port=port)

# Default page
@app.route('/')
def homepage():
    return render_template('home.html')

# Send registration alert email
def send_login_email(email, user):
    msg = Message('Sucessful Registration ', recipients=[email])
    msg.body = f"Dear {user},\n\nYour email has been successfully verified. You can now log in to your account.\n\nThank you for registering with us!"
    mail.send(msg)

# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = conn.cursor()
        # Fetch user and check if the email is verified
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        #('id','name','email','username','password','email_verified')
        if user:
            if user[5]:  # Assuming the 6th column is email_verified
                name = user[1]  # Assuming the second column is the user's name
                return render_template('main.html',user=name)
            else:
                return render_template('login.html', message='Please verify your email before logging in.')
        else:
            return render_template('login.html', message='Invalid Credentials or New User !!')

    return render_template('login.html')  # Display the login form for GET requests

# Token generation and verification
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

def generate_confirmation_token(email):
    return s.dumps(email, salt='email-confirm')

def confirm_token(token, expiration=3600):
    try:
        email = s.loads(token, salt='email-confirm', max_age=expiration)
    except Exception:
        return False
    return email

# Send email
def send_email(to, subject, template):
    msg = Message(subject, recipients=[to], html=template)
    mail.send(msg)

# Registration Page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        username = request.form['username']
        createpassword = request.form['createpassword']
        finalpassword = request.form['finalpassword']

        if createpassword == finalpassword:
            cursor = conn.cursor()
            # Check if user already exists
            cursor.execute("SELECT * FROM users WHERE email=%s OR user_name=%s", (email, username))
            user = cursor.fetchone()

            if user:
                return render_template('register.html', message='Account already exists!!')
            else:
                # Insert the user as unverified
                cursor.execute(
                    "INSERT INTO users (name, email, user_name, password, email_verified) VALUES (%s, %s, %s, %s, %s)", 
                    (name, email, username, createpassword, False)
                )
                conn.commit()

                # Generate email verification token
                token = generate_confirmation_token(email)
                confirm_url = url_for('confirm_email', token=token, _external=True)
                
                # Send verification email
                html = render_template('activate.html', confirm_url=confirm_url)
                subject = "Please confirm your email"
                send_email(email, subject, html)

                return render_template('register.html', message="A confirmation email has been sent. Please verify to activate your account.")

        else:
            return render_template('register.html', message='Passwords do not match!!')

    return render_template('register.html')


# Confirm email
@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)
    except:
        return render_template('error.html', message="The confirmation link is invalid or has expired.")

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if user and not user[5]:  # Check if email is not verified yet
        cursor.execute("UPDATE users SET email_verified=%s WHERE email=%s", (True, email))
        conn.commit()
        send_login_email(email,user=user[1])
        return render_template('login.html', message1="Your account has been verified. You can now log in.")
    else:
        return render_template('error.html', message="Account already confirmed or invalid link.")


if __name__ == '__main__':
    app.run(debug=True)

# Close the connection after the app is done running
conn.close()
