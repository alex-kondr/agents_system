from log.log import bot_log

from functions import save_files, open_files


def add_prod(product: str) -> str:
    products = open_files.products

    if product not in products:
        products.append(product)
        msg = f"\nТовар '{product}' доданий до списку"
        save_files.save_products(products)
    else:
        msg = "\nТакий товар вже є у списку"

    bot_log(msg)
    return msg


def del_prod_by_name(product: list) -> str:
    products = open_files.products

    if product in products:
        products.remove(product)
        msg = f"\nТовар '{product}' видалено зі списку"
        save_files.save_products((products))
    else:
        msg = "\nТакого товару немає у списку"

    bot_log(msg)
    return msg


def sold_prod(product) -> str:
    products = open_files.products
    products_sold = open_files.products_sold

    if product in products:
        products.remove(product)
        products_sold.append(product)
        msg = f"\nТовар '{product}' продано"
        save_files.save_products(products)
        save_files.save_products_sold(products_sold)
    else:
        msg = "\nТакого товару немає у списку"

    bot_log(msg)
    return msg


def find_palidrome(products: list) -> None:
    palin_prod = []
    for product in products:
        if product.lower() == product[::-1].lower():
            palin_prod.append(product)

    message = f"В списку товарів є такі слова-паліндроми:\n{palin_prod}" if palin_prod else "В списку товарів відсутні слова паліндроми."
    print(message)
