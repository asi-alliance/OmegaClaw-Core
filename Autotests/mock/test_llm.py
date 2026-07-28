import pytest

from llm import *
from rpc import LOCALHOST

TEST_ADDRESS = (LOCALHOST, 9767)

class TestLlmMock:

    def setup_class(cls):
        import logging
        import threading

        def thread_id_filter(record):
            record.thread_id = threading.get_native_id()
            return record

        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[%(levelname)s] [%(thread_id)d]: %(message)s'))
        handler.addFilter(thread_id_filter)
        logging.getLogger().handlers.clear()
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)

    @pytest.fixture
    def agent(self):
        agent = LlmMockAgent(TEST_ADDRESS)
        yield agent
        agent.stop(5)

    @pytest.fixture
    def controller(self):
        controller = LlmMockController(TEST_ADDRESS)
        yield controller
        controller.stop(5)

    def test_response(self, agent, controller):
        assert controller.set_answer("hello", "world")
        assert agent.chat(":-:-:-:['HUMAN-MSG', 'test: hello']") == "world"

    def test_test_restart(self, agent):
        controller = LlmMockController(TEST_ADDRESS)
        assert controller.set_answer("hello", "world")
        assert agent.chat(":-:-:-:['HUMAN-MSG', 'test: hello']") == "world"
        controller.stop(5)
        controller = LlmMockController(TEST_ADDRESS)
        assert controller.set_answer("hello", "earth")
        assert agent.chat(":-:-:-:['HUMAN-MSG', 'test: hello']") == "earth"
        controller.stop(5)

    def test_no_message(self, agent, controller):
        assert controller.set_answer("hello", "world")
        assert agent.chat(":-:-:-:DO NOT RE-SEND OR SPAM!") == ""

    def test_context_manager(self, agent):
        with llm_mock_controller(address=TEST_ADDRESS) as controller:
            assert controller.set_answer("hello", "world")
            assert agent.chat(":-:-:-:['HUMAN-MSG', 'test: hello']") == "world"

    def test_context_manager_timeout(self, agent):
        address = (TEST_ADDRESS[0], TEST_ADDRESS[1] + 1)
        try:
            with llm_mock_controller(address=address, timeout=2) as controller:
                assert False
        except RuntimeError as e:
            assert e.args == ("Agent didn't answered in 2 seconds",)
