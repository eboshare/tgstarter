import asyncio
import typing

import aiogram
from aiogram.types import base
from aiogram import types


class Bot(aiogram.Bot):
    async def send_large_message(
        self,
        chat_id: typing.Union[base.Integer, base.String],
        text: base.String,
        # parse_mode: typing.Optional[base.String] = None,
        disable_web_page_preview: typing.Optional[base.Boolean] = None,
        disable_notification: typing.Optional[base.Boolean] = None,
        reply_to_message_id: typing.Optional[base.Integer] = None,
        # reply_markup: typing.Union[
        #     None,
        #     types.InlineKeyboardMarkup,
        #     types.ReplyKeyboardMarkup,
        #     types.ReplyKeyboardRemove,
        #     types.ForceReply,
        # ] = None,
        max_length: base.Integer = 4096
    ) -> typing.List[types.Message]:
        """No parse_mode is supported"""
        kwargs = locals()
        ignore_keys = (
            'self',
            'text',
            'max_length',
        )
        for key in ignore_keys:
            del kwargs[key]

        start_index = 0
        end_index = max_length
        cut_text = text[start_index:end_index]

        result_messages = []
        while cut_text:
            message = await self.send_message(text=cut_text, **kwargs)
            result_messages.append(message)
            start_index = end_index
            end_index += max_length
            cut_text = text[start_index:end_index]

        return result_messages

    async def send_with_action(
        self,
        chat_id: int,
        coroutine: typing.Awaitable,
        action: str = types.ChatActions.TYPING,
        delay: int = 5
    ) -> typing.Any:
        async def infinite_chat_action() -> None:
            while True:
                await self.send_chat_action(chat_id=chat_id, action=action)
                await asyncio.sleep(delay)

        tasks = [
            asyncio.create_task(coro)
            for coro in (infinite_chat_action(), coroutine)
        ]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        coro = next(iter(done))
        return coro.result()
