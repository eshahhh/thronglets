from enum import Enum, auto
from collections import defaultdict
import time

class MessageChannel(Enum):
    DIRECT = auto()
    LOCATION = auto()
    GLOBAL = auto()
    GROUP = auto()
    TRADE = auto()
    GOVERNANCE = auto()

class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

class Message:
    def __init__(self, id, sender_id, recipient_id, channel, content, timestamp, location=None, metadata=None, read=False, priority=MessagePriority.NORMAL, group_id=None, expires_at=None):
        self.id = id
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.channel = channel
        self.content = content
        self.timestamp = timestamp
        self.location = location
        self.metadata = metadata or {}
        self.read = read
        self.priority = priority
        self.group_id = group_id
        self.expires_at = expires_at

    def is_expired(self, current_time=None):
        if self.expires_at is None:
            return False
        current_time = current_time or time.time()
        return current_time > self.expires_at

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
            "priority": self.priority.name if hasattr(self.priority, "name") else self.priority,
            "group_id": self.group_id,
            "expires_at": self.expires_at,
        }

class MessageBus:
    def __init__(self, max_history_per_agent=100):
        self._next_message_id = 0
        self._max_history = max_history_per_agent
        self._inboxes = defaultdict(list)
        self._location_channels = defaultdict(list)
        self._group_channels = defaultdict(list)
        self._trade_channel = []
        self._governance_channel = []
        self._global_channel = []
        self._message_history = []
        self._subscribers = defaultdict(list)
        self._channel_subscribers = defaultdict(list)
        self._group_members = defaultdict(set)
        self._agent_groups = defaultdict(set)

    def _generate_message_id(self):
        msg_id = f"msg_{self._next_message_id}"
        self._next_message_id += 1
        return msg_id

    def send_direct(self, sender_id, recipient_id, content, timestamp=None, metadata=None, priority=MessagePriority.NORMAL, expires_at=None):
        message = Message(
            id=self._generate_message_id(),
            sender_id=sender_id,
            recipient_id=recipient_id,
            channel=MessageChannel.DIRECT,
            content=content,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=metadata or {},
            priority=priority,
            expires_at=expires_at,
        )
        self._inboxes[recipient_id].append(message)
        self._trim_inbox(recipient_id)
        self._message_history.append(message)
        self._notify_subscribers(recipient_id, message)
        self._notify_channel_subscribers(MessageChannel.DIRECT, message)
        return message

    def broadcast_location(self, sender_id, location_id, content, timestamp=None, metadata=None, exclude_sender=True, priority=MessagePriority.NORMAL):
        message = Message(
            id=self._generate_message_id(),
            sender_id=sender_id,
            recipient_id=None,
            channel=MessageChannel.LOCATION,
            content=content,
            timestamp=timestamp if timestamp is not None else time.time(),
            location=location_id,
            metadata=metadata or {},
            priority=priority,
        )
        self._location_channels[location_id].append(message)
        self._message_history.append(message)
        self._notify_channel_subscribers(MessageChannel.LOCATION, message)
        return message

    def broadcast_global(self, sender_id, content, timestamp=None, metadata=None, priority=MessagePriority.NORMAL):
        message = Message(
            id=self._generate_message_id(),
            sender_id=sender_id,
            recipient_id=None,
            channel=MessageChannel.GLOBAL,
            content=content,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=metadata or {},
            priority=priority,
        )
        self._global_channel.append(message)
        self._message_history.append(message)
        self._notify_channel_subscribers(MessageChannel.GLOBAL, message)
        return message

    def broadcast_group(self, sender_id, group_id, content, timestamp=None, metadata=None, priority=MessagePriority.NORMAL, exclude_sender=True):
        message = Message(
            id=self._generate_message_id(),
            sender_id=sender_id,
            recipient_id=None,
            channel=MessageChannel.GROUP,
            content=content,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=metadata or {},
            priority=priority,
            group_id=group_id,
        )
        self._group_channels[group_id].append(message)
        self._message_history.append(message)
        
        for member_id in self._group_members.get(group_id, set()):
            if exclude_sender and member_id == sender_id:
                continue
            self._notify_subscribers(member_id, message)
        
        self._notify_channel_subscribers(MessageChannel.GROUP, message)
        return message

    def send_trade_message(self, sender_id, content, recipient_id=None, timestamp=None, metadata=None, priority=MessagePriority.HIGH):
        message = Message(
            id=self._generate_message_id(),
            sender_id=sender_id,
            recipient_id=recipient_id,
            channel=MessageChannel.TRADE,
            content=content,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=metadata or {},
            priority=priority,
        )
        self._trade_channel.append(message)
        if recipient_id:
            self._inboxes[recipient_id].append(message)
            self._trim_inbox(recipient_id)
        self._message_history.append(message)
        if recipient_id:
            self._notify_subscribers(recipient_id, message)
        self._notify_channel_subscribers(MessageChannel.TRADE, message)
        return message

    def send_governance_message(self, sender_id, content, group_id=None, timestamp=None, metadata=None, priority=MessagePriority.HIGH):
        message = Message(
            id=self._generate_message_id(),
            sender_id=sender_id,
            recipient_id=None,
            channel=MessageChannel.GOVERNANCE,
            content=content,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=metadata or {},
            priority=priority,
            group_id=group_id,
        )
        self._governance_channel.append(message)
        self._message_history.append(message)
        
        if group_id:
            for member_id in self._group_members.get(group_id, set()):
                self._notify_subscribers(member_id, message)
        
        self._notify_channel_subscribers(MessageChannel.GOVERNANCE, message)
        return message

    def register_group_member(self, group_id, agent_id):
        self._group_members[group_id].add(agent_id)
        self._agent_groups[agent_id].add(group_id)

    def unregister_group_member(self, group_id, agent_id):
        self._group_members[group_id].discard(agent_id)
        self._agent_groups[agent_id].discard(group_id)

    def get_agent_groups(self, agent_id):
        return self._agent_groups.get(agent_id, set())

    def get_inbox(self, agent_id, unread_only=False, limit=None, channel=None, priority_min=None):
        messages = list(self._inboxes.get(agent_id, []))
        
        messages = [m for m in messages if not m.is_expired()]
        
        if unread_only:
            messages = [m for m in messages if not m.read]
        if channel:
            messages = [m for m in messages if m.channel == channel]
        if priority_min:
            messages = [m for m in messages if m.priority.value >= priority_min.value]
        
        messages = sorted(messages, key=lambda m: (m.priority.value, m.timestamp), reverse=True)
        if limit:
            messages = messages[:limit]
        return messages

    def get_location_messages(self, location_id, since_timestamp=None, limit=None, priority_min=None):
        messages = list(self._location_channels.get(location_id, []))
        messages = [m for m in messages if not m.is_expired()]
        
        if since_timestamp is not None:
            messages = [m for m in messages if m.timestamp > since_timestamp]
        if priority_min:
            messages = [m for m in messages if m.priority.value >= priority_min.value]
        
        messages = sorted(messages, key=lambda m: m.timestamp, reverse=True)
        if limit:
            messages = messages[:limit]
        return messages

    def get_global_messages(self, since_timestamp=None, limit=None, priority_min=None):
        messages = list(self._global_channel)
        messages = [m for m in messages if not m.is_expired()]
        
        if since_timestamp is not None:
            messages = [m for m in messages if m.timestamp > since_timestamp]
        if priority_min:
            messages = [m for m in messages if m.priority.value >= priority_min.value]
        
        messages = sorted(messages, key=lambda m: m.timestamp, reverse=True)
        if limit:
            messages = messages[:limit]
        return messages

    def get_group_messages(self, group_id, since_timestamp=None, limit=None, priority_min=None):
        messages = list(self._group_channels.get(group_id, []))
        messages = [m for m in messages if not m.is_expired()]
        
        if since_timestamp is not None:
            messages = [m for m in messages if m.timestamp > since_timestamp]
        if priority_min:
            messages = [m for m in messages if m.priority.value >= priority_min.value]
        
        messages = sorted(messages, key=lambda m: m.timestamp, reverse=True)
        if limit:
            messages = messages[:limit]
        return messages

    def get_trade_messages(self, agent_id=None, since_timestamp=None, limit=None):
        messages = list(self._trade_channel)
        messages = [m for m in messages if not m.is_expired()]
        
        if agent_id:
            messages = [m for m in messages if m.sender_id == agent_id or m.recipient_id == agent_id]
        if since_timestamp is not None:
            messages = [m for m in messages if m.timestamp > since_timestamp]
        
        messages = sorted(messages, key=lambda m: m.timestamp, reverse=True)
        if limit:
            messages = messages[:limit]
        return messages

    def get_governance_messages(self, group_id=None, since_timestamp=None, limit=None):
        messages = list(self._governance_channel)
        messages = [m for m in messages if not m.is_expired()]
        
        if group_id:
            messages = [m for m in messages if m.group_id == group_id]
        if since_timestamp is not None:
            messages = [m for m in messages if m.timestamp > since_timestamp]
        
        messages = sorted(messages, key=lambda m: m.timestamp, reverse=True)
        if limit:
            messages = messages[:limit]
        return messages

    def get_all_messages_for_agent(self, agent_id, since_timestamp=None, limit=None):
        messages = []
        
        messages.extend(self._inboxes.get(agent_id, []))
        
        for group_id in self._agent_groups.get(agent_id, set()):
            messages.extend(self._group_channels.get(group_id, []))
        
        messages = [m for m in messages if not m.is_expired()]
        
        if since_timestamp is not None:
            messages = [m for m in messages if m.timestamp > since_timestamp]
        
        messages = sorted(messages, key=lambda m: (m.priority.value, m.timestamp), reverse=True)
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

    def subscribe_channel(self, channel, callback):
        self._channel_subscribers[channel].append(callback)

    def unsubscribe(self, agent_id, callback):
        if callback in self._subscribers[agent_id]:
            self._subscribers[agent_id].remove(callback)
            return True
        return False

    def unsubscribe_channel(self, channel, callback):
        if callback in self._channel_subscribers[channel]:
            self._channel_subscribers[channel].remove(callback)
            return True
        return False

    def _notify_subscribers(self, agent_id, message):
        for callback in list(self._subscribers.get(agent_id, [])):
            try:
                callback(message)
            except Exception:
                pass

    def _notify_channel_subscribers(self, channel, message):
        for callback in list(self._channel_subscribers.get(channel, [])):
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
        self._group_channels.clear()
        self._trade_channel.clear()
        self._governance_channel.clear()
        self._global_channel.clear()
        self._message_history.clear()
        self._next_message_id = 0

    def export_history(self):
        return [m.to_dict() for m in self._message_history]

    def get_channel_stats(self):
        return {
            "direct_messages": len([m for m in self._message_history if m.channel == MessageChannel.DIRECT]),
            "location_broadcasts": len([m for m in self._message_history if m.channel == MessageChannel.LOCATION]),
            "global_broadcasts": len(self._global_channel),
            "group_messages": sum(len(msgs) for msgs in self._group_channels.values()),
            "trade_messages": len(self._trade_channel),
            "governance_messages": len(self._governance_channel),
            "total_messages": len(self._message_history),
            "active_groups": len(self._group_channels),
            "active_locations": len(self._location_channels),
        }

    def route_message(self, sender_id, content, routing, timestamp=None, metadata=None, priority=MessagePriority.NORMAL):
        messages = []
        ts = timestamp if timestamp is not None else time.time()
        
        if routing.get("direct"):
            for recipient_id in routing["direct"]:
                msg = self.send_direct(sender_id, recipient_id, content, ts, metadata, priority)
                messages.append(msg)
        
        if routing.get("locations"):
            for location_id in routing["locations"]:
                msg = self.broadcast_location(sender_id, location_id, content, ts, metadata, priority=priority)
                messages.append(msg)
        
        if routing.get("groups"):
            for group_id in routing["groups"]:
                msg = self.broadcast_group(sender_id, group_id, content, ts, metadata, priority)
                messages.append(msg)
        
        if routing.get("global"):
            msg = self.broadcast_global(sender_id, content, ts, metadata, priority)
            messages.append(msg)
        
        if routing.get("trade"):
            recipient = routing.get("trade_recipient")
            msg = self.send_trade_message(sender_id, content, recipient, ts, metadata, priority)
            messages.append(msg)
        
        if routing.get("governance"):
            group_id = routing.get("governance_group")
            msg = self.send_governance_message(sender_id, content, group_id, ts, metadata, priority)
            messages.append(msg)
        
        return messages
