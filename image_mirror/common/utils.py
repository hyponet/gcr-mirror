import uuid
import time
from datetime import datetime


def gen_uuid():
    return str(uuid.uuid4())


def get_time():
    return int(time.time())


def timestamp2datetime(timestamp, need_str=True):
    dt = datetime.fromtimestamp(timestamp)
    if need_str:
        return "{}".format(dt.strftime("%Y-%m-%d %H:%M:%S"))
    return dt
