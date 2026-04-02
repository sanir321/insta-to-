import os
import pickle
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request as GoogleRequest
from core.status import status_manager

class YouTubeService:
    def __init__(self, client_secrets_file, scopes, token_pickle_file=None):
        self.client_secrets_file = client_secrets_file
        self.token_pickle_file = token_pickle_file or "youtube_token.pickle"
        self.scopes = scopes
        self.service = None

    def get_authenticated_service(self):
        status_manager.update(action="Authenticating", progress=10, step="Google Auth")
        credentials = None
        if os.path.exists(self.token_pickle_file):
            with open(self.token_pickle_file, 'rb') as token:
                credentials = pickle.load(token)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(GoogleRequest())
            else:
                if os.environ.get("RAILWAY_PROJECT_ID") or os.environ.get("HEADLESS"):
                    file_name = os.path.basename(self.token_pickle_file)
                    status_manager.log(f"❌ ERROR: Token file '{file_name}' is missing or invalid.")
                    status_manager.log(f"👉 Ensure the corresponding Base64 environment variable is correctly set in Railway.")
                    raise Exception(f"Missing or invalid YouTube token: {file_name}")
                
                status_manager.log("🌐 Opening browser for YouTube authentication...")
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.scopes)
                credentials = flow.run_local_server(port=0)
            
            with open(self.token_pickle_file, 'wb') as token:
                pickle.dump(credentials, token)

        self.service = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
        return self.service

    def upload_video(self, file_path, title, description, privacy='unlisted'):
        status_manager.update(action="Uploading", progress=85, step="YouTube Shorts Upload")
        body = {
            'snippet': {
                'title': title[:100],
                'description': description,
                'tags': ['Shorts', 'Reels', 'Viral'],
                'categoryId': '22' # People & Blogs
            },
            'status': {
                'privacyStatus': privacy,
                'selfDeclaredMadeForKids': False
            }
        }

        insert_request = self.service.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        )

        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                status_manager.update(progress=85 + int(progress * 0.15), step=f"Uploading... {progress}%")

        status_manager.log(f"✅ Uploaded! ID: {response['id']}")
        return response['id']
