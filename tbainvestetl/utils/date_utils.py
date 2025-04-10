import datetime

from pandas.tseries.offsets import BDay
from pytz import timezone


def get_last_business_date(asof):
    """Returns last business date that has closed in NY

    Parameters
    ----------
    asof: datetime.datetime or datetime.date

    Returns
    -------
    datetime.date
        Last business date that has closed in NY.
        If self.today is a weekend or holiday, it returns the last business date.
        If self.today is a business date, then it returns the same date if it is past
        4 pm ET, otherwise the last business date.
    """

    if asof:
        # get datetime.date object
        if isinstance(asof, datetime.date) and not isinstance(asof, datetime.datetime):
            asof_date = asof
        else:
            asof_date = asof.date()

        # Check whether it is a business day
        is_business_day = (asof_date - BDay(1) + BDay(1)).date() == asof_date

        # Check whether stock market is closed in USA
        if isinstance(asof, datetime.datetime):
            time_eastern = asof.astimezone(timezone("US/Eastern"))
            is_after_4_pm = time_eastern.hour >= 16
        else:
            is_after_4_pm = True

        # If weekday and after 4 pm ET
        if is_business_day and is_after_4_pm:
            return asof_date

        # If weekend, holiday or before 4 pm then return last business day
        return (asof_date - BDay(1)).date()
    return None


def get_last_quarter_date(asof):
    if asof:
        if asof.month < 4:
            return datetime.date(asof.year - 1, 12, 31)
        if asof.month < 7:
            return datetime.date(asof.year, 3, 31)
        if asof.month < 10:
            return datetime.date(asof.year, 6, 30)
        return datetime.date(asof.year, 9, 30)
    return None
