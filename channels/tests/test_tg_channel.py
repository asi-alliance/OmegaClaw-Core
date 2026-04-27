import os
import sys

# Mock OpenAI API key for import-time client initialization
os.environ["OPENAI_API_KEY"] = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

import unittest
from unittest.mock import MagicMock, patch, mock_open

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from channels.tg_channel import _TelegramChannel

class TestTelegramChannel(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Initialize without loading actual config files
        with patch("os.path.exists", return_value=False):
            self.channel = _TelegramChannel()

    def test_normalize_chat_id(self):
        """Test chat ID normalization logic."""
        self.assertEqual(self.channel._normalize_chat_id("12345678901"), "-12345678901")
        self.assertEqual(self.channel._normalize_chat_id("-100123"), "-100123")
        self.assertEqual(self.channel._normalize_chat_id("  12345678901  "), "-12345678901")
        self.assertIsNone(self.channel._normalize_chat_id(None))
        self.assertIsNone(self.channel._normalize_chat_id(""))

    def test_normalize_chat_ids(self):
        """Test normalization of multiple chat IDs."""
        input_ids = ["12345678901", "-100123", "  456  "]
        expected = {"-12345678901", "-100123"}
        result = self.channel._normalize_chat_ids(input_ids)
        self.assertIn("-12345678901", result)
        self.assertIn("-100123", result)
        self.assertIn("456", result)

    def test_is_allowed_chat(self):
        """Test authorization logic for chats."""
        self.channel.restrict_to_config_chat = True
        self.channel.allowed_chat_ids = {"-1001", "-1002"}
        
        self.assertTrue(self.channel._is_allowed_chat("-1001"))
        self.assertTrue(self.channel._is_allowed_chat(-1002))
        self.assertFalse(self.channel._is_allowed_chat("-1003"))
        
        self.channel.restrict_to_config_chat = False
        self.assertTrue(self.channel._is_allowed_chat("-1003"))

    @patch("builtins.open", new_callable=mock_open, read_data="telegram:\n  allowed_chats: ['-1001']\n  batching:\n    window_seconds: 5")
    @patch("os.path.exists", return_value=True)
    def test_load_config(self, mock_exists, mock_file):
        """Test loading configuration from YAML."""
        self.channel.load_config("fake_path")
        self.assertEqual(self.channel.window_seconds, 5)
        self.assertIn("-1001", self.channel.allowed_chat_ids)


    async def test_is_chat_authorized_private_admin(self):
        """Test authorization for private messages from admins."""
        mock_message = MagicMock()
        mock_message.chat.type = "private"
        mock_message.from_user.id = 123
        
        self.channel.admin_ids = [123]
        self.channel.dm_enabled = False
        
        self.assertTrue(self.channel._is_chat_authorized(mock_message))

    async def test_is_chat_authorized_private_non_admin(self):
        """Test authorization for private messages from non-admins."""
        mock_message = MagicMock()
        mock_message.chat.type = "private"
        mock_message.from_user.id = 456
        
        self.channel.admin_ids = [123]
        self.channel.dm_enabled = False
        self.assertFalse(self.channel._is_chat_authorized(mock_message))
        
        self.channel.dm_enabled = True
        self.assertTrue(self.channel._is_chat_authorized(mock_message))

if __name__ == "__main__":
    unittest.main()
