import os
import json

from files import list_files


if not os.path.exists(list_files.products):
    with open(list_files.products, "w", encoding="utf-8") as fh:
        json.dump([], fh)

with open(list_files.products, "r", encoding="utf-8") as fh:
    products = json.load(fh)

if not os.path.exists(list_files.reviews):
    with open(list_files.reviews, "w", encoding="utf-8"):
        pass

with open(list_files.reviews, "r", encoding="utf-8") as fh:
    reviews = json.load(fh)

if not os.path.exists(list_files.employees):
    with open(list_files.employees, "w", encoding="utf-8") as fh:
        json.dump({}, fh)

with open(list_files.employees, "r", encoding="utf-8") as fh:
    employees = json.load(fh)

if not os.path.exists(list_files.products_sold):
    with open(list_files.products_sold, "w", encoding="utf-8") as fh:
        json.dump([], fh)

with open(list_files.products_sold, "r", encoding="utf-8") as fh:
    products_sold = json.load(fh)

if not os.path.exists(list_files.log):
    with open(list_files.log, "w", encoding="utf-8") as fh:
        json.dump([], fh)

with open(list_files.log, "r", encoding="utf-8") as fh:
    log = json.load(fh)

if not os.path.exists(list_files.most_using_command):
    with open(list_files.most_using_command, "w", encoding="utf-8") as fh:
        json.dump({}, fh)

with open(list_files.most_using_command, "r", encoding="utf-8") as fh:
    most_using_command = json.load(fh)