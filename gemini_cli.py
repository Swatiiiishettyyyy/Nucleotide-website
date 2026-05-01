#!/usr/bin/env python3
"""
Gemini CLI - Simple command-line interface for Google Gemini API
"""

import sys
import os
import google.generativeai as genai
from typing import Optional


def load_api_key() -> Optional[str]:
    """Load API key from environment variable."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set")
        print("Set it with: $env:GOOGLE_API_KEY='your-api-key'")
        return None
    return api_key


def chat_mode():
    """Interactive chat mode."""
    model = genai.GenerativeModel('gemini-pro')
    conversation = model.start_chat()
    
    print("Gemini Chat Mode (type 'exit' to quit)")
    print("=" * 50)
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ('exit', 'quit'):
                print("Goodbye!")
                break
            if not user_input:
                continue
            
            response = conversation.send_message(user_input)
            print(f"\nGemini: {response.text}")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


def single_prompt_mode(prompt: str):
    """Single prompt mode - get one response and exit."""
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)
    print(response.text)


def main():
    """Main entry point."""
    api_key = load_api_key()
    if not api_key:
        sys.exit(1)
    
    genai.configure(api_key=api_key)
    
    if len(sys.argv) > 1:
        # Single prompt mode
        prompt = " ".join(sys.argv[1:])
        single_prompt_mode(prompt)
    else:
        # Interactive chat mode
        chat_mode()


if __name__ == "__main__":
    main()
