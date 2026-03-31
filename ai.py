import instaloader
import time
import random
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def scrape_reel_urls_in_chunks(target_username, output_filename="reel_urls.txt", chunk_size=30, pause_minutes=5):
    # Initialize Instaloader
    L = instaloader.Instaloader()
    
    # 🔑 Login Support (Recommended for avoiding 403 Forbidden)
    ig_username = os.getenv("IG_USERNAME")
    ig_password = os.getenv("IG_PASSWORD")
    
    if ig_username and ig_password:
        print(f"🔐 Logging into Instagram as {ig_username}...")
        try:
            L.login(ig_username, ig_password)
            print("✅ Login successful!")
        except Exception as e:
            print(f"⚠️ Login failed: {e}. Attempting to scrape publicly...")
    else:
        print("💡 No IG_USERNAME found in .env. Attempting public scrape...")

    print(f"🔍 Fetching profile: {target_username}...")
    try:
        profile = instaloader.Profile.from_username(L.context, target_username)
    except Exception as e:
        print(f"❌ Failed to load profile: {e}")
        return

    print(f"Scanning posts for {target_username} in chunks of {chunk_size}...")
    
    total_reels = 0
    current_chunk_count = 0
    
    # Open the text file in 'a' (append) mode. 
    # This prevents overwriting your file if you restart the script.
    with open(output_filename, "a") as file:
        
        for post in profile.get_posts():
            if post.is_video:
                reel_url = f"https://www.instagram.com/reel/{post.shortcode}/"
                
                # Write to the file and force it to save to the hard drive immediately 
                file.write(reel_url + "\n")
                file.flush() 
                
                total_reels += 1
                current_chunk_count += 1
                
                print(f"Saved: {reel_url} | Chunk progress: {current_chunk_count}/{chunk_size}")
                
                # Add a randomized short delay between individual posts (1 to 3 seconds)
                # This makes the scraper look much more human.
                time.sleep(random.uniform(1.0, 3.0))
                
                # Check if we have completed a chunk
                if current_chunk_count >= chunk_size:
                    print(f"\n⏸️ Chunk of {chunk_size} completed.")
                    print(f"😴 Sleeping for {pause_minutes} minutes to avoid rate limits...")
                    
                    # Pause the script (minutes converted to seconds)
                    time.sleep(pause_minutes * 60) 
                    
                    print("▶️ Waking up! Resuming the next chunk...\n")
                    # Reset the chunk counter for the next batch
                    current_chunk_count = 0 

    print(f"\n✅ Done! Successfully appended a total of {total_reels} Reel URLs to {output_filename}")

# --- Execute the function ---
if __name__ == "__main__":
    account_to_scrape = "stravity.official" 
    
    # You can adjust how many Reels per chunk and how long to wait between them
    scrape_reel_urls_in_chunks(
        target_username=account_to_scrape, 
        chunk_size=30,       # Scrape 25 reels at a time
        pause_minutes=0.5      # Wait 5 minutes between chunks
    )