import channels

class TestCommChannel(channels.CommChannel):

    started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        raise NotImplementedError()

    def receive(self) -> str:
        raise NotImplementedError()

    def send(self, message: str) -> None:
        raise NotImplementedError()


def test_commchannel_config():
    channel = TestCommChannel()
    channels.registerCommChannel("Test", channel)
    channels.commChannelStart("Test")
    assert channel.started

