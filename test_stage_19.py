import asyncio
import uuid
from unittest.mock import Mock, AsyncMock

# Mock your MessageResponse and delivery_service
class MessageResponse:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

async def test_stage19_logic():
    """Test the stage 19 logic with different inputs"""
    
    # Mock delivery service
    delivery_service = Mock()
    delivery_service.process_identity_choice = AsyncMock(return_value={
        "success": True,
        "reflection_id": "test-id",
        "sarthi_message": "Identity processed",
        "current_stage": 100,
        "data": []
    })
    
    delivery_service.process_delivery_choice = AsyncMock(return_value={
        "success": True,
        "reflection_id": "test-id", 
        "sarthi_message": "Delivery processed",
        "current_stage": 100,
        "data": []
    })
    
    delivery_service.send_reflection = AsyncMock(return_value={
        "success": True,
        "reflection_id": "test-id",
        "sarthi_message": "Initial options",
        "current_stage": 100,
        "data": []
    })
    
    # Mock request and other vars
    reflection_id = uuid.uuid4()
    db = Mock()
    logger = Mock()
    
    # Test Case 1: Identity choice - anonymous
    print("Testing anonymous choice...")
    request = Mock()
    request.data = [{"reveal_name": False}]
    
    # Your stage 19 logic here (copy paste your if statement)
    if True:  # current_stage == 19
        logger.info(f"Processing Stage 19 for reflection {reflection_id}")
        
        try:
            if request.data and len(request.data) > 0:
                user_choice = request.data[0]
                
                if "reveal_name" in user_choice:
                    reveal_choice = user_choice.get("reveal_name")
                    provided_name = user_choice.get("name")
                    result = await delivery_service.process_identity_choice(
                        reflection_id=reflection_id,
                        reveal_choice=reveal_choice,
                        provided_name=provided_name,
                        db=db
                    )
            
            response = MessageResponse(
                success=result.get("success", True),
                reflection_id=result["reflection_id"],
                sarthi_message=result["sarthi_message"],
                current_stage=result.get("current_stage", 19),
                next_stage=result.get("next_stage", 19),
                data=result.get("data", [])
            )
            
            print(f"✅ Anonymous choice test passed: {response.sarthi_message}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    # Test Case 2: Delivery mode choice
    print("\nTesting delivery mode choice...")
    request.data = [{"delivery_mode": 0, "recipient_email": "test@example.com"}]
    
    # Run your logic again with different input
    # ... (copy your stage 19 logic)

# Run the test
if __name__ == "__main__":
    asyncio.run(test_stage19_logic())