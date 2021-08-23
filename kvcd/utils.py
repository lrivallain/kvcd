"""Some small tools that can be used in kvcd modules
"""

import yaml
import functools
import functools
import threading


def str2bool(v:str):
    """Transform a string to a boolean value.

    Args:
        v (str): String value to convert

    Returns:
        bool: True if v is 'True', False otherwise.
    """
    return bool(yaml.safe_load(v))


def lowercase_first_string_letter(v:str):
    """Transform a string to lowercase first letter.

    Args:
        v (str): String value to convert

    Returns:
        str: Lowercase first letter of v
    """
    return v[0].lower() + v[1:]


def setInterval(sec: int):
    """Time-interval based decorator

    usage: @setInterval(sec=3)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*argv, **kw):
            func(*argv, **kw)
            t = threading.Timer(sec, wrapper, argv, kw)
            t.start()
        return wrapper
    return decorator
