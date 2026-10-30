"""Transport-independent actor values; construction alone grants no authority."""
from dataclasses import dataclass


@dataclass(frozen=True)
class UserActor:
    user_id: int
    subject: str

    def __post_init__(self):
        if isinstance(self.user_id, bool) or not isinstance(self.user_id, int):
            raise TypeError('user_id must be an integer')
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError('subject must be a nonempty string')
