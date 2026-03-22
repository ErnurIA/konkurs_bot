"""FSM күйлері: сынып таңдаудан тест бастауға дейін."""
from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    waiting_for_class = State()
    waiting_for_name = State()
    waiting_to_start_test = State()
