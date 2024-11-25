"""
String helpers
"""

import random
import string


def get_random_string(length) -> str:
    """
    Get a random string of ascii chargs
    """
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))
