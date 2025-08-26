import asyncio
import json
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path to allow for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from llm_system import LLMClient
from config import AppConfig

class TestLLMSystem:
    """
    A dedicated test suite for the llm_system package.
    """
    def __init__(self):
        self.llm_service = None

    async def initialize(self):
        """
        Initializes the LLMClient using the central AppConfig.
        """
        try:
            load_dotenv()
            # Load the central application configuration
            app_config = AppConfig.from_env()
            
            # Initialize the LLMClient with its specific configuration
            self.llm_service = LLMClient(config=app_config.llm)
            
            print("✅ LLM System initialized successfully!")
            print(f"   - Provider: {app_config.llm.provider}")
            print(f"   - Model: {app_config.llm.model}")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize LLM System: {e}")
            return False

    async def run_automated_test(self):
        """
        Runs a predefined test case to verify the LLMClient's functionality.
        """
        print("\n" + "="*60)
        print("RUNNING AUTOMATED LLM SYSTEM TEST")
        print("="*60)
        
        # 1. Define the input for the LLM service
        test_input = {
            "reflection_id": "test_abc_123",
            "prompt": "The user is at the beginning of the conversation.",
            "user_message": "I want to stop this right now."
        }
        
        print(f"📤 Sending Input:\n{json.dumps(test_input, indent=2)}")

        try:
            # 2. Call the LLM service
            result_json = await self.llm_service.process_json_request(json.dumps(test_input))
            
            # 3. Parse and display the result
            result = json.loads(result_json)
            
            print(f"\n📥 Received Output:\n{json.dumps(result, indent=2)}")
            
            # 4. Validate the output structure
            if "system_response" in result and "user_response" in result:
                print("\n✅ PASSED: Output contains the required 'system_response' and 'user_response' keys.")
            else:
                print("\n❌ FAILED: The output format is incorrect.")

        except Exception as e:
            print(f"\n❌ ERROR: An exception occurred during the test: {e}")

    async def run_interactive_test(self):
        """
        Allows for real-time, interactive testing of the LLMClient.
        """
        print("\n" + "="*60)
        print("INTERACTIVE LLM SYSTEM TEST")
        print("="*60)
        print("Enter a message to send to the LLM. Type 'quit' to exit.")

        while True:
            print("\n" + "-"*40)
            user_message = input("Enter user message: ").strip()

            if user_message.lower() == 'quit':
                break

            if not user_message:
                print("Please enter a message.")
                continue

            # Create the JSON input for the LLM service
            request_data = {
                "reflection_id": f"interactive_{os.urandom(4).hex()}",
                "prompt": "This is an interactive test prompt.",
                "user_message": user_message
            }
            
            print(f"\n📡 Processing...")
            try:
                result_json = await self.llm_service.process_json_request(json.dumps(request_data))
                result = json.loads(result_json)
                print(f"\n📋 LLM Response:\n{json.dumps(result, indent=2)}")
            except Exception as e:
                print(f"❌ Error: {e}")

    async def shutdown(self):
        """Shuts down the LLM service."""
        if self.llm_service:
            await self.llm_service.shutdown()
        print("\n🔄 LLM System shutdown complete.")


async def main():
    """Main function to run the test suite."""
    print("🚀 Starting LLM System Test Suite")
    tester = TestLLMSystem()

    if not await tester.initialize():
        return

    try:
        # Run the automated test first
        await tester.run_automated_test()

        # Ask the user if they want to run interactive tests
        choice = input("\nRun interactive tests? (y/n): ").lower()
        if choice == 'y':
            await tester.run_interactive_test()

    except KeyboardInterrupt:
        print("\nExiting due to user interrupt...")
    finally:
        await tester.shutdown()

    print("✅ LLM System test suite finished!")


if __name__ == "__main__":
    asyncio.run(main())