import channels

class TestCommChannel(channels.CommChannel):

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
    channels.registerCommChannel("Test", channel)
    config = { "test_param": "test_value" }
    channels.commChannelConfig("Test", config)
    assert channel.passed_config == config

