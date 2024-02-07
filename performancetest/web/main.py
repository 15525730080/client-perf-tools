# _*_ coding: utf-8 _*_
import asyncio
import datetime
import hashlib
import multiprocessing
import os
import re
import shutil
import sys
import threading
import time
import traceback
import webbrowser
from builtins import *

import psutil
from airtest.core.android.adb import ADB
from fastapi import FastAPI, Request
from starlette.responses import RedirectResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from tidevice import Usbmux
from tidevice._device import Device

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.getcwd()))))
from performancetest.core.global_data import logger
from performancetest.core.task_handle import TaskHandle
from performancetest.web.dao import connect, Task
from performancetest.web.entity import DeviceEntity, PackageEntity, TaskEntity
from performancetest.web.util import DataCollect

app = FastAPI()
logger.info("工作空间{0}".format(os.getcwd()))
BASE_CSV_DIR = os.path.join(os.path.dirname(__file__), "test_result")
if not os.path.exists(BASE_CSV_DIR):
    os.mkdir(BASE_CSV_DIR)
app.mount("/static", StaticFiles(directory=BASE_CSV_DIR), name="static")
cache_device_info = dict()


@app.middleware("http")
async def http_filter(request: Request, call_next):
    try:
        response = await call_next(request)
    except BaseException as e:
        traceback.print_exc()
        return JSONResponse(content={"code": 500, "msg": str(e)})
    return response


@app.get("/")
def index():
    return RedirectResponse(url="/static/index.html")


@app.get("/get_local_device/")
async def get_local_device(request: Request):
    async def real_func():
        client_host: str = request.client.host
        adb: ADB = ADB(server_addr=(client_host, 5037))
        devices: list = await asyncio.wait_for(asyncio.to_thread(adb.devices), 10)
        logger.info("devices {0}".format(devices))
        res_list: list = []
        for i in devices:
            if i[0] in cache_device_info:
                res_list.append(cache_device_info[i[0]])
                cache_device_info[i[0]]["host"] = client_host
            else:
                adb.serialno = i[0]
                info: dict = await asyncio.wait_for(asyncio.to_thread(adb.get_device_info), 10)
                info["host"] = client_host
                info["port"] = 5037
                info["platform"] = "android"
                res_list.append(info)
                cache_device_info[i[0]] = info
        logger.info(res_list)
        return res_list

    return await asyncio.wait_for(real_func(), timeout=15)


@app.post("/get_local_device_packages/")
async def get_local_device_packages(request: Request, device: DeviceEntity):
    client_host: str = request.client.host
    adb: ADB = ADB(server_addr=(client_host, 5037), serialno=device.serialno)
    app_list: list = await asyncio.wait_for(asyncio.to_thread(adb.list_app), 10)
    logger.info(app_list)
    if not app_list:
        app_list = []
    return [{"name": i, "package": i} for i in app_list]


@app.post("/get_local_device_packages_version/")
async def get_local_device_packages_version(request: Request, package: PackageEntity):
    client_host: str = request.client.host
    adb: ADB = ADB(server_addr=(client_host, 5037), serialno=package.serialno)
    package_info = await asyncio.wait_for(asyncio.to_thread(adb.shell, ['dumpsys', 'package', package.package]), 10)
    matcher = re.search(r'versionName=(.*)', package_info)
    if matcher:
        version = matcher.group(1)
    else:
        version = ''
    return version


@app.get("/get_local_device_ios/")
async def get_local_device_ios(request: Request):
    res = []
    for i in Usbmux().device_udid_list():
        res.append({"serialno": i, "host": "localhost", "port": 5037, "platform": "ios"})
    return res


@app.post("/get_local_device_packages_ios/")
async def get_local_device_packages_ios(request: Request, device: DeviceEntity):
    d = Device(device.serialno)
    return [{"name": i.get("CFBundleName"), "package": i.get("CFBundleIdentifier"),
             "version": i.get("CFBundleShortVersionString")}
            for i in d.installation.iter_installed(app_type="User")]


@app.get("/get_all_task/")
def get_all_task(request: Request):
    with connect() as session:
        all_task = session.query(Task).order_by(Task.start_time.desc()).all()
        return [i.to_dict() for i in all_task]


