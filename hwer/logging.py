import logging
import os
logging.basicConfig(
    format='[PID: %(process)d] [%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
    level=os.environ.get("LOGLEVEL", "INFO"),
    datefmt='%Y-%m-%d %H:%M:%S')


def getLogger(name, level=None):
    level = os.environ.get("LOGLEVEL", "INFO") if level is None else level
    log = logging.getLogger(name)
    log.setLevel(level)
    return log

