import os
from dotenv import load_dotenv
from openai import OpenAI

# Load the .env file
load_dotenv()

KILO_API_KEY = os.getenv("KILO_API_KEY")
KILO_BASE_URL = "https://api.kilo.ai/api/gateway/"
KILO_MODEL = "deepseek/deepseek-chat"

def test_connection():
    if not KILO_API_KEY or KILO_API_KEY == "your_kilo_api_key_here":
        print("❌ Error: KILO_API_KEY is not set in the .env file.")
        return

    print(f"🔗 Connecting to Kilo AI Gateway ({KILO_MODEL})...")
    
    try:
        client = OpenAI(api_key=KILO_API_KEY, base_url=KILO_BASE_URL)
        
        response = client.chat.completions.create(
            model=KILO_MODEL,
            messages=[{"role": "user", "content": "Write a short, viral YouTube title for an Instagram Reel about a cute kitten."}],
            max_tokens=50
        )
        
        print("\n✅ Kilo AI is WORKING!")
        print(f"🤖 AI Response: {response.choices[0].message.content.strip()}")
        
    except Exception as e:
        print(f"❌ Kilo AI failed: {e}")

if __name__ == "__main__":
    test_connection()
