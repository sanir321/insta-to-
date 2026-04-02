import os
import json
from openai import OpenAI
from core.status import status_manager

class AIAgent:
    def __init__(self, api_key, model="deepseek/deepseek-chat"):
        self.api_key = api_key
        self.base_url = "https://api.kilo.ai/api/gateway/"
        self.model = model

    def generate_viral_metadata(self, original_title, original_description, channel_number=1):
        """
        Generate viral YouTube Shorts metadata.

        channel_number=1 (default): titles focused on confidence, action, and
        urgency with energetic emojis (🔥💪⚡).
        channel_number=2: titles focused on systems, mastery, and
        transformation with distinct emojis (🔐🧠✨).
        Both channels receive unique, SEO-friendly output so YouTube does not
        treat the uploads as duplicates.
        """
        channel_number = channel_number if channel_number in (1, 2) else 1

        if not self.api_key:
            return original_title, "Uploaded via InstaToYTAgent #Shorts #Reels"

        status_manager.update(
            action="AI Analysis",
            progress=75,
            step=f"Generating Viral Captions (Channel {channel_number})"
        )
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        context = f"Title: {original_title}\nCaption: {original_description}"

        if channel_number == 2:
            style_instructions = (
                "Channel 2 Style — focus on SYSTEMS, MASTERY, and TRANSFORMATION.\n"
                "- Frame the title as unlocking a method, code, or system (e.g. 'Unlock...', 'The ... System', 'Master the ...').\n"
                "- Use intellectual, aspirational language.\n"
                "- Preferred emojis: 🔐 🧠 ✨ 🎯 💡 (pick 1-2 max).\n"
                "- Description should highlight the deeper insight or skill being taught.\n"
                "- Hashtags should lean toward self-improvement, mindset, and mastery."
            )
        else:
            style_instructions = (
                "Channel 1 Style — focus on CONFIDENCE, ACTION, and URGENCY.\n"
                "- Frame the title as an immediate benefit or challenge (e.g. 'Boost ...', 'Stop ...', 'Do This to ...').\n"
                "- Use punchy, high-energy language.\n"
                "- Preferred emojis: 🔥 💪 ⚡ 🚀 😤 (pick 1-2 max).\n"
                "- Description should hype the viewer and drive engagement.\n"
                "- Hashtags should lean toward motivation, confidence, and viral trends."
            )

        prompt = f"""
        You are a viral YouTube Shorts expert. Create a catchy title and a high-engagement description based on the following Instagram Reel metadata:

        {context}

        {style_instructions}

        General Guidelines:
        1. The YouTube title should be short (<60 chars) and clicky.
        2. The description should summarize the video nicely (2-3 sentences).
        3. Include 3-5 relevant viral hashtags at the end of the description.
        4. The title and description MUST be noticeably different in angle and wording from a Channel 1 version of the same content.

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
            status_manager.log(f"🤖 AI Generated Title (Channel {channel_number}): {title}")
            return title, description
        except Exception as e:
            status_manager.log(f"❌ Kilo AI failed: {e}")
            return original_title, "Uploaded via InstaToYTAgent #Shorts"
