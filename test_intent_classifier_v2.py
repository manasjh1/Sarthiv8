import asyncio
import json
import sys
import os
from dotenv import load_dotenv

# Add the parent directory to sys.path so we can import necessary modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompt_engine import PromptEngineService
from global_intent_classifier import GlobalIntentClassifierService
from global_intent_classifier.llm_service_client import MockLLMService
from config import GlobalIntentClassifierConfig, PromptEngineConfig

class TestGlobalIntentClassifierV2:
    def __init__(self):
        self.prompt_service = None
        self.intent_service = None
        self.llm_service = None

    async def initialize(self):
        """Initialize all required services"""
        try:
            load_dotenv()

            # 1. Initialize Prompt Engine Service
            prompt_config = PromptEngineConfig.from_env()
            self.prompt_service = PromptEngineService.from_config(prompt_config)
            await self.prompt_service.initialize()

            # 2. Initialize Mock LLM Service
            self.llm_service = MockLLMService()
            await self.llm_service.initialize()

            # 3. Load Global Intent Classifier Config
            gic_config = GlobalIntentClassifierConfig.from_env()

            # 4. Initialize Global Intent Classifier Service
            self.intent_service = GlobalIntentClassifierService(
                prompt_engine_service=self.prompt_service,
                llm_service=self.llm_service,
                config=gic_config
            )

            print("✅ All services initialized successfully!")
            print("   - Prompt Engine Service: Ready")
            print("   - Mock LLM Service: Ready")
            print("   - Global Intent Classifier: Ready")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize services: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def shutdown(self):
        """Shutdown all services gracefully"""
        if self.intent_service:
            await self.intent_service.shutdown()
        if self.llm_service:
            await self.llm_service.shutdown()
        if self.prompt_service:
            await self.prompt_service.shutdown()
        print("\n🔄 All services shutdown complete")

    async def run_automated_tests(self):
        """Run a series of automated tests for different input scenarios"""
        test_cases = [
            {
                "description": "Direct message: Stop conversation",
                "input": {"reflection_id": "user_123", "message": "Can you please end this chat?"},
                "expected_intent": "INTENT_STOP"
            },
            {
                "description": "Direct message: Restart conversation",
                "input": {"reflection_id": "user_123", "message": "Let's start over from the beginning."},
                "expected_intent": "INTENT_RESTART"
            },
            {
                "description": "Direct message: User is confused",
                "input": {"reflection_id": "user_456", "message": "I'm not sure what to do next, can you help?"},
                "expected_intent": "INTENT_CONFUSED"
            },
            {
                "description": "Direct message: No specific intent",
                "input": {"reflection_id": "user_789", "message": "Tell me a fun fact about the ocean."},
                "expected_intent": "NO_OVERRIDE"
            },
            {
                "description": "Fallback: Use reflection_id to fetch message (stop)",
                "input": {"reflection_id": "test_001", "message": ""},
                "expected_intent": "INTENT_STOP"
            },
            {
                "description": "Fallback: Use reflection_id to fetch message (restart)",
                "input": {"reflection_id": "test_002", "message": ""},
                "expected_intent": "INTENT_RESTART"
            }
        ]

        print("\n" + "="*60)
        print("RUNNING AUTOMATED INTENT CLASSIFIER TESTS")
        print("="*60)

        for i, test in enumerate(test_cases, 1):
            print(f"\n🧪 Test Case {i}: {test['description']}")
            print(f"🎯 Expected Intent: {test['expected_intent']}")
            print("-" * 40)

            json_input = json.dumps(test["input"])
            print(f"📤 Input: {json_input}")

            try:
                result_json = await self.intent_service.process_json_request(json_input)
                result = json.loads(result_json)
                print(f"📥 Output: {result_json}")

                if result['intent'] == test['expected_intent']:
                    print("✅ PASSED")
                else:
                    print(f"❌ FAILED - Expected '{test['expected_intent']}', but got '{result['intent']}'")
            except Exception as e:
                print(f"❌ ERROR: An exception occurred during the test: {e}")

    async def run_interactive_test(self):
        """Allow for interactive testing from the command line"""
        print("\n" + "="*60)
        print("INTERACTIVE INTENT CLASSIFIER TEST")
        print("="*60)
        print("Enter a message to classify. Type 'quit' to exit.")

        while True:
            print("\n" + "-"*40)
            user_message = input("Enter message: ").strip()

            if user_message.lower() == 'quit':
                break

            if not user_message:
                print("Please enter a message.")
                continue

            # Create the JSON input using the new MessageRequest format
            request_data = {
                "reflection_id": f"interactive_{os.urandom(4).hex()}",
                "message": user_message
            }
            json_input = json.dumps(request_data)

            print(f"\n📡 Processing...")
            print(f"📤 Input: {json_input}")

            try:
                result_json = await self.intent_service.process_json_request(json_input)
                result = json.loads(result_json)
                print(f"\n📋 Result:")
                print(json.dumps(result, indent=2))
            except Exception as e:
                print(f"❌ Error: {e}")


async def main():
    """Main function to run the test suite"""
    print("🚀 Starting Global Intent Classifier Test Suite (V2)")
    tester = TestGlobalIntentClassifierV2()

    if not await tester.initialize():
        return

    try:
        # Run automated tests first
        await tester.run_automated_tests()

        # Ask user if they want to run interactive tests
        choice = input("\nRun interactive tests? (y/n): ").lower()
        if choice == 'y':
            await tester.run_interactive_test()

    except KeyboardInterrupt:
        print("\nExiting due to user interrupt...")
    finally:
        await tester.shutdown()

    print("✅ Test suite finished!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ An unexpected application error occurred: {e}")