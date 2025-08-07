from flask import Flask, render_template, request, jsonify
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import random
import csv
import os
from threading import Thread
import time
from flask_cors import CORS
import atexit
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import hashlib
from Crypto import Random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configuration from environment variables
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
SECRET_KEY = os.getenv('ENCRYPTION_KEY')  # Must be exactly 32 bytes for AES-256

# Validate configuration
if not all([SENDER_EMAIL, SENDER_PASSWORD, SECRET_KEY]):
    raise ValueError("Missing required environment variables")


# In-memory storage for OTPs
otp_storage = {}

# File to store reminders
REMINDERS_FILE = 'reminders.csv'
active_threads = []

# Initialize encryption
def generate_iv():
    """Generate a cryptographically secure random IV"""
    return Random.new().read(AES.block_size)

def get_cipher(iv=None):
    """Initialize AES cipher with proper key derivation"""
    if not iv:
        iv = generate_iv()
    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    return AES.new(key, AES.MODE_CBC, iv), iv

def encrypt_data(data):
    """Encrypt data with AES-256-CBC"""
    if not data:
        return data
    cipher, iv = get_cipher()
    padded_data = pad(data.encode(), AES.block_size)
    encrypted = cipher.encrypt(padded_data)
    return base64.b64encode(iv + encrypted).decode('utf-8')

def decrypt_data(encrypted_data):
    """Decrypt AES-256-CBC encrypted data"""
    if not encrypted_data:
        return encrypted_data
    decoded = base64.b64decode(encrypted_data)
    iv = decoded[:AES.block_size]
    encrypted = decoded[AES.block_size:]
    cipher, _ = get_cipher(iv)
    decrypted = cipher.decrypt(encrypted)
    return unpad(decrypted, AES.block_size).decode('utf-8')

# Create reminders file if it doesn't exist
if not os.path.exists(REMINDERS_FILE):
    with open(REMINDERS_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'encrypted_email', 'encrypted_message', 'reminder_time', 'verified'])

def cleanup_threads():
    """Clean up any remaining threads on exit"""
    for thread in active_threads:
        if thread.is_alive():
            thread.join(timeout=1)

atexit.register(cleanup_threads)

@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html')

@app.route('/send_otp', methods=['POST'])
def send_otp():
    """Handle OTP generation and sending"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400

        receiver_email = data.get('receiver_email')
        reminder_message = data.get('reminder_message')
        reminder_time = data.get('reminder_time')

        if not all([receiver_email, reminder_message, reminder_time]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))
        
        # Store OTP with timestamp
        otp_storage[receiver_email] = {
            'otp': otp,
            'timestamp': datetime.now(),
            'reminder_message': reminder_message,
            'reminder_time': reminder_time
        }

        # Send OTP email
        try:
            msg = MIMEText(f'Your OTP for Remainder.io is: {otp}\n\nReminder details:\nMessage: {reminder_message}\nTime: {reminder_time}')
            msg['Subject'] = 'Your Remainder.io Verification OTP'
            msg['From'] = SENDER_EMAIL
            msg['To'] = receiver_email

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
            
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Failed to send email: {str(e)}'}), 500

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    """Verify OTP and schedule reminders"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400

        receiver_email = data.get('receiver_email')
        user_otp = data.get('otp')
        reminder_message = data.get('reminder_message')
        reminder_time = data.get('reminder_time')

        if not all([receiver_email, user_otp, reminder_message, reminder_time]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        # Check if OTP exists and is valid
        if receiver_email in otp_storage:
            stored_data = otp_storage[receiver_email]
            
            # Check if OTP matches and is not expired (5 minutes)
            if (user_otp == stored_data['otp'] and 
                (datetime.now() - stored_data['timestamp']) < timedelta(minutes=5)):
                
                # Encrypt sensitive data before storing
                encrypted_email = encrypt_data(receiver_email)
                encrypted_message = encrypt_data(reminder_message)
                
                # Store the verified reminder with encrypted data
                with open(REMINDERS_FILE, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        datetime.now().isoformat(),  # timestamp
                        encrypted_email,
                        encrypted_message,
                        reminder_time,
                        True
                    ])
                
                # Schedule reminder emails (using original unencrypted data)
                schedule_reminders(receiver_email, reminder_message, reminder_time)
                
                # Remove OTP from storage
                del otp_storage[receiver_email]
                
                return jsonify({'success': True})
        
        return jsonify({'success': False, 'message': 'Invalid or expired OTP'}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def schedule_reminders(receiver_email, reminder_message, reminder_time_str):
    """Schedule reminder emails at three different times"""
    try:
        # Parse the time string (handle both with and without seconds)
        try:
            reminder_time = datetime.strptime(reminder_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            reminder_time = datetime.strptime(reminder_time_str, '%Y-%m-%dT%H:%M:%S')
        
        # Schedule three reminders
        reminders = [
            (reminder_time - timedelta(minutes=5)),  # 5 minutes before
            reminder_time,                          # exact time
            (reminder_time + timedelta(minutes=5))   # 5 minutes after
        ]
        
        for scheduled_time in reminders:
            delay = (scheduled_time - datetime.now()).total_seconds()
            if delay > 0:
                # Create a new thread for each reminder
                t = Thread(target=send_reminder_email, args=(
                    receiver_email,
                    reminder_message,
                    scheduled_time.strftime('%Y-%m-%d %H:%M'),
                    delay
                ))
                t.daemon = True  # Make thread a daemon so it won't block program exit
                t.start()
                active_threads.append(t)
                print(f"Scheduled reminder for {receiver_email} at {scheduled_time} (in {delay} seconds)")
    except Exception as e:
        print(f"Error scheduling reminders: {e}")

def send_reminder_email(receiver_email, message, scheduled_time_str, delay):
    """Send the actual reminder email"""
    time.sleep(delay)
    
    try:
        print(f"Attempting to send reminder to {receiver_email}...")
        
        # Create new SMTP connection for each email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            
            subject = "Remainder.io: Your scheduled reminder"
            body = f"""This is your reminder from Remainder.io:

{message}

Scheduled for: {scheduled_time_str}
Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
            
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = SENDER_EMAIL
            msg['To'] = receiver_email
            
            server.send_message(msg)
            print(f"Reminder successfully sent to {receiver_email}")
    except Exception as e:
        print(f"Failed to send reminder to {receiver_email}: {e}")

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)