import datetime as dt
import enum
import typing as tp


class EventType(enum.Enum):
    REQUESTED = 'REQUESTED'
    REVIEWED = 'REVIEWED'
    REMOVED = 'REMOVED'
    MERGED = 'MERGED'
    CLOSED = 'CLOSED'
    NONE = 'NONE'


class Event:
    __slots__ = ('_type', 'reviewer', 'event_at')

    _type: EventType
    reviewer: tp.Optional[str]
    event_at: dt.datetime

    def __init__(self, event: tp.Dict[str, tp.Any], author: str):
        self._type = self._get_type(event['__typename'])
        if not self.is_ok:
            return

        if self.is_reviewed:
            self.reviewer = event['author']['login']
        elif self.is_removed or (
            self.is_requested
            and event['actor']['login'] == author  # only author can remove?
        ):
            reviewer = event.get('requestedReviewer')
            if not reviewer:
                self._type = EventType.NONE
                return

            self.reviewer = reviewer['login']
        else:
            self.reviewer = None

        last_at = event.get('submittedAt') or event.get('createdAt')
        if not last_at:
            self._type = EventType.NONE
            return

        self.event_at = dt.datetime.strptime(
            last_at, '%Y-%m-%dT%H:%M:%SZ',
        ).replace(tzinfo=dt.timezone.utc)

    def __repr__(self):
        return str(
            {
                'type': str(self._type),
                'reviewer': self.reviewer if self.reviewer else 'None',
                'event_at': self.event_at.isoformat(),
            },
        )

    @staticmethod
    def _get_type(event_type_str: str) -> EventType:
        if event_type_str == 'ReviewRequestedEvent':
            return EventType.REQUESTED
        if event_type_str == 'PullRequestReview':
            return EventType.REVIEWED
        if event_type_str == 'ReviewRequestRemovedEvent':
            return EventType.REMOVED
        if event_type_str == 'MergedEvent':
            return EventType.MERGED
        if event_type_str == 'ClosedEvent':
            return EventType.CLOSED
        return EventType.NONE

    @property
    def is_ok(self) -> bool:
        return self._type != EventType.NONE

    @property
    def is_requested(self) -> bool:
        return self._type == EventType.REQUESTED

    @property
    def is_reviewed(self) -> bool:
        return self._type == EventType.REVIEWED

    @property
    def is_removed(self) -> bool:
        return self._type == EventType.REMOVED

    @property
    def is_terminal(self) -> bool:
        return self._type == EventType.MERGED or self._type == EventType.CLOSED
