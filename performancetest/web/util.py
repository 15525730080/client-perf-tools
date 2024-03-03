import asyncio
import concurrent.futures
import json
import os
import traceback
from builtins import *
from pathlib import Path

import numpy as np

from logzero import logger


class DataCollect(object):

    def __init__(self, file_dir_path=None):
        """
        任务所在文件夹, 设置了这个文件夹其他的不需要再传file_path
        """
        self.file_dir_path = file_dir_path
        self.is_need_relative_time = False

    def __read_csv_file(self, file_path=None, skip_rows=1, usecols=None):
        """
        读取cpu，memory，fps，gpu，温度等csv文件的值
        """
        if not usecols:
            csv_data = np.genfromtxt(file_path, skip_header=skip_rows, delimiter=",", dtype=float, filling_values=0)
        else:
            csv_data = np.genfromtxt(file_path, skip_header=skip_rows, delimiter=",", dtype=float, filling_values=0,
                                     usecols=usecols)
        return csv_data

    def __read_cpu(self, file_path=None):
        if not file_path:
            file_path = os.path.join(self.file_dir_path, "cpu.csv")
        return self.__read_csv_file(file_path=file_path)

    def __read_memory(self, file_path=None):
        if not file_path:
            file_path = os.path.join(self.file_dir_path, "memory.csv")
        return self.__read_csv_file(file_path=file_path)

    def __read_gpu(self, file_path=None):
        if not file_path:
            file_path = os.path.join(self.file_dir_path, "gpu.csv")
        return self.__read_csv_file(file_path=file_path)

    def __read_device_temperature(self, file_path=None):
        if not file_path:
            file_path = os.path.join(self.file_dir_path, "devicebattery.csv")
        return self.__read_csv_file(file_path=file_path, usecols=(0, 1))

    def __read_device_battery_level(self, file_path=None):
        if not file_path:
            file_path = os.path.join(self.file_dir_path, "devicebattery.csv")
        return self.__read_csv_file(file_path=file_path, usecols=(0, 2))

    def __read_fps(self, file_path=None):
        if not file_path:
            file_path = os.path.join(self.file_dir_path, "fps.csv")
        return self.__read_csv_file(file_path=file_path)

    def __read_network(self, file_path=None):
        if not file_path:
            file_path = os.path.join(self.file_dir_path, "network.csv")
        return self.__read_csv_file(file_path=file_path)

    # 监控类型对应的读取方法
    __monitortype_func = {"cpu": __read_cpu, "memory": __read_memory, "fps": __read_fps,
                          "gpu": __read_gpu, "devicebatterytemperature": __read_device_temperature,
                          "devicebatterylevel": __read_device_battery_level, "network": __read_network}

    # 读数据的方法使用：DataCollect.read_data(1, "cpu", "memory", "fps")
    @classmethod
    def read_data(cls, file_dir_path: int, /, *args, **kwargs):
        """
        param: "cpu", "memory"
        return:
        {
            public_imgs：[{"16xxxxxx": "pic_path"}, {"16xxxxxx": "pic_path1"}]
            public_start_time：16xxxxxx: int,
            public_end_time：16xxxxxx: int,
            cpu: {
                 time：[16xxxxxx, 16xxxxxx]  //cpu,memory,fps 开始真实时间戳相同
                 value: [100, 101]
                 relative_time: [00:00, 00:10]
            },
            memory: {
                  time：[16xxxxxx, 16xxxxxx]  //cpu,memory,fps 开始真实时间戳相同
                 value: [100, 101]

            }
        }
        """
        return cls.item_result(file_dir_path, monitortypes=args,
                               is_need_relative_time=kwargs.get("is_need_relative_time", True))

    # 读所有类型的数据的方法使用：DataCollect.read_data(1, "cpu", "memory", "fps")
    @classmethod
    def read_data_all(cls, file_dir_path):
        return cls.read_data(file_dir_path, *cls.__monitortype_func.keys())

    @classmethod
    def item_result(cls, file_dir_path: int, monitortypes: tuple, **kwargs):
        data_collect = DataCollect(file_dir_path=file_dir_path)
        result_dict: dict = {}  # 存储每种监控类型的结果
        for monitor_name in monitortypes:
            try:
                future = cls.__monitortype_func.get(monitor_name)(data_collect)
                if future.any():
                    result_dict[monitor_name] = future
            except:
                traceback.print_exc()
        for key, value_future in list(result_dict.items()):
            try:
                value_future_res = value_future
                if len(value_future_res.shape) < 2:
                    raise Exception("数组低于2维度")
                if value_future_res.size <= 0:
                    raise Exception("数据结果为空")
                result_dict[key] = value_future_res
            except Exception as e:
                logger.error(e)
                result_dict.pop(key, None)
        if result_dict:
            public_start_time, public_end_time = cls.get_public_time(result_dict)
            # 获取所有结果
            for (monitor_name, future_result) in result_dict.items():
                result_dict[monitor_name] = cls.time_value_result(monitor_name, future_result,
                                                                  public_start_time, public_end_time,
                                                                  is_need_relative_time=kwargs.get(
                                                                      "is_need_relative_time", False))
            result_dict["public_start_time"] = public_start_time
            result_dict["public_end_time"] = public_end_time
            img_path_dir = os.path.join(file_dir_path, "picture_log")
            if os.path.exists(img_path_dir):
                task_dir, task_name_int = os.path.split(file_dir_path)
                _, host = os.path.split(task_dir)
                result_dict["public_imgs"] = cls.get_public_imgs(img_path_dir, public_start_time,
                                                                 public_end_time, task_name_int, host)
        try:
            result_dict = cls.format_data(result_dict, monitortypes)
        except:
            traceback.print_exc()
        return result_dict

    @staticmethod
    def get_public_imgs(img_path_dir: str, public_start_time: int, public_end_time: int, task_name_int: str, host: str):
        all_imgs = os.listdir(img_path_dir)
        img_time_dict = {i: "" for i in range(public_start_time, public_end_time + 1)}
        for img in all_imgs:
            try:
                img_time_dict[int(int(
                    img.replace(".jpg", "")) * 0.001)] = "/static/{0}/{1}/picture_log/{2}".format(host, task_name_int,
                                                                                                  img)
            except Exception as e:
                logger.error(e)
                traceback.print_exc()
                continue
        res_list = []
        for key, v in img_time_dict.items():
            try:
                res_list.append({"time": key, "picture_path": v,
                                 "relative_time": DataCollect.seconds_to_time(int(key) - public_start_time)})
            except Exception as e:
                logger.error(e)
        res_list.sort(key=lambda x: int(x.get("time")))
        return res_list

    @staticmethod
    def get_public_time(result_dict: dict):
        time_collect: list[list] = [list(map(lambda x: int(x), future_result[:, 0])) for monitor_name, future_result in
                                    result_dict.items()]  # 所有的时间[[], []]
        public_start_time, public_end_time = DataCollect.find_common_elements(time_collect)
        return public_start_time, public_end_time

    @staticmethod
    def find_common_elements(lists):

        min_time = None
        max_time = None
        for item_list in lists:
            if not min_time:
                min_time = item_list[0]
            if not max_time:
                max_time = item_list[-1]
            max_time = max(max_time, max(item_list))
            min_time = min(min_time, min(item_list))
        return min_time, max_time

    # 获取不同类型的数据，掐头去尾保证所有的数据起点终点一致
    @staticmethod
    def time_value_result(monitor_name, csv_data, start_time, end_time, **kwargs):
        real_time: list = csv_data[:, 0].tolist()
        value: list = np.round(csv_data[:, 1], 2).tolist()
        value_max = max(value)
        value_min = min(value)
        value_avg = round(sum(value) / len(value), 2) if value and len(value) else 0
        real_time_int: list = list(map(lambda x: int(x), real_time))
        head_lack_second = real_time_int[0] - start_time
        end_lack_second = end_time - real_time_int[-1]
        head_time = [real_time_int[0] + i for i in range(head_lack_second)]
        end_time = [real_time_int[-1] + i for i in range(end_lack_second)]
        head_time_value = ["-" for i in range(head_lack_second)]
        end_time_value = ["-" for i in range(end_lack_second)]
        res_dict = {"time": head_time + real_time + end_time, "value": head_time_value + value + end_time_value,
                    "max": value_max, "min": value_min, "avg": value_avg}
        if kwargs.get("is_need_relative_time", False):
            res_dict["relative_time"] = [DataCollect.seconds_to_time(item - start_time) for item in
                                         head_time + real_time_int + end_time]
        if monitor_name == "fps":
            try:
                res_dict["full_number"] = max(csv_data[:, 3])  # 满帧
                source_jank_number = csv_data[:, 4].tolist()
                source_big_jank_number = csv_data[:, 5].tolist()
                res_dict["jank_number_sum"] = sum(source_jank_number)
                res_dict["big_jank_number_sum"] = sum(source_big_jank_number)
                res_dict["all_jank_rate"] = round((sum(source_jank_number) + sum(source_big_jank_number)) / len(
                    res_dict["time"]) * 100, 2)
                res_dict["jank_number"] = head_time_value + source_jank_number + end_time_value  # 卡顿
                res_dict["big_jank_number"] = head_time_value + source_big_jank_number + end_time_value  # 强卡顿
                res_dict["ftimege100"] = head_time_value + csv_data[:, 6].tolist() + end_time_value  # 增量耗时
            except Exception as e:
                res_dict["full_number"] = 0
                res_dict["jank_number"] = []
                res_dict["big_jank_number"] = []
                res_dict["ftimege100"] = []
                res_dict["jank_number_sum"] = 0
                res_dict["big_jank_number_sum"] = 0
                res_dict["all_jank_rate"] = 0
                logger.error(e)
            # fps值需要去掉开头一个和最后一个
        elif monitor_name == "network":
            try:
                res_dict["realtime_downFlow"] = res_dict["value"]
                del res_dict["value"]
                del res_dict["max"]
                del res_dict["min"]
                del res_dict["avg"]
                res_dict["realtime_upFlow"] = head_time_value + np.round(csv_data[:, 2], 2).tolist() + end_time_value
                res_dict["sum_realtimeFlow"] = head_time_value + np.round(csv_data[:, 3], 2).tolist() + end_time_value
                res_dict["sum_accumFlow_sum"] = 0
                if csv_data.shape[1] > 4:
                    sum_accumFlow_np = np.round(csv_data[:, 6], 2)
                    res_dict["accumulate_downFlow"] = head_time_value + np.round(csv_data[:, 4],
                                                                                 2).tolist() + end_time_value
                    res_dict["accumulate_upFlow"] = head_time_value + np.round(csv_data[:, 5],
                                                                               2).tolist() + end_time_value
                    res_dict["sum_accumFlow"] = head_time_value + sum_accumFlow_np.tolist() + end_time_value

                    res_dict["sum_accumFlow_sum"] = "{} kB".format(sum_accumFlow_np[-1]) if sum_accumFlow_np[
                                                                                                -1] < 1024 else "{} M".format(
                        round(sum_accumFlow_np[-1] / 1024, 2))
            except:
                traceback.print_exc()
                res_dict["realtime_downFlow"] = res_dict["value"]
                res_dict["realtime_upFlow"] = []
                res_dict["sum_realtimeFlow"] = []
                res_dict["accumulate_downFlow"] = []
                res_dict["accumulate_upFlow"] = []
                res_dict["sum_accumFlow"] = []
        elif monitor_name == "cpu":
            try:
                proc_app_cpu = csv_data[:, 2].tolist()
                proc_sys_cpu = csv_data[:, 3].tolist()
                res_dict["proc_app_cpu_max"] = max(proc_app_cpu)
                res_dict["proc_sys_cpu_max"] = max(proc_sys_cpu)
                res_dict["proc_app_cpu_avg"] = round(sum(proc_app_cpu) / len(proc_app_cpu), 2)
                res_dict["proc_sys_cpu_avg"] = round(sum(proc_sys_cpu) / len(proc_sys_cpu), 2)
                proc_app_cpu = head_time_value + proc_app_cpu + end_time_value
                proc_sys_cpu = head_time_value + proc_sys_cpu + end_time_value
                res_dict["proc_app_cpu"] = proc_app_cpu
                res_dict["proc_sys_cpu"] = proc_sys_cpu
            except Exception as e:
                res_dict["proc_app_cpu"] = []
                res_dict["proc_sys_cpu"] = []
                res_dict["proc_app_cpu_max"] = 0
                res_dict["proc_sys_cpu_max"] = 0
                res_dict["proc_app_cpu_avg"] = 0
                res_dict["proc_sys_cpu_avg"] = 0
                logger.error(e)
            # fps值需要去掉开头一个和最后一个
        return res_dict

    @staticmethod
    def seconds_to_time(time_data_collect):
        minutes = str(time_data_collect // 60).zfill(2)
        seconds = str(time_data_collect % 60).zfill(2)
        return f"{minutes}:{seconds}"

    @classmethod
    def format_data(cls, perf_data, monitortypes):
        min_time = int(perf_data["public_start_time"])
        new_time = list(range(int(perf_data["public_start_time"]), int(perf_data["public_end_time"]) + 1))
        monitors = [key for key in list(perf_data.keys()) if key in monitortypes]
        for monitor in monitors:
            if monitor == "fps" and monitor in perf_data:
                existing_time = perf_data[monitor]['time']
                existing_value = perf_data[monitor]['value']
                existing_jank_number = perf_data[monitor]['jank_number']
                existing_big_jank_number = perf_data[monitor]['big_jank_number']
                existing_ftimege100 = perf_data[monitor]['ftimege100']
                new_value = ['-'] * len(new_time)
                new_jank_number = ['-'] * len(new_time)
                new_big_jank_number = ['-'] * len(new_time)
                new_ftimege100 = ['-'] * len(new_time)
                for i, t in enumerate(existing_time):
                    new_value[int(t) - int(min_time)] = existing_value[i]
                    if existing_jank_number:
                        new_jank_number[int(t) - int(min_time)] = existing_jank_number[i]
                    if existing_big_jank_number:
                        new_big_jank_number[int(t) - int(min_time)] = existing_big_jank_number[i]
                    if existing_ftimege100:
                        new_ftimege100[int(t) - int(min_time)] = existing_ftimege100[i]
                perf_data[monitor]['time'] = new_time
                perf_data[monitor]['value'] = new_value
                perf_data[monitor]['jank_number'] = new_jank_number
                perf_data[monitor]['big_jank_number'] = new_big_jank_number
                perf_data[monitor]['ftimege100'] = new_ftimege100
            elif monitor == "network" and monitor in perf_data:
                existing_time = perf_data[monitor]['time']
                existing_realtime_downFlow = perf_data[monitor]['realtime_downFlow']
                existing_realtime_upFlow = perf_data[monitor]['realtime_upFlow']
                existing_sum_realtimeFlow = perf_data[monitor]['sum_realtimeFlow']
                if "sum_accumFlow" in perf_data[monitor]:
                    existing_sum_accumFlow = perf_data[monitor]['sum_accumFlow']
                    existing_accumulate_upFlow = perf_data[monitor]['accumulate_upFlow']
                    existing_accumulate_downFlow = perf_data[monitor]['accumulate_downFlow']
                new_realtime_downFlow = ['-'] * len(new_time)
                new_realtime_upFlow = ['-'] * len(new_time)
                new_sum_realtimeFlow = ['-'] * len(new_time)
                if "sum_accumFlow" in perf_data[monitor]:
                    new_sum_accumFlow = ['-'] * len(new_time)
                    new_accumulate_upFlow = ['-'] * len(new_time)
                    new_accumulate_downFlow = ['-'] * len(new_time)
                for i, t in enumerate(existing_time):
                    if new_realtime_downFlow:
                        new_realtime_downFlow[int(t) - int(min_time)] = existing_realtime_downFlow[i]
                    if new_realtime_upFlow:
                        new_realtime_upFlow[int(t) - int(min_time)] = existing_realtime_upFlow[i]
                    if new_sum_realtimeFlow:
                        new_sum_realtimeFlow[int(t) - int(min_time)] = existing_sum_realtimeFlow[i]
                    if "sum_accumFlow" in perf_data[monitor]:
                        if new_sum_accumFlow:
                            new_sum_accumFlow[int(t) - int(min_time)] = existing_sum_accumFlow[i]
                        if new_accumulate_upFlow:
                            new_accumulate_upFlow[int(t) - int(min_time)] = existing_accumulate_upFlow[i]
                        if new_accumulate_downFlow:
                            new_accumulate_downFlow[int(t) - int(min_time)] = existing_accumulate_downFlow[i]
                perf_data[monitor]['time'] = new_time
                perf_data[monitor]['realtime_downFlow'] = new_realtime_downFlow
                perf_data[monitor]['realtime_upFlow'] = new_realtime_upFlow
                perf_data[monitor]['sum_realtimeFlow'] = new_sum_realtimeFlow
                perf_data[monitor]['sum_accumFlow'] = new_sum_accumFlow
                perf_data[monitor]['accumulate_downFlow'] = new_accumulate_downFlow
                perf_data[monitor]['accumulate_upFlow'] = new_accumulate_upFlow

            elif monitor == "cpu" and monitor in perf_data and "proc_app_cpu" in perf_data["cpu"]:
                existing_time = perf_data[monitor]['time']
                existing_value = perf_data[monitor]['value']
                existing_proc_cpu = perf_data[monitor]['proc_app_cpu']
                existing_proc_sys_cpu = perf_data[monitor]['proc_sys_cpu']
                new_value = ['-'] * len(new_time)
                new_proc_cpu = ['-'] * len(new_time)
                new_proc_sys_cpu = ['-'] * len(new_time)
                for i, t in enumerate(existing_time):
                    new_value[int(t) - int(min_time)] = existing_value[i]
                    if existing_proc_cpu:
                        new_proc_cpu[int(t) - int(min_time)] = existing_proc_cpu[i]
                    if existing_proc_sys_cpu:
                        new_proc_sys_cpu[int(t) - int(min_time)] = existing_proc_sys_cpu[i]
                perf_data[monitor]['time'] = new_time
                perf_data[monitor]['value'] = new_value
                if existing_proc_cpu:
                    perf_data[monitor]['proc_app_cpu'] = new_proc_cpu
                if existing_proc_sys_cpu:
                    perf_data[monitor]['proc_sys_cpu'] = new_proc_sys_cpu
            else:
                if monitor in perf_data:
                    existing_time = perf_data[monitor]['time']
                    existing_value = perf_data[monitor]['value']
                    new_value = ['-'] * len(new_time)
                    for i, t in enumerate(existing_time):
                        new_value[int(t) - int(min_time)] = existing_value[i]
                    perf_data[monitor]['time'] = new_time
                    perf_data[monitor]['value'] = new_value
            try:
                perf_data[monitor]["relative_time"] = [DataCollect.seconds_to_time(i - perf_data[monitor]['time'][0])
                                                       for i in perf_data[monitor]['time']]
            except Exception as e:
                logger.error(e)
                traceback.print_exc()
                perf_data[monitor]["relative_time"] = []
        return perf_data


class ResultDataUtil(object):

    @classmethod
    def get_path_file(cls, save_dir):
        save_dir = Path(save_dir)
        return [c_file for c_file in save_dir.iterdir() if c_file.is_file() and c_file.suffix == ".csv"]

    @classmethod
    async def get_csv2multi_list(cls, csv_path):
        # 读取CSV文件
        data = await asyncio.to_thread(np.genfromtxt, csv_path, delimiter=',', dtype=str, skip_header=1,
                                       filling_values=0, encoding="utf-8")
        # 读取第一行作为标题（键）
        with open(csv_path, 'r', encoding="utf-8") as file:
            header = next(file).strip().split(',')
            # 创建字典，将标题作为键，数据列作为值
        result_dict = {header[i]: data[:, i].tolist() for i in range(data.shape[1])}
        return result_dict

    @classmethod
    async def get_all_task_data(cls, save_dir):
        print(cls.get_path_file(save_dir))
        all_data = await asyncio.gather(*[cls.get_csv2multi_list(file.resolve()) for file in cls.get_path_file(save_dir)])
        print(all_data)


if __name__ == '__main__':
    res = asyncio.run(ResultDataUtil.get_all_task_data(
        r"E:\服务器上传代码\client-perf-tools\performancetest\web\test_result\1709475382"))

    # print(json.dumps(res))
