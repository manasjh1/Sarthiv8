import asyncio
import json
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompt_engine import PromptEngineService

class PromptEngineConfig:
    def __init__(self):
        load_dotenv()
        self.supabase_connection_string = os.getenv('SUPABASE_CONNECTION_STRING')
        self.max_pool_connections = int(os.getenv('PROMPT_MAX_POOL_CONNECTIONS', '10'))
        self.min_pool_connections = int(os.getenv('PROMPT_MIN_POOL_CONNECTIONS', '2'))
        self.connection_timeout = int(os.getenv('PROMPT_CONNECTION_TIMEOUT', '30'))

class InteractivePromptTester:
    def __init__(self):
        self.service = None
        self.running = True
    
    async def initialize(self):
        """Initialize the prompt engine service"""
        try:
            config = PromptEngineConfig()
            self.service = PromptEngineService.from_config(config)
            await self.service.initialize()
            print("Prompt Engine Service initialized successfully!")
            return True
        except Exception as e:
            print(f"Failed to initialize service: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown the service"""
        if self.service:
            await self.service.shutdown()
            print("Service shutdown complete")
    
    def show_menu(self):
        """Display the main menu"""
        print("\n" + "=" * 60)
        print("INTERACTIVE PROMPT ENGINE TESTER")
        print("=" * 60)
        print("Options:")
        print("1. Test with custom input")
        print("2. Quick test templates")
        print("3. Show available stages (from your database)")
        print("4. Exit")
        print("-" * 60)
    
    async def test_custom_input(self):
        """Handle custom JSON input from user"""
        print("\nCustom Input Mode")
        print("-" * 30)
        print("Enter your JSON input with 'stage_id' and 'data' (both required)")
        print("Examples:")
        print('  {"stage_id": 1, "data": {}}')
        print('  {"stage_id": 2, "data": {"name": "Manas"}}')
        print("Type 'back' to return to menu")
        
        while True:
            print()
            user_input = input("JSON Input: ").strip()
            
            if user_input.lower() == 'back':
                break
            
            if not user_input:
                print("Please enter valid JSON or 'back'")
                continue
            
            await self.process_and_display(user_input)
    
    async def quick_templates(self):
        """Show quick test templates"""
        print("\nQuick Test Templates")
        print("-" * 30)
        
        templates = [
            {"name": "Stage 1 - Static Only", "json": {"stage_id": 1, "data": {}}},
            {"name": "Stage 2 - With Name", "json": {"stage_id": 2, "data": {"name": "Manas"}}},
            {"name": "Stage 3 - With Emotion", "json": {"stage_id": 3, "data": {"emotion": "happy"}}},
            {"name": "Stage 2 - Empty Data (test missing vars)", "json": {"stage_id": 2, "data": {}}},
            {"name": "Dynamic Test", "json": {"stage_id": 2, "data": {"name": "Alex", "age": 25}}},
            {"name": "Custom - Enter your own", "json": None}
        ]
        
        for i, template in enumerate(templates, 1):
            if template["json"]:
                print(f"{i}. {template['name']}: {json.dumps(template['json'])}")
            else:
                print(f"{i}. {template['name']}")
        
        print("Enter choice (1-6) or 'back':")
        
        while True:
            choice = input("Template choice: ").strip()
            
            if choice.lower() == 'back':
                break
            
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(templates):
                    template = templates[choice_num - 1]
                    
                    if template["json"] is None:
                        # Custom input
                        custom_input = input("Enter custom JSON: ").strip()
                        await self.process_and_display(custom_input)
                    else:
                        # Use template
                        json_input = json.dumps(template["json"])
                        print(f"\nUsing template: {template['name']}")
                        print(f"Input: {json_input}")
                        await self.process_and_display(json_input)
                else:
                    print(f"Please enter a number between 1 and {len(templates)}")
            except ValueError:
                print("Please enter a valid number or 'back'")
    
    async def show_available_stages(self):
        """Show available stages from the database"""
        print("\nAvailable Stages in Database")
        print("-" * 30)
        
        try:
            # Access the database manager from the service
            db_manager = self.service.db_manager
            
            if db_manager._pool:
                async with db_manager._pool.acquire() as connection:
                    stages = await connection.fetch("""
                        SELECT stage_id, prompt_name, is_static, prompt_type,
                               LEFT(prompt, 100) as prompt_preview
                        FROM prompt_table 
                        WHERE status = 1 
                        ORDER BY stage_id
                    """)
                    
                    print(f"Found {len(stages)} active stages:")
                    print()
                    
                    for stage in stages:
                        print(f"Stage {stage['stage_id']}: {stage['prompt_name']}")
                        print(f"  Type: {'User' if stage['prompt_type'] == 0 else 'System'}")
                        print(f"  Static: {stage['is_static']}")
                        print(f"  Preview: {stage['prompt_preview']}...")
                        print()
        except Exception as e:
            print(f"Error fetching stages: {e}")
        
        input("Press Enter to continue...")
    
    async def process_and_display(self, json_input):
        """Process input and display formatted results"""
        print()
        print("Processing...")
        print("-" * 30)
        
        try:
            # Validate JSON first
            input_data = json.loads(json_input)
            
            # Check required fields
            if 'stage_id' not in input_data:
                print("ERROR: Missing 'stage_id' field")
                return
            
            if 'data' not in input_data:
                print("ERROR: Missing 'data' field (can be empty: {})")
                return
            
            print(f"INPUT: {json_input}")
            
            # Process the request
            start_time = asyncio.get_event_loop().time()
            result = await self.service.process_json_request(json_input)
            end_time = asyncio.get_event_loop().time()
            
            # Parse and format result
            response_data = json.loads(result)
            
            print(f"\nOUTPUT ({(end_time - start_time)*1000:.1f}ms):")
            print(json.dumps(response_data, indent=2))
            
            # Show summary
            print(f"\nSUMMARY:")
            print(f"Stage ID: {input_data.get('stage_id')}")
            print(f"Data Keys: {list(input_data.get('data', {}).keys()) if input_data.get('data') else 'Empty'}")
            print(f"Prompt Type: {response_data.get('prompt_type')} ({'User' if response_data.get('prompt_type') == 0 else 'System'})")
            print(f"Is Static: {response_data.get('is_static')}")
            print(f"Prompt Length: {len(response_data.get('prompt', ''))}")
            
            # Show prompt preview
            prompt = response_data.get('prompt', '')
            if len(prompt) > 200:
                print(f"Prompt Preview: {prompt[:200]}...")
            else:
                print(f"Full Prompt: {prompt}")
                
        except json.JSONDecodeError as e:
            print(f"JSON ERROR: {e}")
        except Exception as e:
            print(f"PROCESSING ERROR: {e}")
    
    async def run(self):
        """Main interactive loop"""
        # Initialize service
        if not await self.initialize():
            return
        
        try:
            while self.running:
                self.show_menu()
                choice = input("Choose option (1-4): ").strip()
                
                if choice == '1':
                    await self.test_custom_input()
                elif choice == '2':
                    await self.quick_templates()
                elif choice == '3':
                    await self.show_available_stages()
                elif choice == '4':
                    print("Exiting...")
                    self.running = False
                else:
                    print("Invalid choice. Please enter 1, 2, 3, or 4.")
        
        except KeyboardInterrupt:
            print("\nExiting due to keyboard interrupt...")
        finally:
            await self.shutdown()

async def main():
    """Main function"""
    print("Starting Interactive Prompt Engine Tester...")
    
    tester = InteractivePromptTester()
    await tester.run()
    
    print("Thank you for testing!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()