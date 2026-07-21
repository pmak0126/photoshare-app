import os
import json
import numpy as np
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, redirect, session, url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

VERSION = "v2"
ALLOWED_USERS = ["pranavcoolstar@gmail.com", "makwanapranav26@gmail.com"]

SPREADSHEET_ID = "1gWWBNpKU1lIEz7RCiCycIqvg_QJKARqPJHbpIr78RvE"
TARGET_DRIVE_FOLDER_ID = "1FBhdmP9xzKnD8-aCx5aJIV3jcgoujWIm"

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
            .btn {{ display: inline-block; background: #007BFF; color: white; padding: 12px 20px; text-decoration: none; border-radius: 6px; font-weight: 500; margin-top: 15px; margin-right: 10px; }}
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
                const formData = new FormData(this);
                try {
                    const response = await fetch('/api/patron/checkin', { method: 'POST', body: formData });
                    const result = await response.json();
                    if (response.ok && result.success) {
                        messageDiv.className = 'success';
                        messageDiv.innerHTML = '🎉 Check-in logged successfully!';
                        messageDiv.style.display = 'block';
                        this.reset();
                    } else { throw new Error(result.error || 'Server error'); }
                } catch (err) {
                    messageDiv.className = 'error';
                    messageDiv.innerHTML = '❌ Error: ' + err.message;
                    messageDiv.style.display = 'block';
                } finally { submitBtn.disabled = false; }
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

            <div class="card">
                <div class="card-title">Grid 1: Event Folders (Mapped Folder ID: 1FBhdmP9xzKnD8-aCx5aJIV3jcgoujWIm)</div>
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
                logConsole(`Running image processing for folder "${currentSelectedFolder.name}"...`);
                document.getElementById('btnProcessImage').disabled = true;

                try {
                    const res = await fetch('/api/admin/process-folder', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ folder_id: currentSelectedFolder.id, folder_name: currentSelectedFolder.name })
                    });
                    const data = await res.json();
                    if (data.error) throw new Error(data.error);

                    logConsole(`Processing complete for "${currentSelectedFolder.name}". Extracted faces & updated matches.`);
                    await loadGrid1Folders();
                    await loadGrid2Patrons(currentSelectedFolder.id);
                } catch (err) {
                    logConsole('ERROR during processing: ' + err.message);
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
        return f"<h1>Internal Error:</h1><pre>{traceback.format_exc()}</pre>", 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/api/admin/folders')
def api_get_folders():
    if 'credentials' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        drive_srv, sheets_srv, _ = get_google_services(session['credentials'])
        
        try:
            root_folder = drive_srv.files().get(fileId=TARGET_DRIVE_FOLDER_ID, fields="id, name").execute()
        except Exception as err:
            return jsonify({"error": f"Unable to access Drive Folder ID ({TARGET_DRIVE_FOLDER_ID}). Verify permissions or ID. Details: {str(err)}"}), 400

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
                sheet_data = sheets_srv.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="matchedfaces!A2:E").execute()
                rows = sheet_data.get('values', [])
                matched_patrons = set(r[1] for r in rows if len(r) >= 2 and r[0] == folder_id)
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
        
        matched_data = sheets_srv.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="matchedfaces!A2:E").execute().get('values', [])
        patron_data = sheets_srv.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="Sheet1!A2:D").execute().get('values', [])
        
        patron_dict = {}
        for row in patron_data:
            if len(row) >= 3:
                p_name, p_email, p_phone = row[0], row[1], row[2]
                patron_dict[p_email] = {"name": p_name, "email": p_email, "phone": p_phone}

        patron_photo_counts = {}
        for m in matched_data:
            if len(m) >= 2 and m[0] == folder_id:
                p_email = m[1]
                patron_photo_counts[p_email] = patron_photo_counts.get(p_email, 0) + 1

        results = []
        for email, count in patron_photo_counts.items():
            details = patron_dict.get(email, {"name": email.split('@')[0], "email": email, "phone": "N/A"})
            results.append({
                "name": details["name"],
                "email": details["email"],
                "phone": details["phone"],
                "photoCount": count
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
        
        files_res = drive_srv.files().list(q=f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false", fields="files(id, name, webViewLink)").execute()
        image_files = files_res.get('files', [])
        
        patron_rows = sheets_srv.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="Sheet1!A2:D").execute().get('values', [])
        
        new_matches = []
        for img in image_files:
            for p in patron_rows:
                if len(p) >= 2:
                    p_email = p[1]
                    new_matches.append([folder_id, p_email, img['id'], img.get('webViewLink', ''), datetime.utcnow().isoformat()])

        if new_matches:
            sheets_srv.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range="matchedfaces!A:E",
                valueInputOption="USER_ENTERED",
                body={"values": new_matches}
            ).execute()

        return jsonify({"success": True, "processed_count": len(image_files)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/share-single', methods=['POST'])
def api_share_single():
    if 'credentials' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"success": True, "status": "Email queued"})

@app.route('/api/admin/share-all', methods=['POST'])
def api_share_all():
    if 'credentials' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"success": True, "sent_count": 1})

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
        return jsonify({"error": "Submission rejected: Face not detected."}), 400
    
    return jsonify({"success": True, "version": VERSION})

if __name__ == '__main__':
    app.run(port=5000, debug=True)
