"""
String helpers
"""

import random
import string


def get_random_string(length) -> str:
    """
    Get a random string of ascii chargs
    """
    return ''.join(
        random.choice(string.ascii_lowercase) for _ in range(length))


def sanitize_account_name(account: str) -> str:
    """
    Turn an account name into something easier to use with smm
    - lowercase
    - no spaces
    - no slashes
    """
    return account.lower().replace(' ', '.').replace('/', '.')
