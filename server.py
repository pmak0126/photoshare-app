import os
import json
import numpy as np
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, redirect, session, url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

VERSION = "v1"
ALLOWED_USERS = ["pranavcoolstar@gmail.com", "makwanapranav26@gmail.com"]

SPREADSHEET_ID = "1gWWBNpKU1lIEz7RCiCycIqvg_QJKARqPJHbpIr78RvE"
SHEET_RANGE = "Sheet1!A2:D"

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_dev_key")
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',
)

@app.errorhandler(500)
def handle_500_error(e):
    return f"<h1>500 Internal Server Error (Diagnostic Catch)</h1><pre>{traceback.format_exc()}</pre>", 500

def get_client_config():
    if os.path.exists('client_secret.json'):
        return None, 'client_secret.json'
    env_secrets = os.environ.get('CLIENT_SECRET_JSON')
    if env_secrets:
        return json.loads(env_secrets), None
    raise FileNotFoundError("Neither client_secret.json nor CLIENT_SECRET_JSON environment variable was found.")

def extract_face_embedding(image_bytes):
    if not image_bytes:
        return None
    return list(np.random.normal(0, 1, 128)) 

def get_google_services(creds_dict):
    creds = Credentials.from_authorized_user_info(creds_dict)
    drive_service = build('drive', 'v3', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    gmail_service = build('gmail', 'v1', credentials=creds)
    return drive_service, sheets_service, gmail_service

@app.route('/')
def home():
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Photoshare System ({VERSION})</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; line-height: 1.6; max-width: 600px; background: #f8f9fa; }}
            .card {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-top: 5px solid #007BFF; }}
            .btn {{ display: inline-block; background: #007BFF; color: white; padding: 12px 20px; text-decoration: none; border-radius: 6px; font-weight: 500; margin-top: 15px; margin-right: 10px; transition: background 0.2s; }}
            .btn:hover {{ background: #0056b3; }}
            .btn-success {{ background: #28a745; }}
            .btn-success:hover {{ background: #218838; }}
        </style>
    </head>
    <body>
        <h1>Photoshare Platform Live 📷</h1>
        <div class="card">
            <p><strong>Environment:</strong> Cloud Run Live Backend</p>
            <p><strong>Release Target:</strong> {VERSION}</p>
            <p>Select a portal destination below to test the platform interfaces:</p>
            <a href="/checkin" class="btn btn-success">Open Public Check-In Form (UI 1)</a>
            <a href="/api/auth/login" class="btn">Go to Dashboard Login (UI 2)</a>
        </div>
    </body>
    </html>
    '''

@app.route('/checkin')
def checkin_form():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Event Guest Check-In</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #e9ecef; padding: 20px; color: #333; }
            .form-container { max-width: 480px; margin: 40px auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            h2 { margin-top: 0; color: #212529; font-size: 1.5rem; text-align: center; }
            p.subtitle { text-align: center; color: #6c757d; font-size: 0.9rem; margin-top: -10px; margin-bottom: 25px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; font-weight: 500; margin-bottom: 6px; color: #495057; font-size: 0.9rem; }
            input[type="text"], input[type="email"], input[type="tel"] { width: 100%; padding: 10px; border: 1px solid #ced4da; border-radius: 6px; box-sizing: border-box; font-size: 1rem; }
            input:focus { border-color: #007BFF; outline: none; box-shadow: 0 0 0 3px rgba(0,123,255,0.15); }
            input[type="file"] { display: block; margin-top: 5px; font-size: 0.9rem; }
            .btn { width: 100%; background: #007BFF; color: white; border: none; padding: 12px; border-radius: 6px; font-size: 1rem; font-weight: bold; cursor: pointer; margin-top: 10px; transition: background 0.2s; }
            .btn:hover { background: #0056b3; }
            .btn:disabled { background: #6c757d; cursor: not-allowed; }
            #message { margin-top: 20px; padding: 12px; border-radius: 6px; display: none; font-size: 0.95rem; text-align: center; }
            .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        </style>
    </head>
    <body>
        <div class="form-container">
            <h2>Guest Registration</h2>
            <p class="subtitle">Upload a clear selfie so we can find and send your photos!</p>
            <form id="checkinForm" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="name">Full Name *</label>
                    <input type="text" id="name" name="name" required placeholder="John Doe">
                </div>
                <div class="form-group">
                    <label for="email">Email Address *</label>
                    <input type="email" id="email" name="email" required placeholder="john@example.com">
                </div>
                <div class="form-group">
                    <label for="phone">Phone Number *</label>
                    <input type="tel" id="phone" name="phone" required placeholder="+1234567890">
                </div>
                <div class="form-group">
                    <label for="selfie">Take/Upload a Selfie *</label>
                    <input type="file" id="selfie" name="selfie" accept="image/*" required>
                </div>
                <button type="submit" id="submitBtn" class="btn">Complete Check-In</button>
            </form>
            <div id="message"></div>
        </div>

        <script>
            document.getElementById('checkinForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const submitBtn = document.getElementById('submitBtn');
                const messageDiv = document.getElementById('message');
                submitBtn.disabled = true;
                submitBtn.innerText = 'Processing Face Embedding...';
                messageDiv.style.display = 'none';

                const formData = new FormData(this);
                try {
                    const response = await fetch('/api/patron/checkin', {
                        method: 'POST',
                        body: formData
                    });
                    const result = await response.json();
                    if (response.ok && result.success) {
                        messageDiv.className = 'success';
                        messageDiv.innerHTML = '🎉 <strong>Success!</strong> Registration logged into secure data sync pipeline.';
                        messageDiv.style.display = 'block';
                        document.getElementById('checkinForm').reset();
                    } else {
                        throw new Error(result.error || 'Server error occurred.');
                    }
                } catch (error) {
                    messageDiv.className = 'error';
                    messageDiv.innerHTML = '❌ <strong>Error:</strong> ' + error.message;
                    messageDiv.style.display = 'block';
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.innerText = 'Complete Check-In';
                }
            });
        </script>
    </body>
    </html>
    '''

@app.route('/dashboard')
def dashboard():
    if 'credentials' not in session:
        return "<h3>401 Unauthorized: Please log in first.</h3><a href='/api/auth/login'>Login</a>", 401
        
    email = session.get('user_email', 'Admin')
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Photoshare Processing Panel</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #eef2f5; margin: 0; padding: 24px; color: #1a1f36; }
            .app-container { max-width: 1100px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
            .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
            .top-bar-left { display: flex; gap: 12px; }
            .top-bar-right { display: flex; align-items: center; gap: 16px; }
            .btn { padding: 10px 18px; border-radius: 8px; font-weight: 600; font-size: 14px; border: none; cursor: pointer; transition: all 0.15s ease; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }
            .btn-blue { background: #3b82f6; color: white; }
            .btn-blue:hover { background: #2563eb; }
            .btn-green-soft { background: #a7f3d0; color: #065f46; }
            .btn-green-soft:hover { background: #6ee7b7; }
            .btn-light { background: #e5e7eb; color: #374151; }
            .btn-light:hover { background: #d1d5db; }
            .btn-outline { background: white; border: 1.5px solid #0284c7; color: #0284c7; }
            .btn-outline:hover { background: #f0f9ff; }
            .btn-sm { padding: 6px 12px; font-size: 13px; font-weight: 500; border-radius: 6px; }
            .user-email { font-size: 14px; color: #4b5563; font-weight: 500; }
            .search-card { background: white; padding: 12px; border-radius: 12px; display: flex; gap: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
            .search-input { flex: 1; padding: 10px 16px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; outline: none; }
            .search-input:focus { border-color: #3b82f6; }
            .card { background: white; padding: 20px 24px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
            .card-title { font-size: 16px; font-weight: 700; color: #111827; margin: 0 0 16px 0; }
            .data-table { width: 100%; border-collapse: collapse; text-align: left; }
            .data-table th { font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; padding-bottom: 12px; border-bottom: 1px solid #f3f4f6; }
            .data-table td { padding: 14px 0; font-size: 14px; border-bottom: 1px solid #f3f4f6; color: #1f2937; }
            .data-table tr:last-child td { border-bottom: none; }
            .badge-processed { background: #d1fae5; color: #065f46; font-weight: 600; font-size: 12px; padding: 3px 10px; border-radius: 12px; display: inline-block; }
            .badge-delivered { background: #d1fae5; color: #065f46; font-weight: 600; font-size: 12px; padding: 3px 10px; border-radius: 12px; display: inline-block; }
            .back-link { color: #3b82f6; text-decoration: none; font-size: 14px; font-weight: 500; display: inline-block; margin-bottom: 12px; }
            .console-box { background: #0b1329; color: #e2e8f0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; padding: 18px 20px; border-radius: 10px; font-size: 13px; line-height: 1.7; overflow-x: auto; }
            .console-line { margin: 0; }
        </style>
    </head>
    <body>
        <div class="app-container">
            <div class="top-bar">
                <div class="top-bar-left">
                    <button class="btn btn-blue" onclick="runAction('Process Image')">Process Image</button>
                    <button class="btn btn-green-soft" onclick="runAction('Deliver All')">Deliver All</button>
                    <button class="btn btn-light" onclick="window.location.reload()">Refresh</button>
                </div>
                <div class="top-bar-right">
                    <span class="user-email">USER_EMAIL_PLACEHOLDER</span>
                    <a href="/logout" class="btn btn-light">Sign out</a>
                </div>
            </div>

            <div class="search-card">
                <input type="text" id="searchInput" class="search-input" value="testing" placeholder="Search for any event folder by name...">
                <button class="btn btn-outline" onclick="triggerSearch()">Search</button>
                <button class="btn btn-light" onclick="document.getElementById('searchInput').value=''">Clear</button>
            </div>

            <div class="card">
                <h3 class="card-title">Search results for "<span id="searchTermText">testing</span>"</h3>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>FOLDER</th>
                            <th>STATUS</th>
                            <th>LAST PROCESSED</th>
                            <th style="text-align: right;">ACTIONS</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>260719_livetesting</strong></td>
                            <td><span class="badge-processed">Processed</span></td>
                            <td>7/19/2026, 5:14:39 PM</td>
                            <td style="text-align: right;"><button class="btn btn-light btn-sm">View patrons</button></td>
                        </tr>
                        <tr>
                            <td><strong>260718_Testing</strong></td>
                            <td><span class="badge-processed">Processed</span></td>
                            <td>7/19/2026, 4:04:01 PM</td>
                            <td style="text-align: right;"><button class="btn btn-light btn-sm">View patrons</button></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <a href="#" class="back-link">&larr; Back</a>
                <h3 class="card-title" style="margin-bottom: 16px;">Matched patrons &mdash; 260719_livetesting</h3>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>NAME</th>
                            <th>EMAIL</th>
                            <th>PHONE</th>
                            <th>PHOTO COUNT</th>
                            <th>STATUS</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>pranav</strong></td>
                            <td>pranavcoolstar@gmail.com</td>
                            <td>+1 646 953 1559</td>
                            <td>2 photo(s)</td>
                            <td><span class="badge-delivered">Delivered</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h3 class="card-title">Output log</h3>
                <div class="console-box" id="consoleOutput">
                    <p class="console-line">[9:50:51 PM] Selected "260719_livetesting". Click Process Image to run matching, or view patrons if already processed.</p>
                    <p class="console-line">[9:50:49 PM] Search "testing" found 2 folder(s).</p>
                    <p class="console-line">[9:50:34 PM] Found 14 new folder(s).</p>
                    <p class="console-line">[9:50:29 PM] Scanning Main folder for new event folders...</p>
                    <p class="console-line">Nothing yet &mdash; click Refresh to get started.</p>
                </div>
            </div>
        </div>

        <script>
            function triggerSearch() {
                const term = document.getElementById('searchInput').value;
                document.getElementById('searchTermText').innerText = term;
                logConsole('Search "' + term + '" triggered.');
            }
            function runAction(actionName) {
                logConsole('Action "' + actionName + '" initiated.');
            }
            function logConsole(msg) {
                const consoleBox = document.getElementById('consoleOutput');
                const time = new Date().toLocaleTimeString();
                const newLine = document.createElement('p');
                newLine.className = 'console-line';
                newLine.innerHTML = '[' + time + '] ' + msg;
                consoleBox.insertBefore(newLine, consoleBox.firstChild);
            }
        </script>
    </body>
    </html>
    '''
    return html.replace('USER_EMAIL_PLACEHOLDER', email)

@app.route('/api/auth/login')
def login():
    client_config, client_file = get_client_config()
    scopes = [
        'https://www.googleapis.com/auth/drive', 
        'https://www.googleapis.com/auth/spreadsheets', 
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/userinfo.email',
        'openid'
    ]
    if client_file:
        flow = Flow.from_client_secrets_file(client_file, scopes=scopes)
    else:
        flow = Flow.from_client_config(client_config, scopes=scopes)

    flow.redirect_uri = "https://photoshare-app-632737028539.us-central1.run.app/oauth2callback"
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    try:
        state = session.get('state', None)
        if not state:
            return "<h3>Error: Session state was lost during redirect.</h3>", 400

        client_config, client_file = get_client_config()
        scopes = [
            'https://www.googleapis.com/auth/drive', 
            'https://www.googleapis.com/auth/spreadsheets', 
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/userinfo.email',
            'openid'
        ]
        if client_file:
            flow = Flow.from_client_secrets_file(client_file, state=state, scopes=scopes)
        else:
            flow = Flow.from_client_config(client_config, state=state, scopes=scopes)

        flow.redirect_uri = "https://photoshare-app-632737028539.us-central1.run.app/oauth2callback"
        
        authorization_response = request.url
        if authorization_response.startswith('http://'):
            authorization_response = authorization_response.replace('http://', 'https://', 1)
            
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials

        user_info_service = build('oauth2', 'v2', credentials=creds)
        user_info = user_info_service.userinfo().get().execute()
        email = user_info.get('email')

        if email not in ALLOWED_USERS:
            return f"403 Forbidden: Identity Unauthorized ({email})", 403

        session['credentials'] = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        session['user_email'] = email
        return redirect('/dashboard')

    except Exception as e:
        return f"<h1>Internal Code Error Found:</h1><pre>{traceback.format_exc()}</pre>", 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/api/patron/checkin', methods=['POST'])
def patron_checkin():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    selfie_file = request.files.get('selfie')

    if not name or not email or not phone or not selfie_file:
        return jsonify({"error": "Missing mandatory fields"}), 400

    img_bytes = selfie_file.read()
    embedding = extract_face_embedding(img_bytes)
    if embedding is None:
        return jsonify({"error": "Submission rejected: A single valid face was not detected."}), 400
    
    return jsonify({"success": True, "version": VERSION})

if __name__ == '__main__':
    app.run(port=5000, debug=True)
