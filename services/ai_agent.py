import os
import json
from openai import OpenAI
from core.status import status_manager

class AIAgent:
    def __init__(self, api_key, model="deepseek/deepseek-chat"):
        self.api_key = api_key
        self.base_url = "https://api.kilo.ai/api/gateway/"
        self.model = model

    def generate_viral_metadata(self, original_title, original_description):
        if not self.api_key:
            return original_title, "Uploaded via InstaToYTAgent #Shorts #Reels"

        status_manager.update(action="AI Analysis", progress=75, step="Generating Viral Captions")
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        context = f"Title: {original_title}\nCaption: {original_description}"
        
        prompt = f"""
        You are a viral YouTube Shorts expert. Create a catchy title and a high-engagement description based on the following Instagram Reel metadata:
        
        {context}
        
        Guidelines:
        1. The YouTube title should be short (<60 chars) and clicky.
        2. The description should summarize the video nicely.
        3. Include 3-5 relevant viral hashtags.
        
        Respond STRICTLY in JSON format: {{"title": "...", "description": "..."}}
        """
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            data = json.loads(response.choices[0].message.content)
            title = data.get("title", original_title)
            description = data.get("description", "Uploaded via InstaToYTAgent #Shorts")
            status_manager.log(f"🤖 AI Generated Title: {title}")
            return title, description
        except Exception as e:
            status_manager.log(f"❌ Kilo AI failed: {e}")
            return original_title, "Uploaded via InstaToYTAgent #Shorts"
