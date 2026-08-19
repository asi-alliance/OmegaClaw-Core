import logging

logger = logging.getLogger(__name__)

_commChannelRegistry = {}

def is_control_command(text: str) -> bool:
    from memory_export import is_export_command
    return is_export_command(text)

def handle_control_message(text: str, owner_key: str, deliver_reply) -> bool:
    from memory_export import handle_export_command

    if not is_control_command(text):
        return False
    reply = handle_export_command(text, owner_key, deliver_reply)
    if reply is not None:
        deliver_reply(reply)
    return True

class CommChannel:
    """Communication channel implementation"""

    def start(self) -> None:
        """Configure and start communication channel"""
        raise NotImplementedError()

    def stop(self) -> None:
        """Stop communication channel and free resources"""
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

def commChannelStart(commchannel):
    """Select and start one of the communication channels registered by
    plugins"""
    global _commchannel
    _commchannel = _commChannelRegistry.get(commchannel, None)
    if _commchannel is None:
        _error("commChannelStart", f"Communication channel plugin {commchannel} is not registered")
    _commchannel.start()

def commChannelReceive():
    """Receive message from selected communication channel"""
    global _commchannel
    return _commchannel.receive()

def commChannelSend(message):
    """Send message via selected communication channel"""
    global _commchannel
    _commchannel.send(message)
