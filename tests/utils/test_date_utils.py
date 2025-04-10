import datetime

import pytest
from pytz import timezone

from tbainvestetl.utils import date_utils

tz = timezone("US/Pacific")


@pytest.mark.parametrize(
    "datetime_run,date_exp",
    [
        (
            datetime.datetime(2022, 10, 26, 18, 0, 0, tzinfo=tz),
            datetime.datetime(2022, 10, 26),
        ),
        (
            datetime.datetime(2022, 10, 26, 10, 0, 0, tzinfo=tz),
            datetime.datetime(2022, 10, 25),
        ),
        (
            datetime.datetime(2022, 10, 22, 22, 0, 0, tzinfo=tz),
            datetime.datetime(2022, 10, 21),
        ),
        (datetime.datetime(2023, 1, 2, tzinfo=tz), datetime.datetime(2022, 12, 30)),
        (datetime.date(2023, 1, 1), datetime.datetime(2022, 12, 30)),
        (datetime.date(2023, 1, 2), datetime.datetime(2023, 1, 2)),
    ],
)
def test_get_last_business_date(datetime_run, date_exp):
    date_act = date_utils.get_last_business_date(asof=datetime_run)
    assert date_exp.date() == date_act
