"""
Brain: LLM interface for natural language processing and response generation.
Handles conversation streaming with proper error recovery and logging.
"""

import time
from openai import OpenAI, RateLimitError, APIConnectionError
import os
from dotenv import load_dotenv
from conversation import get_conversation_history, add_ai_message
from user_manager import get_current_user_name

# Setup logging
try:
    from logger import logger, log_ai_response, log_error
except ImportError:
    import logging
    logger = logging.getLogger("Brain")
    def log_ai_response(x): pass
    def log_error(x, y): pass

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logger.info("Brain Module initialized - GPT-4o-mini")

# Error recovery settings
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # Exponential backoff multiplier


def think_stream():
    """
    Generate AI response with streaming for faster feedback.
    Includes proper error handling and retry logic.
    """
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"🧠 LLM Call (attempt {attempt+1}/{MAX_RETRIES})")
            messages = get_conversation_history()
            logger.debug(f"📝 Conversation history: {len(messages)} messages")
            
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                top_p=0.9,
                max_tokens=250,
                stream=True,
                timeout=30.0,
            )

            logger.info("✅ Stream opened")
            full_reply = ""

            for chunk in stream:
                delta = chunk.choices[0].delta

                if hasattr(delta, "content") and delta.content:
                    text = delta.content
                    full_reply += text
                    yield text

            logger.info(f"✅ Response complete: {len(full_reply)} chars")
            add_ai_message(full_reply)
            log_ai_response(full_reply)
            return

        except RateLimitError as e:
            wait_time = 2 ** attempt
            logger.warning(f"⏱️ Rate limit hit - waiting {wait_time}s before retry")
            time.sleep(wait_time)

        except APIConnectionError as e:
            logger.error(f"❌ API connection error (attempt {attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt
                logger.info(f"🔄 Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                log_error("LLM", str(e))
                yield f"Sorry, I'm having trouble connecting. Please try again."
                return

        except Exception as e:
            logger.error(f"💥 Unexpected error: {e}", exc_info=True)
            log_error("LLM", str(e))
            yield f"I encountered an error. Please try again."
            return

def think(user_input: str) -> str:
    """
    Non-streaming version for use cases that need full response upfront.
    Falls back to streaming internally and collects full response.
    """
    full_response = ""
    for chunk in think_stream():
        full_response += chunk
    return full_response
