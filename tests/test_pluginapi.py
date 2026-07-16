import pluginapi
import plugin

class TestCommChannel(pluginapi.CommChannel):

    passed_config = None

    def config(self, config: dict) -> None:
        self.passed_config = config
        assert self.passed_config["test_param"] == "test_value"

    def receive(self) -> str:
        """Receive message from the communication channel"""
        raise NotImplementedError()

    def send(self, message: str) -> None:
        """Send message via the communication channel"""
        raise NotImplementedError()


def test_commchannel_config():
    channel = TestCommChannel()
    pluginapi.registerCommChannel("Test", channel)
    config = { "test_param": "test_value" }
    plugin.commChannelConfig("Test", config)
    assert channel.passed_config == config

