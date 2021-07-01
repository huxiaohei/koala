import traceback
import weakref
from abc import ABC
from koala.message import RpcMessage
from koala.typing import *
from koala.logger import logger
from koala.network.socket_session import SocketSession, SocketSessionManager
from koala.server.actor_context import ActorContext
from koala.server.rpc_proxy import get_rpc_proxy


_session_manager = SocketSessionManager()


async def _send_message(session_id: int, msg: object):
    session = _session_manager.get_session(session_id)
    if session:
        await session.send_message(msg)


class ActorBase(ABC):
    def __init__(self):
        self.__session_id = 0
        self.__uid = 0
        self.__context = None
        self.__socket_session = None
        pass

    def _init_actor(self, uid: object, context: ActorContext):
        self.__uid = uid
        self.__context = context
        pass

    @property
    def type_name(self):
        return self.__qualname__

    @property
    def uid(self) -> object:
        return self.__uid

    @property
    def context(self) -> ActorContext:
        return self.__context

    def set_session_id(self, session_id: int):
        self.__session_id = session_id
        socket_session = _session_manager.get_session(self.__session_id)
        self.__socket_session = weakref.ref(socket_session)

    @property
    def session_id(self) -> int:
        return self.__session_id

    @property
    def _socket(self) -> Optional[SocketSession]:
        if self.__socket_session is not None:
            return self.__socket_session()
        return None

    async def _activate_async(self):
        try:
            await self.on_activate_async()
        except Exception as e:
            logger.error("Actor.OnActivateAsync, Actor:%s/%s, Exception:%s, StackTrace:%s" %
                         (self.type_name, self.uid, e, traceback.format_exc()))

    async def _deactivate_async(self):
        try:
            await self.on_deactivate_async()
        except Exception as e:
            logger.error("Actor.OnDeactivateAsync, Actor:%s/%s, Exception:%s, StackTrace:%s" %
                         (self.type_name, self.uid, e, traceback.format_exc()))

    async def on_activate_async(self):
        pass

    async def on_deactivate_async(self):
        pass

    async def send_message(self, msg: object, session_id=0):
        socket_proxy = self._socket
        if session_id != 0:
            session = _session_manager.get_session(session_id)
            if session:
                socket_proxy = session
        if socket_proxy:
            await socket_proxy.send_message(msg)
        else:
            logger.warning("Actor.SendMessage, Actor:%s/%s , SocketSession not found" % (self.type_name, self.uid))

    async def dispatch_user_message(self, msg: object) -> None:
        """
        用户需要自己处理的消息
        不要抛出异常
        :param msg: 用户自定义消息
        """
        if isinstance(msg, RpcMessage):
            logger.debug("Actor.DispatchUserMessage, Actor:%s/%s, MessageType:%s" %
                         (self.type_name, self.uid, type(msg.meta)))
        else:
            logger.debug("Actor.DispatchUserMessage, Actor:%s/%s" % (self.type_name, self.uid))

    def get_proxy(self, i_type: Type[T], uid: object) -> T:
        o = get_rpc_proxy(i_type, uid, self.context)
        return cast(T, o)
