from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pytz


@dataclass
class TZChoice:
    name: str
    abbrev: str
    utcoffset: timedelta
    dstoffset: timedelta

    def __hash__(self) -> int:
        return hash(self.utcoffset_str())

    def __eq__(self, other) -> bool:
        return self.utcoffset_str() == other.utcoffset_str()

    def __lt__(self, other) -> bool:
        return int(self.utcoffset_str()) < int(other.utcoffset_str())

    def __repr__(self) -> str:
        return f"TZ<{self.choice_str}>"

    def now(self) -> datetime:
        tzone = pytz.timezone(self.name)
        now = datetime.now(tzone)
        return now

    def utcoffset_str(self, dt: Optional[datetime] = None) -> str:
        if dt is None:
            dt = self.now()
        return f"{dt:%z}"

    @property
    def offsets(self) -> tuple[timedelta, ...]:
        return (self.utcoffset, self.dstoffset)

    @property
    def choice_str(self):
        now = self.now()
        return (
            f"{self.abbrev} ({now:%H:%M}, UTC{self.utcoffset_str(now)}"
            f"{', DST' if self.is_dst() else ''})"
        )

    def is_dst(self) -> bool:
        return self.dstoffset.total_seconds() != 0


def abbrevs_pytz() -> dict[str, set[TZChoice]]:
    choices = defaultdict(set)

    for name in pytz.all_timezones:
        tzone = pytz.timezone(name)
        for utcoffset, dstoffset, tzabbrev in getattr(
            tzone,
            "_transition_info",
            [
                [
                    None,
                    None,
                    datetime.now(tzone).tzname(),
                ]
            ],
        ):
            if tzabbrev == "LMT":
                continue
            if utcoffset is None:
                continue
            choices[tzabbrev].add(TZChoice(name, tzabbrev, utcoffset, dstoffset))

    choices["UTC"].add(TZChoice("UTC", "UTC", timedelta(0), timedelta(0)))

    return choices


if __name__ == "__main__":
    from pprint import pprint

    choices = abbrevs_pytz()
    pprint(choices)
