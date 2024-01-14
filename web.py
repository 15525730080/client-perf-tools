import asyncio
import base64
import threading
import traceback

import adbutils
import tornado
from PIL import Image
from io import BytesIO
from tornado.websocket import WebSocketHandler
from core.android_tool import *
from core.ios_tool import *


async def handle_request(func, **kwargs):
    try:
        func_signature = inspect.signature(func)
        valid_kwargs = {k: kwargs[k] for k in func_signature.parameters if k in kwargs}
        if not valid_kwargs:
            result = await func()
        else:
            result = await func(**valid_kwargs)
        if isinstance(result, Image.Image):
            with BytesIO() as buffer:
                result.save(buffer, format="JPEG")
                image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                return {"data": image_data, "content_type": "image/jpeg"}
        return {"data": result}
    except Exception as e:
        return {"error": str(e)}


class CommonError(object):
    LOSE_SERIAL = "缺少设备序列号"
    INVALID_FUNC = "不存在的方法"


class PerfWebSocket(WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        def run():
            if self.request.arguments["serial"] and self.request.arguments["package"]:
                serial = self.request.arguments["serial"][0].decode()
                package = self.request.arguments["package"][0].decode()
                if serial and package:
                    self.serial = serial
                    try:
                        asyncio.run(perf([
                            "cpu", "memory",
                            "fps",
                            "gpu", "package_process_info", "battery", "ps"
                            ],
                                         adbutils.device(serial=serial), package, self))
                    except Exception as e:
                        traceback.print_exc()
                        logger.error(e)
                    logger.info("stop success")

        th = threading.Thread(target=run)
        th.start()
        logger.info("start {0}".format(self))

    def on_close(self):
        if self.monitors:
            for key, cur_coroutine in self.monitors.items():
                cur_coroutine.stop()
        logger.info("close end")


class WebHandler(tornado.web.RequestHandler):
    def data_received(self, chunk: bytes):
        logger.info(chunk)

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")  # 允许所有来源
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    async def get(self, func_name):
        device_serial = self.get_query_argument("device_serial", default=None)
        func = globals().get(func_name)
        device = None
        if device_serial:
            device = adbutils.device(serial=device_serial) if device_serial else None
        if not func or not callable(func):
            self.write(json.dumps({"error": CommonError.INVALID_FUNC}))
            return

        func_args = {k: self.get_query_argument(k) for k in self.request.arguments}
        func_args["device"] = device
        result = await handle_request(func, **func_args)
        self.write(json.dumps(result))


def make_app():
    return tornado.web.Application([
        (r"/perf", PerfWebSocket),
        (r"/([^/]+)", WebHandler),
    ])


if __name__ == "__main__":
    app = make_app()
    app.listen(8888)
    logger.info("server star")
    tornado.ioloop.IOLoop.current().start()
    asyncio.run(Fps(adbutils.device(serial="4bce207"), "com.sankuai.meituan").gfx_fps())
    # asyncio.run(Fps(adbutils.device(serial="4bce207"), "com.sankuai.meituan").fps())
