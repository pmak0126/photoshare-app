        "service": "PhotoShare Server Gateway",
        "message": "Production ML engine is loaded and awaiting trigger runs."
    }

@app.post("/process-event")
async def process_event(request: Request):
    try:
        body = await request.json()
        creds_data = body.get("credentials")
        event_folder_id = body.get("folderId")
        root_folder_id = body.get("rootFolderId")
        tolerance = float(body.get("tolerance", 0.6))
        
        if not creds_data or not event_folder_id or not root_folder_id:
            raise HTTPException(status_code=400, detail="Missing required configuration mapping elements.")
            
        creds = Credentials.from_authorized_user_info(creds_data)
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        sheets_list = drive_service.files().list(
            q=f"'{root_folder_id}' in parents and name = 'patroncontact' and mimeType = 'application/vnd.google-apps.spreadsheet'",
            fields="files(id)"
        ).execute()
        
        if not sheets_list.get('files'):
            raise HTTPException(status_code=404, detail="patroncontact master sheet database not found.")
            
        sheet_id = sheets_list['files'][0]['id']
        sheet_data = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Sheet1!A2:G"
        ).execute()
        
        patron_rows = sheet_data.get('values', [])
        known_embeddings = []
        known_contact_ids = []
        
        for row in patron_rows:
            if len(row) >= 6:
                try:
                    embedding = json.loads(row[5])
                    known_embeddings.append(np.array(embedding))
                    known_contact_ids.append(row[0])
                except Exception:
                    continue
                    
        files_results = drive_service.files().list(
            q=f"'{event_folder_id}' in parents and mimeType contains 'image/'",
            fields="files(id, name, webViewLink, webContentLink)"
        ).execute()
        files = files_results.get('files', [])
        
        matched_results = []
        
        for file in files:
            file_request = drive_service.files().get_media(fileId=file['id'])
            file_stream = io.BytesIO()
            downloader = MediaIoBaseDownload(file_stream, file_request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
                
            file_stream.seek(0)
            
            try:
                image = fr.load_image_file(file_stream)
                face_locations = fr.face_locations(image, model="hog")
                face_encodings = fr.face_encodings(image, face_locations)
                
                for encoding in face_encodings:
                    if len(known_embeddings) == 0:
                        break
                        
                    distances = fr.face_distance(known_embeddings, encoding)
                    best_match_idx = np.argmin(distances)
                    
                    if distances[best_match_idx] <= tolerance:
                        matched_id = known_contact_ids[best_match_idx]
                        matched_results.append({
                            "contact_id": matched_id,
                            "file_name": file['name'],
                            "web_link": file['webViewLink']
                        })
            except Exception:
                continue
                
        match_sheet_list = drive_service.files().list(
            q=f"'{root_folder_id}' in parents and name = 'matchedfaces' and mimeType = 'application/vnd.google-apps.spreadsheet'",
            fields="files(id)"
        ).execute()
        
        target_match_sheet_id = ""
        if not match_sheet_list.get('files'):
            new_sheet_metadata = {
                'name': 'matchedfaces',
                'parents': [root_folder_id],
                'mimeType': 'application/vnd.google-apps.spreadsheet'
            }
            new_sheet = drive_service.files().create(body=new_sheet_metadata, fields='id').execute()
            target_match_sheet_id = new_sheet['id']
            sheets_service.spreadsheets().values().append(
                spreadsheetId=target_match_sheet_id,
                range="Sheet1!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [["Event_Folder_ID", "Contact_ID", "Photo_Links", "Match_Count"]]}
            ).execute()
        else:
            target_match_sheet_id = match_sheet_list['files'][0]['id']
            
        aggregated_matches = {}
        for match in matched_results:
            c_id = match['contact_id']
            if c_id not in aggregated_matches:
                aggregated_matches[c_id] = []
            aggregated_matches[c_id].append(match['web_link'])
            
        upload_rows = []
        for c_id, links in aggregated_matches.items():
            upload_rows.append([
                event_folder_id,
                c_id,
                json.dumps(links),
                len(links)
            ])
            
        if upload_rows:
            sheets_service.spreadsheets().values().append(
                spreadsheetId=target_match_sheet_id,
                range="Sheet1!A2",
                valueInputOption="USER_ENTERED",
                body={"values": upload_rows}
            ).execute()
            
        return {
            "success": True, 
            "total_scanned": len(files), 
            "matches_identified": len(upload_rows)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
EOF

cat << 'EOF' > requirements.txt
fastapi==0.110.0
uvicorn==0.28.0
numpy==1.26.4
google-api-python-client==2.122.0
google-auth==2.28.2
EOF

cat << 'EOF' > Dockerfile
FROM ageitgey/face_recognition:latest
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python3", "main.py"]
EOF

gcloud run deploy photoshare-server-matcher     --source .     --region us-central1     --allow-unauthenticated     --memory=2Gi     --cpu=1
# 1. Clean up stray files in home folder
rm -f ~/main.py ~/requirements.txt ~/Dockerfile
# 2. Switch to the correct workspace directory
cd ~/photoshare-backend
# 3. Write optimized files
cat << 'EOF' > main.py
import os
import io
import json
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import face_recognition as fr

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "PhotoShare Server Gateway",
        "message": "Production ML engine is loaded and awaiting trigger runs."
    }

@app.post("/process-event")
async def process_event(request: Request):
    try:
        body = await request.json()
        creds_data = body.get("credentials")      # OAuth tokens forwarded from UI 2
        event_folder_id = body.get("folderId")    # Target Event Photo Folder ID
        root_folder_id = body.get("rootFolderId")  # Master Directory Folder ID
        tolerance = float(body.get("tolerance", 0.6)) # Euclidean threshold
        
        if not creds_data or not event_folder_id or not root_folder_id:
            raise HTTPException(status_code=400, detail="Missing required configuration mapping elements.")
            
        # 1. Authorize APIs using the photographer's login credentials
        creds = Credentials.from_authorized_user_info(creds_data)
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        # 2. Retrieve patron contact face embeddings from Google Sheets
        sheets_list = drive_service.files().list(
            q=f"'{root_folder_id}' in parents and name = 'patroncontact' and mimeType = 'application/vnd.google-apps.spreadsheet'",
            fields="files(id)"
        ).execute()
        
        if not sheets_list.get('files'):
            raise HTTPException(status_code=404, detail="patroncontact master sheet database not found.")
            
        sheet_id = sheets_list['files'][0]['id']
        sheet_data = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Sheet1!A2:G" # Read rows (skipping header)
        ).execute()
        
        patron_rows = sheet_data.get('values', [])
        known_embeddings = []
        known_contact_ids = []
        
        for row in patron_rows:
            if len(row) >= 6:
                try:
                    # Column 5 contains the stringified 128D array from face-api.js
                    embedding = json.loads(row[5])
                    known_embeddings.append(np.array(embedding))
                    known_contact_ids.append(row[0]) # Column 0 has Contact_ID
                except Exception:
                    continue # Skip malformed row entries gracefully
                    
        # 3. Fetch list of event photos to compare
        files_results = drive_service.files().list(
            q=f"'{event_folder_id}' in parents and mimeType contains 'image/'",
            fields="files(id, name, webViewLink, webContentLink)"
        ).execute()
        files = files_results.get('files', [])
        
        matched_results = []
        
        # 4. Process event images sequentially over internal high-speed memory streams
        for file in files:
            # Download photo from Google Drive into RAM
            file_request = drive_service.files().get_media(fileId=file['id'])
            file_stream = io.BytesIO()
            downloader = MediaIoBaseDownload(file_stream, file_request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
                
            file_stream.seek(0)
            
            # Load file directly into machine learning framework
            try:
                image = fr.load_image_file(file_stream)
                face_locations = fr.face_locations(image, model="hog") # Rapid CPU-optimized model
                face_encodings = fr.face_encodings(image, face_locations)
                
                for encoding in face_encodings:
                    if len(known_embeddings) == 0:
                        break
                        
                    # Calculate vector distances
                    distances = fr.face_distance(known_embeddings, encoding)
                    best_match_idx = np.argmin(distances)
                    
                    if distances[best_match_idx] <= tolerance:
                        matched_id = known_contact_ids[best_match_idx]
                        matched_results.append({
                            "contact_id": matched_id,
                            "file_name": file['name'],
                            "web_link": file['webViewLink']
                        })
            except Exception:
                continue # Skip unreadable image files (corrupt headers, zero-byte uploads)
                
        # 5. Populate or Update the matched results back in Google Sheets
        match_sheet_list = drive_service.files().list(
            q=f"'{root_folder_id}' in parents and name = 'matchedfaces' and mimeType = 'application/vnd.google-apps.spreadsheet'",
            fields="files(id)"
        ).execute()
        
        target_match_sheet_id = ""
        if not match_sheet_list.get('files'):
            # Generate sheet from scratch if it doesn't exist
            new_sheet_metadata = {
                'name': 'matchedfaces',
                'parents': [root_folder_id],
                'mimeType': 'application/vnd.google-apps.spreadsheet'
            }
            new_sheet = drive_service.files().create(body=new_sheet_metadata, fields='id').execute()
            target_match_sheet_id = new_sheet['id']
            sheets_service.spreadsheets().values().append(
                spreadsheetId=target_match_sheet_id,
                range="Sheet1!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [["Event_Folder_ID", "Contact_ID", "Photo_Links", "Match_Count"]]}
            ).execute()
        else:
            target_match_sheet_id = match_sheet_list['files'][0]['id']
            
        # Group matches by User Contact ID
        aggregated_matches = {}
        for match in matched_results:
            c_id = match['contact_id']
            if c_id not in aggregated_matches:
                aggregated_matches[c_id] = []
            aggregated_matches[c_id].append(match['web_link'])
            
        # Compile spreadsheet rows
        upload_rows = []
        for c_id, links in aggregated_matches.items():
            upload_rows.append([
                event_folder_id,
                c_id,
                json.dumps(links),
                len(links)
            ])
            
        if upload_rows:
            sheets_service.spreadsheets().values().append(
                spreadsheetId=target_match_sheet_id,
                range="Sheet1!A2",
                valueInputOption="USER_ENTERED",
                body={"values": upload_rows}
            ).execute()
            
        return {
            "success": True, 
            "total_scanned": len(files), 
            "matches_identified": len(upload_rows)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
EOF

cat << 'EOF' > requirements.txt
fastapi==0.110.0
uvicorn==0.28.0
numpy==1.26.4
google-api-python-client==2.122.0
google-auth==2.28.2
face-recognition==1.3.0
EOF

cat << 'EOF' > Dockerfile
FROM python:3.10-slim

# Install sequential compilation dependencies needed to build dlib/face-recognition cleanly
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    gfortran \
    pkg-config \
    libgraphicsmagick1-dev \
    libatlas-base-dev \
    libjpeg-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python3", "main.py"]
EOF

echo "All production workspace files successfully restored inside ~/photoshare-backend!"
gcloud run deploy photoshare-server-matcher     --source .     --region us-central1     --allow-unauthenticated     --memory=2Gi     --cpu=1
# Ensure we are in the correct workspace directory
cd ~/photoshare-backend
# Overwrite requirements.txt with instant prebuilt wheels
cat << 'EOF' > requirements.txt
fastapi==0.110.0
uvicorn==0.28.0
numpy==1.26.4
google-api-python-client==2.122.0
google-auth==2.28.2
dlib-bin==19.24.2
face-recognition-models>=0.3.0
Click>=6.0
Pillow>=6.0.0
EOF

# Overwrite Dockerfile to run the no-dependency ML install
cat << 'EOF' > Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Copy the dependency index
COPY requirements.txt .

# Install the pre-compiled binary dependencies instantly
RUN pip install --no-cache-dir -r requirements.txt

# Install face-recognition using the no-deps flag to completely bypass compiler execution
RUN pip install --no-cache-dir face-recognition==1.3.0 --no-deps

# Copy the FastAPI app code
COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
EOF

gcloud run deploy photoshare-server-matcher     --source .     --region us-central1     --allow-unauthenticated     --memory=2Gi     --cpu=1
gcloud run deploy photoshare-server-matcher   --source=https://github.com/makwanapranav26/photoshare-backend   --region=us-central1
cd ~/photoshare-backend
gcloud run deploy photoshare-server-matcher   --source .   --region us-central1
ls
gcloud run deploy photoshare-server-matcher   --source .   --region us-central1   --project photoshare-system
nano setup_project_v1.sh
cat << 'EOF' > setup_project_v1.sh
# 1. Download the workspace setup script
cat << 'EOF' > setup_and_push_pipeline.sh
# (The system has loaded the script contents inside setup_and_push_pipeline.sh)
EOF

# 2. Run the script to write index.html, readme, and the workflows folder
bash setup_and_push_pipeline.sh
# 1. Enter the repository folder
cd ~/photoshare-backend
# 2. Initialize local Git repository
git init
# 3. Add files and the workflow settings
git add .
# 4. Create your first commit
git commit -m "Initial Web Application Release v1"
# 5. Point default branch to main
git branch -M main
# 6. Link to your GitHub repository URL
git remote add origin https://github.com/makwanapranav26/photoshare-backend.git
# 7. Push to GitHub
# (Note: Use your GitHub Personal Access Token as the password when prompted)
git push -u origin main
# Create the service account
gcloud iam service-accounts create github-actions-deployer --display-name="GitHub Deployer"
# Grant Admin access to Cloud Run, Storage, Cloud Build, and Container Registry
gcloud projects add-iam-policy-binding photoshare-system     --member="serviceAccount:github-actions-deployer@photoshare-system.iam.gserviceaccount.com"     --role="roles/run.admin"
gcloud projects add-iam-policy-binding photoshare-system     --member="serviceAccount:github-actions-deployer@photoshare-system.iam.gserviceaccount.com"     --role="roles/storage.admin"
gcloud projects add-iam-policy-binding photoshare-system     --member="serviceAccount:github-actions-deployer@photoshare-system.iam.gserviceaccount.com"     --role="roles/cloudbuild.builds.editor"
gcloud projects add-iam-policy-binding photoshare-system     --member="serviceAccount:github-actions-deployer@photoshare-system.iam.gserviceaccount.com"     --role="roles/viewer"
# Generate the JSON access key file
gcloud iam service-accounts keys create sa-key.json     --iam-account=github-actions-deployer@photoshare-system.iam.gserviceaccount.com
cat sa-key.json
ls
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
rm Procfile.txt
ls
rm requirement.txt
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
nano server.py
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
nano server.py
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
nano server.py
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
nano server.py
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
nano server.py
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
nano server.py
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
nano server.py
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
nano server.py
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
nano server.py
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
nano server.py
gcloud run deploy photoshare-app     --source .     --region us-central1     --allow-unauthenticated     --set-env-vars="FLASK_SECRET_KEY=enter_a_long_secure_random_string_here"
git init
git add .
git commit -m "Initial commit: Complete Flask backend with OAuth and Dashboard"
git branch -M main
git remote add origin https://github.com/pmak0126/photoshare-app.git
git push -u origin main
# Completely reset the local git repository tracking history
rm -rf .git
# Re-initialize git clean
git init
git branch -M main
# Tell Git to ignore secret files and python caches
cat <<EOT > .gitignore
client_secret.json
*.pyc
__pycache__/
.env
EOT

