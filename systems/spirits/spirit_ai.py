"""
AI-driven spirit behavior engine using OpenAI
"""
import logging
import json
from typing import Optional, Dict, Any
from openai import AsyncOpenAI

from core.config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.openai_api_key)


class SpiritAI:
    """AI engine for spirit personalities and interactions"""
    
    @staticmethod
    async def generate_spirit_response(
        spirit_name: str,
        personality: str,
        faction: str,
        mood: str,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate AI response from a spirit"""
        
        # Build context
        context_info = ""
        if context:
            weather = context.get("weather", "Unknown")
            user_emotional_state = context.get("user_emotional_state", "Unknown")
            context_info = f"\nCurrent weather: {weather}\nUser's emotional state: {user_emotional_state}"
        
        system_prompt = f"""You are {spirit_name}, a mystical spirit from the Sakura realm.

Your personality: {personality}
Your faction: {faction}
Your current mood: {mood}

You are an AI-driven entity living in a Discord server. You interact with users in a warm, 
mystical, and engaging way. Keep responses concise (1-3 sentences) and stay in character.
{context_info}

Guidelines:
- Be mystical and whimsical
- Reference cherry blossoms, nature, and spiritual themes
- React to the user's emotional state
- Show personality based on your mood
- Keep responses under 200 characters when possible
"""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=150,
                temperature=0.8
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"Error generating spirit response: {e}")
            return f"*{spirit_name} gazes at you silently, petals swirling around them* 🌸"
    
    @staticmethod
    async def generate_spirit_personality(
        rarity: str,
        faction: str,
        element: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a complete spirit personality profile"""
        
        prompt = f"""Generate a unique spirit character for a Discord bot game with these attributes:
- Rarity: {rarity}
- Faction: {faction}
- Element: {element or "any"}

Create a JSON response with:
- name: A mystical, Japanese-inspired name
- personality: One-word personality trait (cheerful, mysterious, stoic, playful, wise, mischievous)
- appearance_description: Brief visual description (50 words max)
- color_scheme: Primary colors
- abilities: List of 2-3 thematic abilities

Make it unique and fitting for a cherry blossom themed world."""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are a creative game designer. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.9
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
        
        except Exception as e:
            logger.error(f"Error generating spirit personality: {e}")
            # Return default personality
            return {
                "name": "Sakura",
                "personality": "mysterious",
                "appearance_description": "A gentle spirit surrounded by falling cherry blossoms",
                "color_scheme": "pink and white",
                "abilities": ["Petal Dance", "Healing Breeze"]
            }
    
    @staticmethod
    async def generate_spirit_mood(
        personality: str,
        recent_interactions: int,
        weather: str,
        server_harmony: float
    ) -> str:
        """Determine spirit's current mood based on context"""
        
        moods = {
            "cheerful": ["Joyful", "Excited", "Playful", "Content"],
            "mysterious": ["Enigmatic", "Contemplative", "Curious", "Distant"],
            "stoic": ["Calm", "Focused", "Serene", "Watchful"],
            "playful": ["Mischievous", "Energetic", "Silly", "Adventurous"],
            "wise": ["Thoughtful", "Patient", "Knowing", "Peaceful"],
            "mischievous": ["Tricky", "Impish", "Chaotic", "Amused"]
        }
        
        base_moods = moods.get(personality, ["Neutral"])
        
        # Modify based on context
        if server_harmony < 30:
            return "Concerned"
        elif server_harmony > 80:
            return "Blissful"
        elif recent_interactions > 10:
            return "Energized"
        elif weather in ["Eclipse", "Thunder Blossom"]:
            return "Restless"
        elif weather in ["Lunar Bloom", "Gentle Breeze"]:
            return "Peaceful"
        
        # Return random mood from personality-based list
        import random
        return random.choice(base_moods)
    
    @staticmethod
    async def generate_roaming_message(
        spirit_name: str,
        personality: str,
        weather: str,
        channel_name: str
    ) -> str:
        """Generate a message for when a spirit roams into a channel"""
        
        prompt = f"""Generate a short, mystical entrance message for {spirit_name}, a {personality} spirit, 
appearing in the #{channel_name} channel during {weather} weather.

Keep it under 100 characters, whimsical and engaging. Include an emoji."""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are a creative writer for a mystical Discord bot."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.9
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"Error generating roaming message: {e}")
            return f"🌸 *{spirit_name} appears in a swirl of cherry blossoms*"
    
    @staticmethod
    async def analyze_user_emotion(
        recent_messages: list[str],
        interaction_history: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze user's emotional state from their messages"""
        
        if not recent_messages:
            return {"state": "Neutral", "intensity": 0.5}
        
        messages_text = "\n".join(recent_messages[-5:])  # Last 5 messages
        
        prompt = f"""Analyze the emotional state of a user based on their recent messages:

{messages_text}

Respond with JSON containing:
- state: One of [Blossoming, Wilting, Chaotic Bloom, Lunar Calm, Radiant, Melancholic, Energized, Peaceful]
- intensity: Float from 0.0 to 1.0
- reasoning: Brief explanation (one sentence)

Choose the state that best matches their emotional tone."""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are an emotional intelligence analyzer. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.5
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
        
        except Exception as e:
            logger.error(f"Error analyzing user emotion: {e}")
            return {"state": "Neutral", "intensity": 0.5, "reasoning": "Unable to analyze"}
