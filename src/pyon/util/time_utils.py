#!/usr/bin/env python

""" Utilities for dealing with various date/time formats and NTP time stamps """

__author__ = 'Michael Meisinger'

import datetime
import numbers
import time


class TimeUtils(object):

    # Difference in seconds between 1900-01-01 and 1970-01-01
    NTP_JAN_1970 = 2208988800

    @classmethod
    def make_datetime(self, date=None):
        """ Return a naive UTC datetime from various formats """
        if date is None:
            date = time.time()

        dt = None
        if isinstance(date, numbers.Number):
            dt = datetime.datetime.utcfromtimestamp(date)
        elif isinstance(date, datetime.datetime):
            dt = date
        elif isinstance(date, datetime.date):
            dt = datetime.datetime.combine(date, datetime.time())
        return dt

    def make_ntp_seconds(self, ts):
        return ts + self.NTP_JAN_1970
