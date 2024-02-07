# coding=utf-8
import json
import os
import subprocess
import sys
import threading
import time
import platform
import traceback
from io import BytesIO
import psutil
import pynvml
import requests

try:
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 128)
except:
    traceback.print_exc()

try:
    pynvml.nvmlInit()
except:
    traceback.print_exc()
    print("本设备gpu获取不适配")
from PIL import ImageGrab
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)


@app.route('/')
def get_platform_info():
    try:
        current_platform = platform.system()
        computer_name = platform.node()
        return jsonify({"platform": current_platform, "computer_name": computer_name, "time": time.time(),
                        "cpu_cores": psutil.cpu_count(),
                        "ram": "{0}G".format(int(psutil.virtual_memory().total / 1024 ** 3)),
                        "rom": "{0}G".format(int(psutil.disk_usage('/').total / 1024 ** 3))})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


@app.route('/pids')
def get_process_pids():
    try:
        process_list = []
        for proc in psutil.process_iter(attrs=['name', 'pid', 'cmdline', 'username']):
            try:
                if ("SYSTEM" not in str(proc.username())) and ("root" not in str(proc.username())):
                    process_list.append(
                        {"name": proc.info['name'], "pid": proc.info['pid'], "cmd": proc.info['cmdline'],
                         "username": proc.username()})
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                print(f"No permission to access process {proc.info['pid']}")
            except Exception as e:
                print(f"Error fetching process info: {str(e)}")
        return jsonify(process_list)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


