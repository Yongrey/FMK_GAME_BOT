import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.middlewares.fsm import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv('TOKEN')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class GameStates(StatesGroup):
    choosing_mode = State()
    waiting_for_players = State()
    waiting_for_player1 = State()
    waiting_for_player2 = State()
    waiting_for_names = State()
    waiting_for_action1 = State()
    waiting_for_action2 = State()
    waiting_for_action3 = State()


@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Это игра 'Переспать, жениться, убить'. Выберите режим игры:\n"
                        "/single - Одиночный режим\n"
                        "/group - Групповой режим\n"
                        "/stop - Прекратить игру")


@dp.message_handler(commands=['single'])
async def start_single_game(message: types.Message):
    await message.reply("Вы выбрали режим на одного. Введите три имени через запятую.")
    await GameStates.waiting_for_names.set()


@dp.message_handler(commands=['group'])
async def start_group_game(message: types.Message):
    await message.reply("Вы выбрали групповой режим. Введите имя игрока, который будет загадывать имена.")
    await GameStates.waiting_for_player1.set()


@dp.message_handler(commands=['stop'], state='*')
async def stop_game(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply("Игра остановлена. Хотите сыграть еще раз? Выберите режим игры /start.")
    logger.info(f"User @{message.from_user.username} stopped the game")


@dp.message_handler(state=GameStates.waiting_for_player1)
async def handle_player1(message: types.Message, state: FSMContext):
    player1 = message.text.strip()
    await state.update_data(player1=player1)
    await message.reply(
        f"Игрок {player1} будет загадывать имена. Теперь введите имя игрока, который будет делать выбор.")
    await GameStates.waiting_for_player2.set()


@dp.message_handler(state=GameStates.waiting_for_player2)
async def handle_player2(message: types.Message, state: FSMContext):
    player2 = message.text.strip()
    await state.update_data(player2=player2)
    await message.reply(f"Игрок {player2} будет делать выбор. {player2}, введите три имени через запятую.")
    await GameStates.waiting_for_names.set()


@dp.message_handler(state=GameStates.waiting_for_names)
async def get_names(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mode = data['mode']

    if mode == "group":
        player1 = data['player1']
        if message.from_user.username != player1:
            await message.reply(f"Имена должен ввести игрок {player1}.")
            return

    names = message.text.split(',')
    if len(names) != 3:
        await message.reply("Пожалуйста, введите ровно три имени через запятую.")
        return

    names = [name.strip() for name in names]
    await state.update_data(names=names)

    logger.info(f"User @{message.from_user.username} provided names: {names}")

    keyboard = generate_keyboard(names[0], [])
    await message.reply(f"Выберите действие для персонажа {names[0]}:", reply_markup=keyboard)
    await GameStates.waiting_for_action1.set()


def generate_keyboard(name, used_actions):
    keyboard = InlineKeyboardMarkup(row_width=3)
    actions = ['fuck', 'marry', 'kill']
    for action in actions:
        if action not in used_actions:
            keyboard.add(InlineKeyboardButton(text=f"{action.capitalize()}", callback_data=f"{action}_{name}"))
    return keyboard


@dp.callback_query_handler(state=GameStates.waiting_for_action1)
async def process_callback1(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mode = data['mode']
    player2 = data.get('player2')

    if mode == "group" and callback_query.from_user.username != player2:
        await bot.answer_callback_query(callback_query.id, text="Только выбранный игрок может сделать выбор.")
        return

    action, name = callback_query.data.split('_')
    names = data['names']
    remaining_names = [n for n in names if n != name]
    used_actions = [action]

    await state.update_data(action1=action, name1=name, remaining_names=remaining_names, used_actions=used_actions)

    logger.info(f"User @{callback_query.from_user.username} chose: {action} for {name}")

    keyboard = generate_keyboard(remaining_names[0], used_actions)
    await bot.answer_callback_query(callback_query.id)
    await bot.edit_message_text(f"Выберите действие для персонажа {remaining_names[0]}:", callback_query.from_user.id,
                                callback_query.message.message_id, reply_markup=keyboard)
    await GameStates.waiting_for_action2.set()


@dp.callback_query_handler(state=GameStates.waiting_for_action2)
async def process_callback2(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mode = data['mode']
    player2 = data.get('player2')

    if mode == "group" and callback_query.from_user.username != player2:
        await bot.answer_callback_query(callback_query.id, text="Только выбранный игрок может сделать выбор.")
        return

    action, name = callback_query.data.split('_')
    remaining_names = data['remaining_names']
    remaining_names = [n for n in remaining_names if n != name]
    used_actions = data['used_actions'] + [action]

    await state.update_data(action2=action, name2=name, remaining_names=remaining_names, used_actions=used_actions)

    logger.info(f"User @{callback_query.from_user.username} chose: {action} for {name}")

    keyboard = generate_keyboard(remaining_names[0], used_actions)
    await bot.answer_callback_query(callback_query.id)
    await bot.edit_message_text(f"Выберите действие для персонажа {remaining_names[0]}:", callback_query.from_user.id,
                                callback_query.message.message_id, reply_markup=keyboard)
    await GameStates.waiting_for_action3.set()


@dp.callback_query_handler(state=GameStates.waiting_for_action3)
async def process_final_callback(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mode = data['mode']
    player2 = data.get('player2')

    if mode == "group" and callback_query.from_user.username != player2:
        await bot.answer_callback_query(callback_query.id, text="Только выбранный игрок может сделать выбор.")
        return

    action, name = callback_query.data.split('_')
    used_actions = data['used_actions'] + [action]

    final_selection = {
        'fuck': data['name1'] if data['action1'] == 'fuck' else (data['name2'] if data['action2'] == 'fuck' else name),
        'marry': data['name1'] if data['action1'] == 'marry' else (
            data['name2'] if data['action2'] == 'marry' else name),
        'kill': data['name1'] if data['action1'] == 'kill' else (data['name2'] if data['action2'] == 'kill' else name)
    }

    logger.info(f"User @{callback_query.from_user.username} made final selections: {final_selection}")

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id,
                           f"Ваш выбор:\nПереспать: {final_selection['fuck']}\nЖениться: {final_selection['marry']}\nУбить: {final_selection['kill']}")
    await state.finish()
    await bot.send_message(callback_query.from_user.id, "Хотите сыграть еще раз? Выберите режим игры /start.")


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
