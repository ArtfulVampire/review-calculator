import datetime as dt


class Config:
    def __init__(self, is_test: bool = False):
        # main.py "crontasks" periods
        self.process_stats_delta = dt.timedelta(minutes=10)
        self.process_notify_delta = dt.timedelta(hours=1)
        self.process_gaps_delta = dt.timedelta(hours=6)
        self.process_subordinated_delta = dt.timedelta(days=1)
        self.process_logins_delta = dt.timedelta(days=1)