# https://stackoverflow.com/questions/73673458/how-to-get-accurate-process-cpu-and-memory-usage-with-python
@app.route('/cpu')
def get_process_cpu():
    try:
        pid = request.args.get("pid")
        proc = psutil.Process(pid=int(pid))
        cpu_time = proc.cpu_times()
        cpu_usage = proc.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        return jsonify({"cpu_usage": cpu_usage / cpu_count, "cpu_usage_all": cpu_usage, "cpu_time": cpu_time,
                        "cpu_core_num": cpu_count, "time": time.time()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


@app.route('/cpu_core')
def get_process_cpu_core():
    try:
        cpu_usage = psutil.cpu_percent(interval=1, percpu=True)
        return jsonify({"cpu_core_usage": cpu_usage, "cpu_core_num": psutil.cpu_count(),
                        "cpu_core_avg": sum(cpu_usage) / psutil.cpu_count(), "time": time.time()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


# mb
@app.route('/memory')
def get_process_memory():
    try:
        pid = request.args.get("pid")
        process = psutil.Process(int(pid))
        process_memory_info = process.memory_info()
        process_memory_usage = process_memory_info.rss / (1024 ** 2)  # In MB
        total_memory = psutil.virtual_memory().total / (1024 ** 2)  # In MB
        percentage_used = round((process_memory_usage / total_memory) * 100, 4)
        total_memory = total_memory / 1024
        return jsonify({"process_memory_info": process_memory_usage, "total_memory": total_memory,
                        "percentage_used": percentage_used, "time": time.time()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


@app.route('/thread_num')
def get_process_thread_num():
    try:
        pid = request.args.get("pid")
        process = psutil.Process(int(pid))
        th_number = process.num_threads()
        return jsonify({"process_num_thread": th_number, "time": time.time()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


@app.route('/handle_num')
def get_process_handle_num():
    try:
        pid = request.args.get("pid")
        process = psutil.Process(int(pid))
        th_number = process.num_handles()
        return jsonify({"process_num_handle": th_number, "time": time.time()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


# mb
@app.route('/io')
def get_process_io():
    try:
        pid = request.args.get("pid")
        process = psutil.Process(int(pid))
        # 获取进程的磁盘 I/O 信息
        io_counters = process.io_counters()
        # 获取磁盘读取和写入的字节数
        disk_read_bytes = io_counters.read_bytes
        disk_write_bytes = io_counters.write_bytes
        # 将字节数转换为MB
        disk_read_mb = disk_read_bytes / (1024 * 1024)
        disk_write_mb = disk_write_bytes / (1024 * 1024)
        return jsonify({"disk_read_mb": disk_read_mb, "disk_write_mb": disk_write_mb, "time": time.time()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


# kb
@app.route('/network')
def get_process_network():
    try:
        psutil.net_io_counters()
        recv_mb = psutil.net_io_counters().bytes_recv / 1024
        send_mb = psutil.net_io_counters().bytes_sent / 1024
        return jsonify({"recv_mb": recv_mb, "send_mb": send_mb, "time": time.time()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


@app.route('/gpu')
def get_gpu():
    try:
        pid = request.args.get("pid")
        pid = int(pid)
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count == 1:
            deviceHandle = pynvml.nvmlDeviceGetHandleByIndex(0)  # 获取第一块GPU的句柄
            gpuUtilization = pynvml.nvmlDeviceGetUtilizationRates(deviceHandle)
            gpu_utilization_percentage = gpuUtilization.gpu  # GPU的计算使用率
            return jsonify({"gpu_used": gpu_utilization_percentage, "time": time.time()})
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            for process in processes:
                print(process)
                if process.pid == pid:
                    gpuUtilization = pynvml.nvmlDeviceGetUtilizationRates(deviceHandle)
                    gpu_utilization_percentage = gpuUtilization.gpu  # GPU的计算使用率
                    return jsonify({"gpu_used": gpu_utilization_percentage, "time": time.time()})
        return jsonify({"gpu_used": 0, "time": time.time()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


fps_queue_dict = {}
thread_lock = threading.Lock()
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    bundle_dir = sys._MEIPASS
else:
    # Running in a normal Python environment
    bundle_dir = os.path.dirname(os.path.abspath(__file__))
moniter_exe = os.path.join(bundle_dir, 'happy_moniter.exe')
print("file: ", __file__)


@app.route('/fps')
def get_fps():
    try:
        pid = request.args.get("pid")
        if not pid:
            return jsonify({"frametime": []})
        with thread_lock:
            if pid in fps_queue_dict:
                res_fps = fps_queue_dict[pid]
                fps_queue_dict[pid] = []
                return jsonify({"frametime": res_fps})
            else:
                def start_coller_fps(pid, fps_queue_dict):
                    res_terminate: subprocess.Popen = subprocess.Popen(
                        [moniter_exe, "-process_id", pid, "-output_stdout", "-stop_existing_session"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    res_terminate.stdout.readline()
                    while not res_terminate.poll():
                        line = res_terminate.stdout.readline()
                        if not line:
                            try:
                                res_terminate.kill()
                            except:
                                traceback.print_exc()
                            break
                        try:
                            line = line.decode(encoding="utf-8")
                            line_list = line.split(",")
                            with thread_lock:
                                # fps_queue_dict[pid].append([line_list[1], line_list[7], line_list[9]])
                                fps_queue_dict[pid].append(round(float(line_list[7]), 7))
                        except:
                            print(line)
                            time.sleep(1)
                            traceback.print_exc()
                    del fps_queue_dict[pid]

                fps_queue_dict[pid] = []
                cur_collect_start_time = time.time()
                threading.Thread(target=start_coller_fps, args=(pid, fps_queue_dict)).start()
                return jsonify({"frametime": [], "cur_collect_start_time": cur_collect_start_time})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


@app.route('/stopfps')
def stop_fps():
    pid = request.args.get("pid")
    if not pid:
        return jsonify({"stop": "success"})
    for proc in psutil.process_iter():
        try:
            if proc.name() == "happy_moniter.exe":
                if proc.cmdline() and len(proc.cmdline()) == 5 and (
                        pid == proc.cmdline()[2]):
                    print("kill {0}".format(proc))
                    proc.kill()
                    time.sleep(3)
                    with thread_lock:
                        try:
                            del fps_queue_dict[pid]
                        except:
                            traceback.print_exc()
                    return jsonify({"stop": "success"})
        except (BaseException, psutil.NoSuchProcess) as e:
            traceback.print_exc()
            print(e)
            continue
    return jsonify({"stop": "success"})


@app.route('/img')
def get_process_img():
    try:
        def snopshot(window=None):
            if window:
                screenshot = ImageGrab.grab(
                    bbox=(window.left, window.top, window.left + window.width, window.top + window.height),
                    all_screens=True)
                img_stream = BytesIO()
                screenshot.save(img_stream, format="PNG")
                img_stream.seek(0)
            else:
                screenshot = ImageGrab.grab(all_screens=True)
                img_stream = BytesIO()
                screenshot.save(img_stream, format="PNG")
                img_stream.seek(0)
            return img_stream

        pid = request.args.get("pid")
        not_window_replace = request.args.get("notwindowreplace")
        if pid and platform.system() == "Windows":
            import ctypes
            import pygetwindow as gw
            def get_pid(hwnd):
                pid = ctypes.wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                return pid.value

            def get_window_by_pid(pid):
                for window in gw.getAllWindows():
                    if get_pid(window._hWnd) == pid:
                        return window
                return None

            window = get_window_by_pid(int(pid))
            if window:
                img_stream = snopshot(window)
                return send_file(img_stream, mimetype="image/png")
            else:
                if not_window_replace:
                    return ""
                else:
                    img_stream = snopshot()
                    return send_file(img_stream, mimetype="image/png")
        else:
            img_stream = snopshot()
            return send_file(img_stream, mimetype="image/png")
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})


if __name__ == '__main__':
    version = "1.1.0"
    DEBUG = False
    if len(sys.argv) >= 2:
        DEBUG = True
    url = "http://10.130.131.58:8000/pc_sdk_version" if DEBUG else "http://10.130.131.57:8000/pc_sdk_version"
    try:
        res = requests.get(url)
        res = json.loads(res.text)
        if version != res.get("data"):
            print("sdk版本异常，请下载最新版本")
            time.sleep(10)
            raise Exception("sdk版本异常，请下载最新版本")
    except:
        traceback.print_exc()
        print("sdk版本异常，请下载最新版本")
        time.sleep(10)
        exit(0)
    app.run(host='0.0.0.0', port=9230, threaded=True)
# 打包命令：pyinstaller --uac-admin  --onefile --add-data happy_moniter.exe:. pc_server.py  -i  logo.ico
