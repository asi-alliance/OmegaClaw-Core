import logging

logger = logging.getLogger(__name__)

_commChannelRegistry = {}

class CommChannel:
    """Communication channel implementation"""

    def config(self, config: dict) -> None:
        """Configure communication channel. Receives the subset of the command
        line parameters which are <key>=<value> pairs"""
        raise NotImplementedError()

    def receive(self) -> str:
        """Receive message from the communication channel"""
        raise NotImplementedError()

    def send(self, message: str) -> None:
        """Send message via the communication channel"""
        raise NotImplementedError()

def registerCommChannel(id: str, channel: CommChannel) -> None:
    """Register communication channel in the registry"""
    global _commChannelRegistry
    logger.info(f"registerCommChannel: registering communication channel {id}")
    _commChannelRegistry[id] = channel

_commchannel: CommChannel = None

def commChannelConfig(commchannel, config):
    """Select and configure one of the communication channels registered by
    plugins"""
    global _commchannel
    _commchannel = _commChannelRegistry.get(commchannel, None)
    if _commchannel is None:
        _error("commChannelConfig", f"Communication channel plugin {commchannel} is not registered")
    _commchannel.config(config)

def commChannelReceive():
    """Receive message from selected communication channel"""
    global _commchannel
    return _commchannel.receive()

def commChannelSend(message):
    """Send message via selected communication channel"""
    global _commchannel
    _commchannel.send(message)
