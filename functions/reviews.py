from log.log import bot_log
from functions import open_files, save_files
from log.log import bot_log


def add_review(review: str) -> str:
    reviews = open_files.reviews
    reviews.append(review)
    save_files.save_reviews(reviews)
    msg = "Відгук успішно додано"
    bot_log(msg)
    return msg


def find_repeated_chars(reviews: list) -> str:
    reviews = " ".join(reviews)

    repeated_groups = set()
    for i in range(len(reviews)):
        for j in range(i+1, len(reviews)):
            slice = reviews[i:j]
            if reviews.count(slice) >= 2:
                repeated_groups.add(slice)

    msg = f"Список груп символів, які повторюються не менше 2 разів:\n{repeated_groups}"
    bot_log(msg)
    return msg