@app.post("/run_task/")
def run_task(request: Request, task: TaskEntity):
    client_host: str = request.client.host
    port = task.port
    serialno = task.serialno
    package = task.package
    start_time = time.time()
    status = 0
    file_dir = os.path.join(BASE_CSV_DIR, client_host, str(int(start_time)))
    logger.info("任务路径{0}".format(file_dir))
    if not os.path.exists(file_dir):
        os.makedirs(file_dir)
    return_task_id = None
    with connect() as session:
        task_running_count = session.query(Task).filter(Task.host == client_host).filter(
            Task.serialno == task.serialno).filter(
            Task.status != 2).count()
        if task_running_count > 0:
            raise Exception("当前设备仍有任务在进行,无法创建新任务")
        new_task = Task(host=client_host, port=port, serialno=serialno, start_time=datetime.datetime.now(),
                        status=status, file_dir=file_dir, package=package, platform=task.platform)
        session.add(new_task)
        session.commit()
        run_all_monitor(serialno, [client_host, port], package, file_dir, new_task.id, task.platform)
        return_task_id = new_task.id
    return {"code": 200, "taskid": return_task_id}


def run_all_monitor(serialno, server_addr: list, package, save_dir, task_id, device_platform):
    task_process = TaskHandle(serialno=serialno, server_addr=server_addr, package=package, save_dir=save_dir,
                              task_id=task_id, device_platform=device_platform)
    task_process.start()
    task_process.join(timeout=3)


@app.get("/stop_task/")
def stop_task(request: Request, id: int):
    client_host: str = request.client.host
    with connect() as session:
        task_item = session.query(Task).filter(Task.id == id).filter(Task.host == client_host).first()
        if not task_item:
            return {"code": 500, "msg": "暂无权限"}
        try:
            proc = psutil.Process(task_item.pid)
            proc.kill()
        except Exception as e:
            logger.error(e)
            traceback.print_exc()
        task_item.status = 2
        task_item.end_time = datetime.datetime.now()
        try:
            if task_item.platform == "ios":
                t = Device(task_item.serialno)
                with t.connect_instruments() as ts:
                    logger.info('Stop...')
                    ts.close()
        except:
            traceback.print_exc()
    return {"code": 200}


@app.get("/delete_task/")
async def delete_task(request: Request, id: int):
    username = request.headers.get("username")
    client_host: str = request.client.host
    with connect() as session:
        item = session.query(Task).filter(Task.id == id).filter(Task.host == client_host).first()
        if item:
            session.delete(item)
        if os.path.exists(item.file_dir):
            try:
                shutil.rmtree(item.file_dir)
            except:
                traceback.print_exc()
    return {"code": 200}


@app.get("/get_task_status/")
def get_task_status(request: Request, id: int):
    client_host: str = request.client.host
    with connect() as session:
        if str(id) in ["1", "2"]:
            task_item = session.query(Task).filter(Task.id == id).first()
        else:
            task_item = session.query(Task).filter(Task.id == id).filter(Task.host == client_host).first()
        if not task_item:
            return {}
        return task_item.to_dict()


@app.get("/result/")
def result(request: Request, id: int):
    client_host: str = request.client.host
    with connect() as session:
        task_item = session.query(Task).filter(Task.id == id).filter(Task.host == client_host).first()
        if not task_item:
            return {"result": {}}
        file_dir = task_item.file_dir
        try:
            result = DataCollect.read_data_all(file_dir)
        except BaseException as e:
            logger.error(e)
            traceback.print_exc()
            return {"result": {}}
        return {"result": result}


@app.get("/get_username/")
async def get_username(request: Request):
    # 获取客户端的 IP 地址
    client_ip = request.client.host
    # 获取浏览器头中的 User-Agent
    user_agent = request.headers.get("user-agent", "")
    # 生成唯一标识符的原始数据
    raw_data = f"{client_ip}{user_agent}".encode("utf-8")
    # 使用哈希函数（如 SHA256）将原始数据转换为固定长度的哈希值
    hash_value = hashlib.md5(raw_data).hexdigest()
    return hash_value


def open_url():
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:80")


if __name__ == "__main__":
    import uvicorn

    multiprocessing.freeze_support()
    threading.Thread(target=open_url).start()
    uvicorn.run("performancetest.web.main:app", host="0.0.0.0", port=80, log_level="error", workers=4, reload=False)
    logger.info("服务启动成功请访问: http://localhost:80")
