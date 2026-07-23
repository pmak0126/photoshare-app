import os
import json
import base64
import io
import numpy as np
import traceback
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, redirect, session, url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import face_recognition
from PIL import Image, ImageOps

VERSION = "v4-dynamic-users"

# Mutable set for dynamic authorization during server runtime
ALLOWED_USERS = {"pranavcoolstar@gmail.com", "makwanapranav26@gmail.com"}

# Default config mapping per user (Fallback defaults if not provided in session)
DEFAULT_USER_CONFIGS = {
    "pranavcoolstar@gmail.com": {
        "spreadsheet_id": "1gWWBNpKU1lIEz7RCiCycIqvg_QJKARqPJHbpIr78RvE",
        "drive_folder_id": "1FBhdmP9xzKnD8-aCx5aJIV3jcgoujWIm"
    },
    "makwanapranav26@gmail.com": {
        "spreadsheet_id": "1gWWBNpKU1lIEz7RCiCycIqvg_QJKARqPJHbpIr78RvE",
        "drive_folder_id": "1FBhdmP9xzKnD8-aCx5aJIV3jcgoujWIm"
    }
}

TOKEN_FILE = "/tmp/google_tokens.json"

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_dev_key")
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',
)

system_creds_cache = None

def get_user_spreadsheet_id():
    return session.get('spreadsheet_id') or os.environ.get("SPREADSHEET_ID", "1gWWBNpKU1lIEz7RCiCycIqvg_QJKARqPJHbpIr78RvE")

def get_user_drive_folder_id():
    return session.get('drive_folder_id') or os.environ.get("TARGET_DRIVE_FOLDER_ID", "1FBhdmP9xzKnD8-aCx5aJIV3jcgoujWIm")

@app.errorhandler(500)
def handle_500_error(e):
    return f"<h1>500 Internal Server Error (Diagnostic Catch)</h1><pre>{traceback.format_exc()}</pre>", 500

def save_creds_to_disk(creds_dict):
    global system_creds_cache
    system_creds_cache = creds_dict
    try:
        with open(TOKEN_FILE, 'w') as f:
            json.dump(creds_dict, f)
    except Exception as e:
        print(f"Failed to persist tokens to disk: {e}")

def load_creds():
    global system_creds_cache
    if system_creds_cache:
        return system_creds_cache
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                system_creds_cache = json.load(f)
                return system_creds_cache
        except Exception:
            pass
    return None

def get_client_config():
    if os.path.exists('client_secret.json'):
        with open('client_secret.json', 'r') as f:
            return json.load(f), 'client_secret.json'
    env_secrets = os.environ.get('CLIENT_SECRET_JSON')
    if env_secrets:
        try:
            decoded = base64.b64decode(env_secrets).decode('utf-8')
            return json.loads(decoded), None
        except Exception:
            return json.loads(env_secrets), None
    raise FileNotFoundError("Neither client_secret.json nor CLIENT_SECRET_JSON environment variable was found.")

