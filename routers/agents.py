from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from functions import open_files
from keyboards.agents import build_agents_keyboard#, build_product_action
from functions import products as funcs_prods, reviews as funcs_revs
from form.products import ProdCreateForm
from form.reviews import ReviewCreateForm
from log.log import bot_log
from models import AgentModel, async_session, Status
from middleware import DbSessionMiddleware


agent_router = Router()
agent_router.update.outer_middleware(DbSessionMiddleware(session_pool=async_session))


@agent_router.message(F.text == "Список агентів")
async def show_all_prods(message: Message, state: FSMContext, session: AsyncSession) -> None:
    result = await session.execute(
        select(AgentModel).filter_by(status=Status.in_progress)
    )
    agents = result.scalars().all()
    keyboard = build_agents_keyboard(agents)
    await edit_or_answer(
        message,
        "Список товарів",
        keyboard
    )


@product_router.callback_query(F.data.startswith("product_"))
async def show_prod_action(callback: CallbackQuery, state: FSMContext) -> None:
    prod_id = int(callback.data.split("_")[-1])
    product = open_files.products[prod_id]
    await edit_or_answer(
        callback.message,
        product,
        build_product_action(product),
        ReplyKeyboardRemove())


async def edit_or_answer(message: Message, text: str, keyboard=None, *args, **kwargs):
   if message.from_user.is_bot:
       await message.edit_text(text=text, reply_markup=keyboard, **kwargs)
   else:
       await message.answer(text=text, reply_markup=keyboard, **kwargs)


@product_router.callback_query(F.data.startswith("del prod"))
async def del_prod_action(callback: CallbackQuery, state: FSMContext) -> None:
    product = callback.data.split(":")[-1]
    msg = funcs_prods.del_prod_by_name(product)
    await callback.message.answer(msg)
    # return await show_all_prods(callback.message, state)


@product_router.callback_query(F.data.startswith("sold prod"))
async def sold_prod_action(callback: CallbackQuery, state: FSMContext):
    product = callback.data.split(":")[-1]
    funcs_prods.sold_prod(product)
    text = f"Товар '{product}' продано"
    await callback.message.answer(text)
    # return await show_all_prods(callback.message, state)


@product_router.callback_query(F.data == "back")
async def back_handler(callback: CallbackQuery, state: FSMContext) -> None:
    state.clear()
    return await show_all_prods(callback.message, state)


@product_router.message(F.text == "Додати новий товар")
async def add_new_prod_action(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ProdCreateForm.name)
    await edit_or_answer(message, "Введіть назву товару")


@product_router.message(ProdCreateForm.name)
async def process_prod_name(message: Message, state: FSMContext):
    data = await state.update_data(name=message.text)
    await state.clear()
    msg = funcs_prods.add_prod(data.get("name"))
    await message.answer(msg)
    # return await show_all_prods(message, state)


@product_router.message(F.text == "Список проданих товарів")
async def show_products_sold(message: Message, state: FSMContext):
    products_sold = open_files.products_sold
    await message.answer("\n".join(products_sold))
    # return await show_all_prods(message, state)


@product_router.message(F.text == "Відгуки")
async def show_reviews(message: Message, state: FSMContext):
    reviews = open_files.reviews
    reviews = [f"{i}. {review}\n" for i, review in enumerate(reviews, start=1)]
    await message.answer("".join(reviews))
    # return await show_all_prods(message, state)


@product_router.message(F.text == "Додати відгук")
async def add_new_review(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ReviewCreateForm.text)
    await edit_or_answer(message, "Введіть свій відгук")


@product_router.message(ReviewCreateForm.text)
async def process_review_text(message: Message, state: FSMContext):
    data = await state.update_data(text=message.text)
    await state.clear()
    msg = funcs_revs.add_review(data.get("text"))
    await message.answer(msg)
    # return await show_all_prods(message, state)


@product_router.message(F.text == "Знайти групи символів,\nякі повторюються\n(використовуючи всі відгуки)")
async def find_repeated_chars(message: Message, state: FSMContext):
    reviews = open_files.reviews
    msg = funcs_revs.find_repeated_chars(reviews)
    await message.answer(msg)
    # return await show_all_prods(message, state)