import json

from files import list_files


def save_products(products: list) -> None:
    with open(list_files.products, "w", encoding="utf-8") as fh:
        json.dump(products, fh, indent=4)


def save_reviews(reviews: list) -> None:
    with open(list_files.reviews, "w", encoding="utf-8") as fh:
        json.dump(reviews, fh, indent=4)


def save_products_sold(products_sold: list) -> None:
    with open(list_files.products_sold, "w", encoding="utf-8") as fh:
        json.dump(products_sold, fh, indent=4)


def save_employees(employees: dict) -> None:
    with open(list_files.employees, "w", encoding="utf-8") as fh:
        json.dump(employees, fh, indent=4)


def save_log(log: list) -> None:
    with open(list_files.log, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=4)


def save_most_using_command(most_using_command: dict) -> None:
    with open(list_files.most_using_command, "w", encoding="utf") as fh:
        json.dump(most_using_command, fh, indent=4)