def extract_face_embeddings(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        image = image.convert('RGB')
        image.thumbnail((1200, 1200))
        np_img = np.array(image)
        
        encodings = face_recognition.face_encodings(np_img)
        if not encodings:
            encodings = face_recognition.face_encodings(np_img, number_of_times_to_upsample=2)
            
        return encodings
    except Exception as e:
        print(f"Error extracting face embedding: {e}")
        return []

def get_google_services(creds_dict):
    client_config, _ = get_client_config()
    if client_config and 'web' in client_config:
        creds_dict['client_id'] = client_config['web']['client_id']
        creds_dict['client_secret'] = client_config['web']['client_secret']
        creds_dict['token_uri'] = client_config['web'].get('token_uri', 'https://oauth2.googleapis.com/token')

    creds = Credentials.from_authorized_user_info(creds_dict)
    drive_service = build('drive', 'v3', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    gmail_service = build('gmail', 'v1', credentials=creds)
    return drive_service, sheets_service, gmail_service

def send_photo_email(gmail_srv, recipient_email, recipient_name, photo_links):
    message = MIMEMultipart("alternative")
    message["To"] = recipient_email
    message["Subject"] = f"📷 Your Photos are Ready, {recipient_name}!"

    links_html = "".join([f'<li><a href="{link}" target="_blank">{link}</a></li>' for link in photo_links])
    count = len(photo_links)
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Hello {recipient_name}! 👋</h2>
        <p>We found <strong>{count} photo(s)</strong> matching your facial recognition check-in from your recent event.</p>
        <p>Click the links below to view and download your photos directly from Google Drive:</p>
        <ul>
            {links_html}
        </ul>
        <br>
        <p>Best regards,<br><strong>Photoshare System Team</strong></p>
    </body>
    </html>
    """
    message.attach(MIMEText(html_content, "html"))
    raw_msg = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    gmail_srv.users().messages().send(userId="me", body={"raw": raw_msg}).execute()

def make_file_public(drive_srv, file_id):
    try:
        drive_srv.permissions().create(
            fileId=file_id,
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
    except Exception as e:
        print(f"Failed to set public view permission for {file_id}: {e}")

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
            .btn {{ display: inline-block; background: #007BFF; color: white; padding: 12px 20px; text-decoration: none; border-radius: 6px; font-weight: 500; margin-top: 15px; margin-right: 10px; }}
            .btn:hover {{ background: #0056b3; }}
            .btn-success {{ background: #28a745; }}
            .btn-success:hover {{ background: #218838; }}
        </style>
    </head>
    <body>
        <h1>Photoshare Platform Live 📷</h1>
        <div class="card">
            <p><strong>Environment:</strong> Cloud Run Live Backend ({VERSION})</p>
            <a href="/checkin" class="btn btn-success">Open Guest Check-In Form</a>
            <a href="/api/auth/login" class="btn">Go to Operations Dashboard</a>
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
            h2 { margin-top: 0; color: #212529; text-align: center; }
            .form-group { margin-bottom: 20px; }
            label { display: block; font-weight: 500; margin-bottom: 6px; }
            input[type="text"], input[type="email"], input[type="tel"] { width: 100%; padding: 10px; border: 1px solid #ced4da; border-radius: 6px; box-sizing: border-box; }
            .btn { width: 100%; background: #007BFF; color: white; border: none; padding: 12px; border-radius: 6px; font-weight: bold; cursor: pointer; }
            #message { margin-top: 20px; padding: 12px; border-radius: 6px; display: none; text-align: center; }
            .success { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
        </style>
    </head>
    <body>
        <div class="form-container">
            <h2>Guest Registration</h2>
            <form id="checkinForm" enctype="multipart/form-data">
                <div class="form-group"><label>Full Name *</label><input type="text" name="name" required></div>
                <div class="form-group"><label>Email Address *</label><input type="email" name="email" required></div>
                <div class="form-group"><label>Phone Number *</label><input type="tel" name="phone" required></div>
                <div class="form-group"><label>Take/Upload Selfie *</label><input type="file" name="selfie" accept="image/*" required></div>
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
                submitBtn.innerText = 'Processing Selfie...';
                const formData = new FormData(this);
                try {
                    const response = await fetch('/api/patron/checkin', { method: 'POST', body: formData });
                    const result = await response.json();
                    if (response.ok && result.success) {
                        messageDiv.className = 'success';
                        messageDiv.innerHTML = '🎉 Check-in logged successfully with face encoding!';
                        messageDiv.style.display = 'block';
                        this.reset();
                    } else { throw new Error(result.error || 'Server error'); }
                } catch (err) {
                    messageDiv.className = 'error';
                    messageDiv.innerHTML = '❌ Error: ' + err.message;
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
    drive_id = get_user_drive_folder_id()
    sheet_id = get_user_spreadsheet_id()
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Photoshare Management Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #eef2f5; margin: 0; padding: 24px; color: #1a1f36; }
            .app-container { max-width: 1200px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
            .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
            .top-bar-left { display: flex; gap: 12px; }
            .top-bar-right { display: flex; align-items: center; gap: 16px; }
            
            .btn { padding: 10px 18px; border-radius: 8px; font-weight: 600; font-size: 14px; border: none; cursor: pointer; transition: all 0.15s ease; text-decoration: none; display: inline-flex; align-items: center; }
            .btn:disabled { opacity: 0.5; cursor: not-allowed; }
            .btn-blue { background: #3b82f6; color: white; }
            .btn-blue:hover:not(:disabled) { background: #2563eb; }
            .btn-green { background: #10b981; color: white; }
            .btn-green:hover:not(:disabled) { background: #059669; }
            .btn-light { background: #e5e7eb; color: #374151; }
            .btn-light:hover:not(:disabled) { background: #d1d5db; }
            .btn-sm { padding: 6px 12px; font-size: 13px; font-weight: 500; border-radius: 6px; }
            
            .card { background: white; padding: 20px 24px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
            .card-title { font-size: 16px; font-weight: 700; color: #111827; margin: 0 0 16px 0; display: flex; justify-content: space-between; align-items: center; }
            
            .search-input { width: 100%; padding: 10px 16px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; box-sizing: border-box; margin-bottom: 12px; }
            .config-bar { display: flex; gap: 10px; margin-bottom: 15px; background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; }
            .config-bar input { flex: 1; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; }

            .table-container { max-height: 340px; overflow-y: auto; border: 1px solid #f3f4f6; border-radius: 8px; }
            .data-table { width: 100%; border-collapse: collapse; text-align: left; }
            .data-table th { font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; padding: 12px 16px; background: #f9fafb; position: sticky; top: 0; border-bottom: 1px solid #e5e7eb; }
            .data-table td { padding: 12px 16px; font-size: 14px; border-bottom: 1px solid #f3f4f6; color: #1f2937; }
            .data-table tr.selected { background-color: #eff6ff; }
            .data-table tr.clickable { cursor: pointer; }
            .data-table tr.clickable:hover { background-color: #f8fafc; }
            
            .console-box { background: #0b1329; color: #e2e8f0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; padding: 16px; border-radius: 10px; font-size: 13px; line-height: 1.6; max-height: 160px; overflow-y: auto; }
            .console-line { margin: 0; }
        </style>
    </head>
    <body>
        <div class="app-container">
            <div class="top-bar">
                <div class="top-bar-left">
                    <button id="btnProcessImage" class="btn btn-blue" disabled onclick="processImage()">Process Image</button>
                    <button id="btnShareAll" class="btn btn-green" disabled onclick="shareToAllMatched()">Share to all matched patrons</button>
                    <button class="btn btn-light" onclick="loadGrid1Folders()">Refresh</button>
                </div>
                <div class="top-bar-right">
                    <span style="font-size: 14px; color: #4b5563;">USER_EMAIL_PLACEHOLDER</span>
                    <a href="/logout" class="btn btn-light">Sign out</a>
                </div>
            </div>

            <!-- Workspace Config Bar -->
            <div class="card" style="padding: 16px 24px;">
                <div style="font-size: 13px; font-weight: 600; margin-bottom: 8px; color: #475569;">Active User Resource Config</div>
                <div class="config-bar">
                    <input type="text" id="driveFolderInput" value="DRIVE_FOLDER_PLACEHOLDER" placeholder="Google Drive Folder ID">
                    <input type="text" id="spreadsheetInput" value="SPREADSHEET_PLACEHOLDER" placeholder="Google Sheet ID">
                    <button class="btn btn-light btn-sm" onclick="updateUserConfig()">Save Workspace IDs</button>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Grid 1: Event Folders</div>
                <input type="text" id="folderSearchInput" class="search-input" onkeyup="filterGrid1()" placeholder="Search event folders by name...">
                <div class="table-container">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>FOLDER NAME</th>
                                <th>PHOTO COUNT</th>
                                <th>IDENTIFIED PATRONS</th>
                            </tr>
                        </thead>
                        <tbody id="grid1Body">
                            <tr><td colspan="3">Loading mapped drive directory...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="card-title">
                    <span>Grid 2: Matched Patrons <span id="selectedFolderTitle" style="color: #3b82f6; font-weight: normal;">(Select a folder above)</span></span>
                </div>
                <div class="table-container">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>FULL NAME</th>
                                <th>EMAIL</th>
                                <th>PHONE</th>
                                <th>MATCHED PHOTO COUNT</th>
                                <th style="text-align: right;">ACTION</th>
                            </tr>
                        </thead>
                        <tbody id="grid2Body">
                            <tr><td colspan="5" style="color: #6b7280;">No folder selected. Select an event folder from Grid 1 to view matched patrons.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="card-title" style="margin-bottom: 8px;">Output Log</div>
                <div class="console-box" id="consoleOutput">
                    <p class="console-line">[System] Multi-grid dashboard ready. Fetching workspace data...</p>
                </div>
            </div>
        </div>

        <script>
            let grid1Folders = [];
            let currentSelectedFolder = null;

            async function updateUserConfig() {
                const driveFolderId = document.getElementById('driveFolderInput').value.trim();
                const spreadsheetId = document.getElementById('spreadsheetInput').value.trim();
                
                logConsole('Updating workspace config IDs...');
                try {
                    const res = await fetch('/api/admin/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ drive_folder_id: driveFolderId, spreadsheet_id: spreadsheetId })
                    });
                    const data = await res.json();
                    if (data.error) throw new Error(data.error);
                    logConsole('Workspace IDs updated successfully!');
                    loadGrid1Folders();
                } catch (err) {
                    logConsole('ERROR updating config: ' + err.message);
                }
            }

            async function loadGrid1Folders() {
                logConsole('Fetching subfolders from mapped Drive folder...');
                try {
                    const res = await fetch('/api/admin/folders');
                    const data = await res.json();
                    if (data.error) throw new Error(data.error);
                    
                    grid1Folders = data.folders || [];
                    renderGrid1(grid1Folders);
                    logConsole('Grid 1 updated: Found ' + grid1Folders.length + ' event folder(s).');
                } catch (err) {
                    logConsole('ERROR loading Grid 1: ' + err.message);
                }
            }

            function renderGrid1(folders) {
                const tbody = document.getElementById('grid1Body');
                if (folders.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="3">No subfolders found inside target Drive folder.</td></tr>';
                    return;
                }

                tbody.innerHTML = folders.map(f => `
                    <tr class="clickable ${currentSelectedFolder && currentSelectedFolder.id === f.id ? 'selected' : ''}" onclick="selectFolder('${f.id}', '${escapeHtml(f.name)}', ${f.photoCount}, ${f.patronCount})">
                        <td><strong>${escapeHtml(f.name)}</strong></td>
                        <td>${f.photoCount} photo(s)</td>
                        <td>${f.patronCount} patron(s)</td>
                    </tr>
                `).join('');
            }

            function filterGrid1() {
                const query = document.getElementById('folderSearchInput').value.toLowerCase();
                const filtered = grid1Folders.filter(f => f.name.toLowerCase().includes(query));
                renderGrid1(filtered);
            }

            async function selectFolder(folderId, folderName, photoCount, patronCount) {
                currentSelectedFolder = { id: folderId, name: folderName, photoCount, patronCount };
                
                renderGrid1(grid1Folders);
                document.getElementById('selectedFolderTitle').innerText = '— ' + folderName;
                document.getElementById('btnProcessImage').disabled = false;
                
                logConsole(`Selected event folder "${folderName}". Loading matched patrons...`);
                await loadGrid2Patrons(folderId);
            }

            async function loadGrid2Patrons(folderId) {
                const tbody = document.getElementById('grid2Body');
                tbody.innerHTML = '<tr><td colspan="5">Loading matched patrons...</td></tr>';
                
                try {
                    const res = await fetch(`/api/admin/matched-patrons?folder_id=${folderId}`);
                    const data = await res.json();
                    if (data.error) throw new Error(data.error);
                    
                    const patrons = data.patrons || [];
                    
                    document.getElementById('btnShareAll').disabled = (patrons.length === 0);

                    if (patrons.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" style="color: #6b7280;">No patrons matched for this folder yet. Click "Process Image" to run facial recognition.</td></tr>';
                        return;
                    }

                    tbody.innerHTML = patrons.map(p => `
                        <tr>
                            <td><strong>${escapeHtml(p.name)}</strong></td>
                            <td>${escapeHtml(p.email)}</td>
                            <td>${escapeHtml(p.phone)}</td>
                            <td>${p.photoCount} photo(s)</td>
                            <td style="text-align: right;">
                                <button class="btn btn-light btn-sm" onclick="shareSinglePatron('${p.email}', '${escapeHtml(p.name)}')">Share</button>
                            </td>
                        </tr>
                    `).join('');
                    
                    logConsole(`Grid 2 populated: Found ${patrons.length} matched patron(s).`);
                } catch (err) {
                    logConsole('ERROR loading Grid 2: ' + err.message);
                }
            }

            async function processImage() {
                if (!currentSelectedFolder) return;
                logConsole(`Running facial recognition for folder "${currentSelectedFolder.name}"...`);
                document.getElementById('btnProcessImage').disabled = true;

                try {
                    const res = await fetch('/api/admin/process-folder', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ folder_id: currentSelectedFolder.id, folder_name: currentSelectedFolder.name })
                    });
                    const data = await res.json();
                    if (data.error) throw new Error(data.error);

                    logConsole(`Processing complete for "${currentSelectedFolder.name}". Found real matches for ${data.matched_patrons} patron(s).`);
                    await loadGrid1Folders();
                    await loadGrid2Patrons(currentSelectedFolder.id);
                } catch (err) {
                    logConsole('ERROR during facial recognition processing: ' + err.message);
                } finally {
                    document.getElementById('btnProcessImage').disabled = false;
                }
            }

            async function shareSinglePatron(email, name) {
                logConsole(`Sending matched photo bundle email to ${name} (${email})...`);
                try {
                    const res = await fetch('/api/admin/share-single', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ folder_id: currentSelectedFolder.id, email: email })
                    });
                    const data = await res.json();
                    if (data.error) throw new Error(data.error);
                    logConsole(`Email successfully sent to ${email}.`);
                } catch (err) {
                    logConsole(`ERROR sharing to ${email}: ` + err.message);
                }
            }

            async function shareToAllMatched() {
                if (!currentSelectedFolder) return;
                logConsole(`Dispatching photo emails to all unsent matched patrons for "${currentSelectedFolder.name}"...`);
                document.getElementById('btnShareAll').disabled = true;

                try {
                    const res = await fetch('/api/admin/share-all', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ folder_id: currentSelectedFolder.id })
                    });
                    const data = await res.json();
                    if (data.error) throw new Error(data.error);

                    logConsole(`Bulk email complete: Sent ${data.sent_count} email package(s).`);
                } catch (err) {
                    logConsole('ERROR in bulk share: ' + err.message);
                } finally {
                    document.getElementById('btnShareAll').disabled = false;
                }
            }

            function logConsole(msg) {
                const box = document.getElementById('consoleOutput');
                const time = new Date().toLocaleTimeString();
                box.innerHTML = `<p class="console-line">[${time}] ${escapeHtml(msg)}</p>` + box.innerHTML;
            }

            function escapeHtml(str) {
                return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
            }

            loadGrid1Folders();
        </script>
    </body>
    </html>
    '''
    return html.replace('USER_EMAIL_PLACEHOLDER', email).replace('DRIVE_FOLDER_PLACEHOLDER', drive_id).replace('SPREADSHEET_PLACEHOLDER', sheet_id)

@app.route('/api/admin/config', methods=['POST'])
def api_update_config():
    if 'credentials' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    drive_folder_id = data.get('drive_folder_id')
    spreadsheet_id = data.get('spreadsheet_id')

    if drive_folder_id:
        session['drive_folder_id'] = drive_folder_id
    if spreadsheet_id:
        session['spreadsheet_id'] = spreadsheet_id

    return jsonify({"success": True})

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
    authorization_url, state = flow.authorization_url(
        access_type='offline', 
        include_granted_scopes='true',
        prompt='consent'
    )
    session['state'] = state
    if hasattr(flow, 'code_verifier') and flow.code_verifier:
        session['code_verifier'] = flow.code_verifier

    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    try:
        state = session.get('state', None)
        if not state:
            return "<h3>Error: Session state lost during redirect.</h3>", 400

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
        if 'code_verifier' in session:
            flow.code_verifier = session['code_verifier']
        
        authorization_response = request.url
        if authorization_response.startswith('http://'):
            authorization_response = authorization_response.replace('http://', 'https://', 1)
            
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials

        user_info_service = build('oauth2', 'v2', credentials=creds)
        user_info = user_info_service.userinfo().get().execute()
        email = user_info.get('email')

        # DYNAMIC USER REGISTRATION: Automatically append new Google authenticated users to ALLOWED_USERS
        if email:
            ALLOWED_USERS.add(email)

        creds_dict = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        
        session['credentials'] = creds_dict
        session['user_email'] = email
        save_creds_to_disk(creds_dict)
        
        # Load user specific IDs or defaults
        user_cfg = DEFAULT_USER_CONFIGS.get(email, {})
        session['spreadsheet_id'] = user_cfg.get('spreadsheet_id', get_user_spreadsheet_id())
        session['drive_folder_id'] = user_cfg.get('drive_folder_id', get_user_drive_folder_id())

        return redirect('/dashboard')

    except Exception as e:
        return f"<h1>Internal Error:</h1><pre>{traceback.format_exc()}</pre>", 500

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
    encodings = extract_face_embeddings(img_bytes)
    if not encodings:
        return jsonify({"error": "Submission rejected: No face detected in uploaded selfie."}), 400

    embedding_json = json.dumps(encodings[0].tolist())

    creds_to_use = session.get('credentials') or load_creds()
    if not creds_to_use:
        return jsonify({"error": "Server not authenticated with Google Sheets yet. Admin must log in once at /api/auth/login to authorize guest check-ins."}), 503

    try:
        _, sheets_srv, _ = get_google_services(creds_to_use)
        
        new_row = [[name, email, phone, datetime.utcnow().isoformat(), embedding_json]]
        
        sheets_srv.spreadsheets().values().append(
            spreadsheetId=get_user_spreadsheet_id(),
            range="Sheet1!A:E",
            valueInputOption="USER_ENTERED",
            body={"values": new_row}
        ).execute()

        return jsonify({"success": True, "version": VERSION})
    except Exception as e:
        return jsonify({"error": f"Failed to append to Google Sheets: {str(e)}"}), 500

@app.route('/api/admin/folders')
def api_get_folders():
    if 'credentials' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        drive_srv, sheets_srv, _ = get_google_services(session['credentials'])
        target_folder_id = get_user_drive_folder_id()
        
        try:
            root_folder = drive_srv.files().get(fileId=target_folder_id, fields="id, name").execute()
        except Exception as err:
            return jsonify({"error": f"Unable to access Drive Folder ID ({target_folder_id}). Details: {str(err)}"}), 400

        photoz_id = root_folder['id']
        
        sub_query = f"'{photoz_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        sub_res = drive_srv.files().list(
            q=sub_query, 
            fields="files(id, name, createdTime)", 
            orderBy="createdTime desc"
        ).execute()
        event_folders = sub_res.get('files', [])
        
        results = []
        for f in event_folders:
            folder_id = f['id']
            folder_name = f['name']
            
            file_query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
            file_res = drive_srv.files().list(q=file_query, fields="files(id)").execute()
            photo_count = len(file_res.get('files', []))
            
            patron_count = 0
            try:
                sheet_data = sheets_srv.spreadsheets().values().get(spreadsheetId=get_user_spreadsheet_id(), range="matchedfaces!A2:G").execute()
                rows = sheet_data.get('values', [])
                matched_patrons = set(r[2] for r in rows if len(r) >= 3 and r[0] == folder_id)
                patron_count = len(matched_patrons)
            except Exception:
                patron_count = 0

            results.append({
                "id": folder_id,
                "name": folder_name,
                "photoCount": photo_count,
                "patronCount": patron_count
            })
            
        return jsonify({"folders": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/matched-patrons')
def api_matched_patrons():
    if 'credentials' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    folder_id = request.args.get('folder_id')
    if not folder_id:
        return jsonify({"error": "Missing folder_id"}), 400

    try:
        _, sheets_srv, _ = get_google_services(session['credentials'])
        
        matched_data = []
        try:
            matched_res = sheets_srv.spreadsheets().values().get(
                spreadsheetId=get_user_spreadsheet_id(), 
                range="matchedfaces!A2:G"
            ).execute()
            matched_data = matched_res.get('values', [])
        except Exception:
            matched_data = []

        results = []
        for row in matched_data:
            if len(row) >= 5 and row[0] == folder_id:
                results.append({
                    "name": row[1] if len(row) > 1 else "N/A",
                    "email": row[2] if len(row) > 2 else "N/A",
                    "phone": row[3] if len(row) > 3 else "N/A",
                    "photoCount": row[4] if len(row) > 4 else "0"
                })
            
        return jsonify({"patrons": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/process-folder', methods=['POST'])
def api_process_folder():
    if 'credentials' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json() or {}
    folder_id = data.get('folder_id')
    if not folder_id:
        return jsonify({"error": "Missing folder_id"}), 400

    try:
        drive_srv, sheets_srv, _ = get_google_services(session['credentials'])
        
        files_res = drive_srv.files().list(
            q=f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false", 
            fields="files(id, name, webViewLink)"
        ).execute()
        image_files = files_res.get('files', [])
        
        if not image_files:
            return jsonify({"success": True, "processed_count": 0, "message": "No images found."})

        patron_data = []
        try:
            p_res = sheets_srv.spreadsheets().values().get(spreadsheetId=get_user_spreadsheet_id(), range="Sheet1!A2:E").execute()
            patron_data = p_res.get('values', [])
        except Exception:
            patron_data = []

        if not patron_data:
            return jsonify({"error": "No registered patrons found in Sheet1."}), 400

        known_patrons = []
        for p in patron_data:
            if len(p) >= 5:
                try:
                    encoding = np.array(json.loads(p[4]))
                    known_patrons.append({
                        "name": p[0],
                        "email": p[1],
                        "phone": p[2],
                        "encoding": encoding,
                        "matched_links": []
                    })
                except Exception:
                    continue

        if not known_patrons:
            return jsonify({"error": "No patrons with valid face encodings found in Sheet1."}), 400

        for img in image_files:
            try:
                img_content = drive_srv.files().get_media(fileId=img['id']).execute()
                img_encodings = extract_face_embeddings(img_content)
                img_link = img.get('webViewLink', f"https://drive.google.com/file/d/{img['id']}/view")

                is_matched = False
                for face_enc in img_encodings:
                    for patron in known_patrons:
                        distance = face_recognition.face_distance([patron['encoding']], face_enc)[0]
                        if distance <= 0.6:
                            if img_link not in patron['matched_links']:
                                patron['matched_links'].append(img_link)
                                is_matched = True

                if is_matched:
                    make_file_public(drive_srv, img['id'])

            except Exception as file_err:
                print(f"Error processing image {img['id']}: {file_err}")
                continue

        timestamp_now = datetime.utcnow().isoformat()
        new_matched_rows = []

        for patron in known_patrons:
            if patron['matched_links']:
                links_str = "\n".join(patron['matched_links'])
                match_count = len(patron['matched_links'])

                new_matched_rows.append([
                    folder_id,
                    patron['name'],
                    patron['email'],
                    patron['phone'],
                    match_count,
                    links_str,
                    timestamp_now
                ])

        if new_matched_rows:
            sheets_srv.spreadsheets().values().append(
                spreadsheetId=get_user_spreadsheet_id(),
                range="matchedfaces!A:G",
                valueInputOption="USER_ENTERED",
                body={"values": new_matched_rows}
            ).execute()

        return jsonify({"success": True, "processed_count": len(image_files), "matched_patrons": len(new_matched_rows)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/share-single', methods=['POST'])
def api_share_single():
    if 'credentials' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    folder_id = data.get('folder_id')
    target_email = data.get('email')

    if not folder_id or not target_email:
        return jsonify({"error": "Missing folder_id or email"}), 400

    try:
        drive_srv, sheets_srv, gmail_srv = get_google_services(session['credentials'])
        
        res = sheets_srv.spreadsheets().values().get(spreadsheetId=get_user_spreadsheet_id(), range="matchedfaces!A2:G").execute()
        rows = res.get('values', [])

        target_row = None
        for r in rows:
            if len(r) >= 6 and r[0] == folder_id and r[2] == target_email:
                target_row = r
                break

        if not target_row:
            return jsonify({"error": f"No matched photos found in sheet for {target_email} in folder {folder_id}."}), 404

        name = target_row[1]
        links = target_row[5].split("\n")

        for link in links:
            if "/file/d/" in link:
                file_id = link.split("/file/d/")[1].split("/")[0]
                make_file_public(drive_srv, file_id)

        send_photo_email(gmail_srv, target_email, name, links)
        return jsonify({"success": True, "status": f"Email successfully dispatched to {target_email}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/share-all', methods=['POST'])
def api_share_all():
    if 'credentials' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    folder_id = data.get('folder_id')

    if not folder_id:
        return jsonify({"error": "Missing folder_id"}), 400

    try:
        drive_srv, sheets_srv, gmail_srv = get_google_services(session['credentials'])
        
        res = sheets_srv.spreadsheets().values().get(spreadsheetId=get_user_spreadsheet_id(), range="matchedfaces!A2:G").execute()
        rows = res.get('values', [])

        sent_count = 0
        for r in rows:
            if len(r) >= 6 and r[0] == folder_id:
                name = r[1]
                email = r[2]
                links = r[5].split("\n")
                
                for link in links:
                    if "/file/d/" in link:
                        file_id = link.split("/file/d/")[1].split("/")[0]
                        make_file_public(drive_srv, file_id)

                try:
                    send_photo_email(gmail_srv, email, name, links)
                    sent_count += 1
                except Exception as mail_err:
                    print(f"Failed to email {email}: {mail_err}")

        return jsonify({"success": True, "sent_count": sent_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
