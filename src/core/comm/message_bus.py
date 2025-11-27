from enum import Enum, auto
from collections import defaultdict
import time

class MessageChannel(Enum):
    DIRECT = auto()
    LOCATION = auto()
    GLOBAL = auto()

class Message:
    def __init__(self, id, sender_id, recipient_id, channel, content, timestamp, location=None, metadata=None, read=False):
        self.id = id
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.channel = channel
        self.content = content
        self.timestamp = timestamp
        self.location = location
        self.metadata = metadata or {}
        self.read = read

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "channel": self.channel.name if hasattr(self.channel, "name") else self.channel,
            "content": self.content,
            "timestamp": self.timestamp,
            "location": self.location,
            "metadata": self.metadata,
            "read": self.read,
        }

class MessageBus:
    def __init__(self, max_history_per_agent=100):
        self._next_message_id = 0
        self._max_history = max_history_per_agent
        self._inboxes = defaultdict(list)
        self._location_channels = defaultdict(list)
        self._global_channel = []
        self._message_history = []
        self._subscribers = defaultdict(list)

    def _generate_message_id(self):
        msg_id = f"msg_{self._next_message_id}"
        self._next_message_id += 1
        return msg_id

    def send_direct(self, sender_id, recipient_id, content, timestamp=None, metadata=None):
        message = Message(
            id=self._generate_message_id(),
            sender_id=sender_id,
            recipient_id=recipient_id,
            channel=MessageChannel.DIRECT,
            content=content,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=metadata or {},
        )
        self._inboxes[recipient_id].append(message)
        self._trim_inbox(recipient_id)
        self._message_history.append(message)
        self._notify_subscribers(recipient_id, message)
        return message

    def broadcast_location(self, sender_id, location_id, content, timestamp=None, metadata=None, exclude_sender=True):
        message = Message(
            id=self._generate_message_id(),
            sender_id=sender_id,
            recipient_id=None,
            channel=MessageChannel.LOCATION,
            content=content,
            timestamp=timestamp if timestamp is not None else time.time(),
            location=location_id,
            metadata=metadata or {},
        )
        self._location_channels[location_id].append(message)
        self._message_history.append(message)
        return message

    def broadcast_global(self, sender_id, content, timestamp=None, metadata=None):
        message = Message(
            id=self._generate_message_id(),
            sender_id=sender_id,
            recipient_id=None,
            channel=MessageChannel.GLOBAL,
            content=content,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=metadata or {},
        )
        self._global_channel.append(message)
        self._message_history.append(message)
        return message

    def get_inbox(self, agent_id, unread_only=False, limit=None):
        messages = list(self._inboxes.get(agent_id, []))
        if unread_only:
            messages = [m for m in messages if not m.read]
        messages = sorted(messages, key=lambda m: m.timestamp, reverse=True)
        if limit:
            messages = messages[:limit]
        return messages

    def get_location_messages(self, location_id, since_timestamp=None, limit=None):
        messages = list(self._location_channels.get(location_id, []))
        if since_timestamp is not None:
            messages = [m for m in messages if m.timestamp > since_timestamp]
        messages = sorted(messages, key=lambda m: m.timestamp, reverse=True)
        if limit:
            messages = messages[:limit]
        return messages

    def get_global_messages(self, since_timestamp=None, limit=None):
        messages = list(self._global_channel)
        if since_timestamp is not None:
            messages = [m for m in messages if m.timestamp > since_timestamp]
        messages = sorted(messages, key=lambda m: m.timestamp, reverse=True)
        if limit:
            messages = messages[:limit]
        return messages

    def mark_read(self, agent_id, message_ids=None):
        count = 0
        for msg in self._inboxes.get(agent_id, []):
            if message_ids is None or msg.id in message_ids:
                if not msg.read:
                    msg.read = True
                    count += 1
        return count

    def get_conversation(self, agent1_id, agent2_id, limit=None):
        messages = [
            m for m in self._message_history
            if m.channel == MessageChannel.DIRECT
            and ((m.sender_id == agent1_id and m.recipient_id == agent2_id)
                 or (m.sender_id == agent2_id and m.recipient_id == agent1_id))
        ]
        messages = sorted(messages, key=lambda m: m.timestamp)
        if limit:
            messages = messages[-limit:]
        return messages

    def subscribe(self, agent_id, callback):
        self._subscribers[agent_id].append(callback)

    def unsubscribe(self, agent_id, callback):
        if callback in self._subscribers[agent_id]:
            self._subscribers[agent_id].remove(callback)
            return True
        return False

    def _notify_subscribers(self, agent_id, message):
        for callback in list(self._subscribers.get(agent_id, [])):
            try:
                callback(message)
            except Exception:
                pass

    def _trim_inbox(self, agent_id):
        inbox = self._inboxes[agent_id]
        if len(inbox) > self._max_history:
            inbox.sort(key=lambda m: m.timestamp)
            self._inboxes[agent_id] = inbox[-self._max_history:]

    def get_message_count(self):
        return len(self._message_history)

    def get_messages_by_sender(self, sender_id):
        return [m for m in self._message_history if m.sender_id == sender_id]

    def get_messages_by_channel(self, channel):
        return [m for m in self._message_history if m.channel == channel]

    def get_communication_partners(self, agent_id):
        partners = defaultdict(int)
        for msg in self._message_history:
            if msg.channel == MessageChannel.DIRECT:
                if msg.sender_id == agent_id and msg.recipient_id:
                    partners[msg.recipient_id] += 1
                elif msg.recipient_id == agent_id:
                    partners[msg.sender_id] += 1
        return dict(partners)

    def get_message_history(self, start_time=None, end_time=None, channel=None):
        messages = list(self._message_history)
        if start_time is not None:
            messages = [m for m in messages if m.timestamp >= start_time]
        if end_time is not None:
            messages = [m for m in messages if m.timestamp <= end_time]
        if channel is not None:
            messages = [m for m in messages if m.channel == channel]
        return messages

    def clear_history(self):
        self._inboxes.clear()
        self._location_channels.clear()
        self._global_channel.clear()
        self._message_history.clear()
        self._next_message_id = 0

    def export_history(self):
        return [m.to_dict() for m in self._message_history]
