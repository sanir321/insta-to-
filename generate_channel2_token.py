from google_auth_oauthlib.flow import InstalledAppFlow
import pickle
import base64
import os

# Client secret file provided by the user
CLIENT_SECRET_FILE = 'client_secret_654287911326-mg7hl36pvk0iqr3pnikg34iujpb6hr8v.apps.googleusercontent.com.json'
TOKEN_PICKLE_FILE = 'youtube_token_channel2.pickle'
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def generate_token():
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"❌ Error: {CLIENT_SECRET_FILE} not found in the current directory.")
        return

    print(f"🌐 Initializing OAuth flow using {CLIENT_SECRET_FILE}...")
    try:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        # This will open a browser window
        creds = flow.run_local_server(port=0)

        # Save token to pickle file
        print(f"💾 Saving token to {TOKEN_PICKLE_FILE}...")
        with open(TOKEN_PICKLE_FILE, 'wb') as f:
            pickle.dump(creds, f)

        # Encode to Base64
        with open(TOKEN_PICKLE_FILE, 'rb') as f:
            token_b64 = base64.b64encode(f.read()).decode()
            print("\n✅ SUCCESS! Here is your Base64 encoded token for Railway:")
            print("-" * 60)
            print(token_b64)
            print("-" * 60)
            print("\n👉 Copy the long string above and add it to Railway as YOUTUBE_TOKEN_B64_CHANNEL2")

    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    generate_token()
