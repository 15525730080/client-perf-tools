# coding=utf-8
import asyncio
import os
import time
import traceback
from builtins import *
import adbutils
from multiprocessing.context import Process
from performancetest.web.dao import connect, Task
from logzero import logger
from android_tool import perf as android_perf
from pc_tool import perf as pc_perf



class TaskHandle(Process):

    def __init__(self, serialno: str, server_addr: list[str], package: str, save_dir: str, task_id: int,
                 device_platform: str):
        super(TaskHandle, self).__init__()
        self.serialno = serialno
        self.server_addr = server_addr
        self.package = package
        self.save_dir = save_dir
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        self.daemon = True
        self.task_id = task_id
        self.device_platform = device_platform  # ios | android

    def start(self):
        logger.info("join task handle")
        super().start()

    def run(self):
        logger.info("join task handle run")
        with connect() as session:
            current_task_running = session.query(Task).filter(
                Task.id == self.task_id).first()
            if current_task_running:
                current_task_running.status = 1
                current_task_running.pid = self.pid
            else:
                # raise Exception("任务不存在")
                pass
            if self.device_platform == "android":
                try:
                    device = adbutils.device(serial=self.serialno)
                    device.app_start(self.package)
                except:
                    traceback.print_exc()
                    current_task_running.status = -1
                    session.flush()
                    session.commit()
                    raise Exception("缺少设备{0}任务启动失败".format(self.serialno))
                time.sleep(0.1)
                asyncio.run(android_perf(device, self.package, self.save_dir))
            elif self.device_platform == "ios":
                raise Exception("ios 设备暂不支持，因为目前ios17以上性能获取和操作需要造一些轮子，所有暂缓实现")
            elif self.device_platform == "pc":
                asyncio.run(pc_perf(self.package, self.save_dir))

    def stop(self):
        pass

    def suspend(self):
        pass


if __name__ == '__main__':
    # task_process = TaskHandle(serialno="emulator-5554", server_addr=["localhost", 5037],
    #                           package="com.sankuai.meituan.merchant", save_dir="localhost", task_id=1,
    #                           device_platform="android")
    # task_process.start()
    # time.sleep(2 * 10)
    task_process = TaskHandle(serialno=None, server_addr=None,
                              package="6728", save_dir="localhost", task_id=1, device_platform="pc")
    task_process.start()
    time.sleep(2 * 10)
