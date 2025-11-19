from typing import Optional

class Message:


    def __init__(self, msg_id: str, sender: str, to: Optional[str], text: str,
                 timestamp: str, is_group: bool = False, deleted: bool = False):
        self.id = msg_id
        self.sender = sender
        self.to = to
        self.text = text
        self.timestamp = timestamp
        self.is_group = is_group
        self.deleted = deleted

    def __repr__(self):
        return (f"Message(id='{self.id}', sender='{self.sender}', "
                f"to='{self.to}', deleted={self.deleted})")