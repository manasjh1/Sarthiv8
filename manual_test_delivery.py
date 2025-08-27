#!/usr/bin/env python3
"""
Manual test script for DeliveryService
Run this to manually test your delivery service with actual data
"""

import asyncio
import uuid
from unittest.mock import Mock
from sqlalchemy.orm import Session

# Import your actual classes
from delivery_service.service import DeliveryService
from app.models import User, Chat, Reflection
from app.database import get_db


class DeliveryServiceTester:
    """Manual tester for DeliveryService"""

    def __init__(self):
        self.delivery_service = DeliveryService()

    def create_test_data(self):
        """Create test data for manual testing"""
        # Create test user
        user = User(
            user_id=uuid.uuid4(),
            name="Test User",
            email="testuser@example.com",
            phone_number=1234567890,
            is_anonymous=False,
            is_verified=True,
            status=1
        )

        # Create test chat
        chat = Chat(
            chat_id=uuid.uuid4(),
            user_id=user.user_id
        )
        # Mock relationship
        chat.user = user

        # Create test reflection
        reflection = Reflection(
            reflection_id=uuid.uuid4(),
            chat_id=chat.chat_id,
            summary="This is a test reflection about gratitude and appreciation for a dear friend.",
            receiver_name="Jane Doe",
            receiver_relationship="friend",
            is_anonymous=None,  # Not decided
            sender_name=None,
            delivery_mode=None,  # Not decided
            is_delivered=0,
            current_stage=19
        )
        # Mock relationship
        reflection.chat = chat

        return user, chat, reflection

    def test_relationship_flow(self):
        """Test the User ↔ Chat ↔ Reflection relationship"""
        print("🔍 Testing relationship flow...")
        
        user, chat, reflection = self.create_test_data()
        
        # Test relationship chain
        print(f"User ID: {user.user_id}")
        print(f"Chat ID: {chat.chat_id}")
        print(f"Chat belongs to User: {chat.user_id}")
        print(f"Reflection ID: {reflection.reflection_id}")
        print(f"Reflection belongs to Chat: {reflection.chat_id}")
        
        # Verify the chain
        assert chat.user_id == user.user_id, "Chat should belong to User"
        assert reflection.chat_id == chat.chat_id, "Reflection should belong to Chat"
        
        print("✅ Relationship flow is correct!")

    def test_identity_decision(self):
        """Test identity decision logic"""
        print("\n🔍 Testing identity decision logic...")
        
        _, _, reflection = self.create_test_data()
        
        # Test not decided
        reflection.is_anonymous = None
        result = self.delivery_service._is_identity_decided(reflection)
        print(f"Not decided (None): {result}")
        assert result is False, "Should be False when is_anonymous is None"
        
        # Test decided - anonymous
        reflection.is_anonymous = True
        result = self.delivery_service._is_identity_decided(reflection)
        print(f"Decided anonymous (True): {result}")
        assert result is True, "Should be True when is_anonymous is True"
        
        # Test decided - not anonymous
        reflection.is_anonymous = False
        result = self.delivery_service._is_identity_decided(reflection)
        print(f"Decided not anonymous (False): {result}")
        assert result is True, "Should be True when is_anonymous is False"
        
        print("✅ Identity decision logic works correctly!")

    def test_sender_name_logic(self):
        """Test sender name determination"""
        print("\n🔍 Testing sender name logic...")
        
        user, _, reflection = self.create_test_data()
        
        # Test anonymous
        reflection.is_anonymous = True
        reflection.sender_name = None
        name = self.delivery_service._get_sender_name(reflection, user)
        print(f"Anonymous: {name}")
        assert name == "Anonymous", "Should return 'Anonymous' when is_anonymous is True"
        
        # Test with custom sender name
        reflection.is_anonymous = False
        reflection.sender_name = "Custom Name"
        name = self.delivery_service._get_sender_name(reflection, user)
        print(f"Custom name: {name}")
        assert name == "Custom Name", "Should return custom sender name"
        
        # Test with user name
        reflection.is_anonymous = False
        reflection.sender_name = None
        user.name = "User Name"
        name = self.delivery_service._get_sender_name(reflection, user)
        print(f"User name: {name}")
        assert name == "User Name", "Should return user's name"
        
        # Test fallback
        reflection.is_anonymous = False
        reflection.sender_name = None
        user.name = None
        name = self.delivery_service._get_sender_name(reflection, user)
        print(f"Fallback: {name}")
        assert name == "Anonymous", "Should fallback to 'Anonymous'"
        
        print("✅ Sender name logic works correctly!")

    def test_email_validation(self):
        """Test email validation"""
        print("\n🔍 Testing email validation...")
        
        test_cases = [
            ("valid@example.com", True),
            ("user.name@domain.co.uk", True),
            ("invalid-email", False),
            ("@domain.com", False),
            ("user@", False),
            ("", False),
            (None, False),
        ]
        
        for email, expected in test_cases:
            result = self.delivery_service._is_valid_email(email)
            print(f"Email: {email} -> {result} (expected: {expected})")
            assert result == expected, f"Email validation failed for {email}"
        
        print("✅ Email validation works correctly!")

    async def test_identity_reveal_request(self):
        """Test identity reveal request generation"""
        print("\n🔍 Testing identity reveal request...")
        
        user, _, reflection = self.create_test_data()
        reflection.is_anonymous = None  # Not decided
        
        result = self.delivery_service._handle_identity_reveal_request(
            reflection.reflection_id, reflection, user, reflection.summary
        )
        
        print(f"Success: {result['success']}")
        print(f"Message: {result['sarthi_message']}")
        print(f"Options count: {len(result['data'][0]['options'])}")
        
        assert result['success'] is True
        assert 'anonymously' in result['sarthi_message'].lower()
        assert len(result['data'][0]['options']) == 2
        
        print("✅ Identity reveal request works correctly!")

    def test_delivery_options_display(self):
        """Test delivery options display"""
        print("\n🔍 Testing delivery options display...")
        
        _, _, reflection = self.create_test_data()
        reflection.is_anonymous = False
        reflection.sender_name = "Test User"
        
        result = self.delivery_service._show_delivery_options(
            reflection.reflection_id, reflection, reflection.summary
        )
        
        print(f"Success: {result['success']}")
        print(f"Options count: {len(result['data'][0]['delivery_options'])}")
        
        # Check all delivery modes are present
        modes = [opt['mode'] for opt in result['data'][0]['delivery_options']]
        expected_modes = [0, 1, 2, 3]  # Email, WhatsApp, Both, Private
        
        for mode in expected_modes:
            assert mode in modes, f"Delivery mode {mode} should be present"
        
        print("✅ Delivery options display works correctly!")

    async def test_mock_delivery_flow(self):
        """Test complete delivery flow with mocks"""
        print("\n🔍 Testing complete delivery flow with mocks...")
        
        # Mock database session
        mock_db = Mock(spec=Session)
        
        user, chat, reflection = self.create_test_data()
        reflection.is_anonymous = False
        reflection.sender_name = "Test User"
        reflection.delivery_mode = 3  # Private mode
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = reflection
        
        # Test private delivery directly (no context manager needed)
        result = self.delivery_service._handle_private_mode(reflection, mock_db)
        
        print(f"Private delivery success: {result['success']}")
        print(f"Delivery status: {result['data'][0]['status']}")
        print(f"Is delivered: {reflection.is_delivered}")
        
        assert result['success'] is True
        assert 'private' in result['data'][0]['status']
        assert reflection.is_delivered == 1
        
        print("✅ Mock delivery flow works correctly!")

    async def test_full_send_reflection_flow(self):
        """Test the main send_reflection method with mocking"""
        print("\n🔍 Testing full send_reflection flow...")
        
        # Create test data
        user, chat, reflection = self.create_test_data()
        reflection.summary = "Complete test reflection summary"
        reflection.is_anonymous = True  # Already decided
        reflection.delivery_mode = None  # Not decided yet
        
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = reflection
        mock_db.commit = Mock()
        
        # Mock get_user_by_chat_id using patch
        from unittest.mock import patch
        
        with patch('delivery_service.service.get_user_by_chat_id') as mock_get_user:
            mock_get_user.return_value = user
            
            # Test send_reflection - should show delivery options since identity is decided
            result = await self.delivery_service.send_reflection(reflection.reflection_id, mock_db)
            
            print(f"Send reflection success: {result['success']}")
            print(f"Current stage: {result['current_stage']}")
            print(f"Has delivery options: {'delivery_options' in result['data'][0]}")
            print(f"Number of delivery options: {len(result['data'][0]['delivery_options'])}")
            
            assert result['success'] is True
            assert result['current_stage'] == 100
            assert 'delivery_options' in result['data'][0]
            assert len(result['data'][0]['delivery_options']) == 4  # Email, WhatsApp, Both, Private
        
        print("✅ Full send_reflection flow works correctly!")

    def run_all_tests(self):
        """Run all manual tests"""
        print("🚀 Starting DeliveryService Manual Tests\n")
        
        try:
            self.test_relationship_flow()
            self.test_identity_decision()
            self.test_sender_name_logic()
            self.test_email_validation()
            
            # Async tests
            asyncio.run(self.test_identity_reveal_request())
            asyncio.run(self.test_mock_delivery_flow())
            asyncio.run(self.test_full_send_reflection_flow())
            
            self.test_delivery_options_display()
            
            print("\n🎉 All manual tests passed!")
            
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            raise


def main():
    """Main function to run manual tests"""
    tester = DeliveryServiceTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()