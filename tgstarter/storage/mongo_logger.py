from typing import (
    Awaitable,
    Callable,
    Optional,
    Dict,
    Tuple,
    Union,
    Any,
    Mapping,
    Sequence,
)
import datetime
import traceback

import pytz
from aiogram import types
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
import jinja2

from tgstarter.models import storage as models
from tgstarter.utils.typing import ExcInfo


def filter_parameters(params: Mapping[str, Any], ignore: Sequence[str]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in params.items()
        if key not in ignore
    }


def get_level_logger(level: models.LogLevel) -> Callable[..., Awaitable]:
    async def appropriate_logger(
        self,
        update: Optional[types.Update] = None,
        task: Optional[models.LogTask] = None,
        type: Optional[models.LogType] = None,
        from_bot: bool = False,
        exc_info: Optional[ExcInfo] = None
    ) -> Optional[str]:
        return await self.log(
            update=update,
            task=task,
            type=type,
            level=level,
            from_bot=from_bot,
            exc_info=exc_info
        )

    return appropriate_logger


class MongoLogger:

    def __init__(
        self,
        *,
        mongo_client: AsyncIOMotorClient,
        mongo_database: AsyncIOMotorDatabase,
        message_format: jinja2.Template,
        timezone: pytz.tzinfo.DstTzInfo,
        collection_name: str = 'logs',
        default_level: models.LogLevel = models.LogLevel.INFO,
        default_type: models.LogType = models.LogType.EVENT
    ) -> None:
        self.client = mongo_client
        self.database = mongo_database
        self.collection_name = collection_name
        self.logs: AsyncIOMotorCollection = self.database[collection_name]

        self.message_format = message_format
        self.timezone = timezone
        self.default_level = default_level
        self.default_type = default_type

    def render_message(
        self,
        utc_datetime: datetime.datetime,
        object_id: ObjectId,
        exception: Union[Dict[str, str], Dict[str, None]]
    ) -> str:
        return self.message_format.render(
            error_type=exception['type'],
            error_value=exception['value'],
            datetime=utc_datetime,
            object_id=object_id,
            traceback=exception['traceback'],
            # separator=self.SEPARATOR,
        )

    def prepare_exception(self, exc_info: ExcInfo) -> Union[Dict[str, str], Dict[str, None]]:
        if exc_info == (None, None, None):
            return {
                'type': None,
                'value': None,
                'traceback': None,
            }
        else:
            type_, value, tb = exc_info
            tb = traceback.TracebackException(type_, value, tb)
            return {
                'type': type_.__name__,
                'value': str(value),
                'traceback': ''.join(tb.format()),
            }

    def prepare_task(self, task: Optional[models.LogTask]) -> Optional[models.LogTask]:
        # TODO: make serialization deeper
        if task is None:
            return task
        if task.args:
            task.args = list(map(str, task.args))
        if task.kwargs:
            task.kwargs = {
                key: str(value) for key, value in task.kwargs.items()
            }
        return task

    def chat_and_user_from_update(self, update: Optional[types.Message]) -> Tuple[types.Chat, types.User]:
        chat = types.Chat()
        user = types.User()
        if update is None:
            return chat, user

        if update.message:
            user = update.message.from_user
            chat = update.message.chat

        elif update.edited_message:
            user = update.edited_message.from_user
            chat = update.edited_message.chat

        elif update.channel_post:
            chat = update.channel_post.chat

        elif update.edited_channel_post:
            chat = update.edited_channel_post.chat

        elif update.inline_query:
            user = update.inline_query.from_user

        elif update.chosen_inline_result:
            user = update.chosen_inline_result.from_user

        elif update.callback_query:
            if update.callback_query.message:
                chat = update.callback_query.message.chat
            user = update.callback_query.from_user

        elif update.shipping_query:
            user = update.shipping_query.from_user

        elif update.pre_checkout_query:
            user = update.pre_checkout_query.from_user

        elif update.poll:
            pass

        elif update.poll_answer:
            pass

        return chat, user

    async def log(
        self,
        update: Optional[types.Update] = None,
        task: Optional[models.LogTask] = None,
        level: Optional[models.LogLevel] = None,
        type: Optional[models.LogType] = None,
        from_bot: bool = False,
        exc_info: Optional[ExcInfo] = None
    ) -> Optional[str]:

        date_time = datetime.datetime.utcnow()
        chat, user = self.chat_and_user_from_update(update=update)
        task = self.prepare_task(task)
        exception = self.prepare_exception(exc_info) if exc_info is not None else None
        model = models.Log(
            datetime=date_time,
            level=level.value if level else self.default_level.value,
            type=type.value if type else self.default_type.value,
            came_from=models.EventFrom.USER if not from_bot else models.EventFrom.BOT,
            user_info=models.LogUserInfo(
                user=user.to_python(),
                chat=chat.to_python()
            ),
            update=update.to_python() if update is not None else None,
            task=task,
            exception=exception
        )
        document = model.dict()
        insert_result = await self.logs.insert_one(document)
        if exception is not None:
            return self.render_message(
                utc_datetime=date_time,
                object_id=insert_result.inserted_id,
                exception=exception
            )

    debug = get_level_logger(level=models.LogLevel.DEBUG)
    info = get_level_logger(level=models.LogLevel.INFO)
    warning = get_level_logger(level=models.LogLevel.WARNING)
    error = get_level_logger(level=models.LogLevel.ERROR)
    critical = get_level_logger(level=models.LogLevel.CRITICAL)
