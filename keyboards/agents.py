from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def build_global_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Список агентів")
    builder.button(text="Додати нового агента")
    builder.button(text="Перевірити статус")
    builder.adjust(1)
    return builder.as_markup()


def build_agents_keyboard(products: list):
    builder = InlineKeyboardBuilder()
    for index, product in enumerate(products):
        builder.button(text=product, callback_data=f"product_{index}")
    builder.adjust(4)
    return builder.as_markup()


# def build_product_action(product: list) -> InlineKeyboardMarkup:
#     builder = InlineKeyboardBuilder()
#     builder.button(text="Видалити товар", callback_data=f"del prod:{product}")
#     builder.button(text="Продати товар", callback_data=f"sold prod:{product}")
#     return builder.as_markup()
