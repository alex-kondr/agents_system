import string
import random


def is_verify_password(password: str) -> bool:
    pass_len = False if len(password) < 8 else True
    pass_digit = False
    pass_char = False

    for char in password:
        if char.isdigit():
            pass_digit = True
        if char.isalpha():
            pass_char = True

    return True if all([pass_len, pass_digit, pass_char]) else False


def generate_password(
    len_password: int = 8,
    is_punctuation: bool = False,
    is_upper: bool = False,
    is_repeate : bool = True
) -> str:

    pass_chars = string.ascii_lowercase + string.digits
    pass_chars += string.ascii_uppercase if is_upper else ""
    pass_chars += string.punctuation if is_punctuation else ""
    password = random.choices(pass_chars, k=len_password) if is_repeate else random.sample(pass_chars, k=len_password)
    return "".join(password)