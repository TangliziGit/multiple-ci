import http
import time
import traceback
from typing import Any
from enum import Enum

import tornado.web


class HttpStatus(Enum):
    success = 1
    failure = 2

class Response:
    def __init__(self, code, status, message='', payload=None):
        self.resp = {
            'code': code,
            'status': status,
            'message': message,
            'time': time.time_ns(),
            'payload': payload,
        }

    def __getitem__(self, item):
        return self.resp.get(item, None)

    def finish(self, handler: tornado.web.RequestHandler):
        handler.finish(self.resp)

    @classmethod
    def ok(cls, payload=None, message=''):
        return Response(http.HTTPStatus.OK, HttpStatus.success.name,
                        payload=payload, message=message)

    @classmethod
    def err(cls, code, message, payload=None):
        return Response(code, HttpStatus.failure.name,
                        payload=payload, message=message)


class BaseHandler(tornado.web.RequestHandler):
    def data_received(self, chunk): pass

    def ok(self, payload=None, message=''):
        Response(http.HTTPStatus.OK, HttpStatus.success.name,
                        payload=payload, message=message).finish(self)

    def err(self, code, message, payload=None):
        Response(code, HttpStatus.failure.name,
                        payload=payload, message=message).finish(self)

    def write_error(self, status_code: int, **kwargs: Any) -> None:
        if "exc_info" in kwargs:
            self.set_header("Content-Type", "text/plain")
            self.err(http.HTTPStatus.INTERNAL_SERVER_ERROR,
                     message=traceback.format_exception(*kwargs["exc_info"])[-1])
        else:
            self.err(status_code, message='unknown error occurred')