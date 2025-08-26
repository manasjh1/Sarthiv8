import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from distress_detection import get_detector
from config import AppConfig

async def interactive_distress_test():
    """
    An interactive test script for the distress_detection package.
    """
    print("🚀 Starting Interactive Distress Detection Test...")
    load_dotenv()
    
    try:
        # Initialize the detector using your central configuration
        app_config = AppConfig.from_env()
        distress_detector = await get_detector(app_config.distress, app_config.llm.api_key)
        print("✅ Distress Detector initialized successfully.")
        print("   Enter a message to check its distress level.")
        print("   Type 'quit' to exit.")
    except Exception as e:
        print(f"❌ Failed to initialize services: {e}")
        return

    # This loop will continuously ask for your input
    while True:
        print("\n" + "-"*40)
        # 1. User gives input
        message = input("Enter message: ").strip()

        if message.lower() == 'quit':
            break

        if not message:
            continue

        # 2. The distress detector checks the input
        distress_level = await distress_detector.check(message)

        # 3. The response is printed
        if distress_level == 1:
            print(f"🚨 Result: CRITICAL (Level 1)")
        elif distress_level == 2:
            print(f"⚠️  Result: WARNING (Level 2)")
        else:
            print(f"✅ Result: SAFE (Level 0)")

    print("\n👋 Exiting test.")

if __name__ == "__main__":
    asyncio.run(interactive_distress_test())