# coding=utf-8
import io
import json
import threading
import os
import time
import csv
import logging
import sys
import traceback

import requests

sys.path.append("windows_perf_tool")
from core.monitor import Monitor
import sys

sys.path.append("windows_perf_tool")
from global_data import GlobalData as G

logger = logging.getLogger(__file__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')


class PcPerf(Monitor):

    def __init__(self, save_dir, test_time=-1, interval=1):
        self.save_dir = save_dir
        self.test_time = test_time
        self._stop_event = threading.Event()
        self.interval = interval
        self.frametime_berfore_time = None
        self.before_frame_time_data = None
        self.pc_perf_collect = [
            threading.Thread(target=self._collect_package_pc_perf_cpu_thread, args=(test_time,)),
            threading.Thread(target=self._collect_package_pc_perf_cpu_core_thread, args=(test_time,)),
            threading.Thread(target=self._collect_package_pc_perf_memory_thread, args=(test_time,)),
            threading.Thread(target=self._collect_package_pc_perf_network_thread, args=(test_time,)),
            threading.Thread(target=self._collect_package_pc_perf_gpu_thread, args=(test_time,)),
            threading.Thread(target=self._collect_package_pc_FPS_thread, args=(test_time,)),
            threading.Thread(target=self._collect_package_thread_num_perf_thread, args=(test_time,)),
            threading.Thread(target=self._collect_package_handle_num_perf_thread, args=(test_time,)),
            threading.Thread(target=self._collect_package_io_perf_thread, args=(test_time,)),
        ]


    def start(self):
        for th in self.pc_perf_collect:
            th.start()

    def stop(self):
        self._stop_event.set()
        time.sleep(1.5)
        logger.info("stop pc perf")
        self.stop_fps()

    def get_cpu(self):
        try:
            res = requests.get(G.pc_sdk_client.format(G.device.device_addr[0]) + "/cpu",
                               params={"pid": G.device.pid})
            cpu_res: dict = json.loads(res.text)
            return cpu_res.get("time", time.time()), cpu_res.get("cpu_usage", 0), cpu_res.get("cpu_core_usage", [])
        except:
            traceback.print_exc()
            return time.time(), 0, 0

    def get_cpu_core(self):
        try:
            res = requests.get(G.pc_sdk_client.format(G.device.device_addr[0]) + "/cpu_core",
                               params={"pid": G.device.pid})
            cpu_res: dict = json.loads(res.text)
            return cpu_res.get("time", time.time()), cpu_res.get("cpu_core_num", 0), cpu_res.get("cpu_core_usage", [])
        except:
            traceback.print_exc()
            return time.time(), 0, 0

    def get_memory(self):
        try:
            res = requests.get(G.pc_sdk_client.format(G.device.device_addr[0]) + "/memory",
                               params={"pid": G.device.pid})
            memory_res: dict = json.loads(res.text)
            return memory_res.get("time", time.time()), memory_res.get("process_memory_info", 0), memory_res.get("total_memory", 0), memory_res.get(
                "percentage_used", 0)
        except:
            traceback.print_exc()
            return time.time(), 0, 0, 0

    def get_io(self):
        try:
            res = requests.get(G.pc_sdk_client.format(G.device.device_addr[0]) + "/io",
                               params={"pid": G.device.pid})
            io_res: dict = json.loads(res.text)
            return io_res.get("time", time.time()), io_res.get("disk_read_mb", 0), io_res.get("disk_write_mb", 0)
        except:
            traceback.print_exc()
            return time.time(), 0, 0

    def get_thread_num(self):
        try:
            res = requests.get(G.pc_sdk_client.format(G.device.device_addr[0]) + "/thread_num",
                               params={"pid": G.device.pid})
            io_res: dict = json.loads(res.text)
            return io_res.get("time", time.time()), io_res.get("process_num_thread", 0)
        except:
            traceback.print_exc()
            return time.time(), 0, 0

    def get_handle_num(self):
        try:
            res = requests.get(G.pc_sdk_client.format(G.device.device_addr[0]) + "/handle_num",
                               params={"pid": G.device.pid})
            io_res: dict = json.loads(res.text)
            return io_res.get("time", time.time()), io_res.get("process_num_handle", 0)
        except:
            traceback.print_exc()
            return time.time(), 0, 0


    def get_network(self):
        try:
            res = requests.get(G.pc_sdk_client.format(G.device.device_addr[0]) + "/network")
            network_res: dict = json.loads(res.text)
            return network_res.get("time", time.time()), network_res.get("recv_mb", 0), network_res.get("send_mb", 0)
        except:
            traceback.print_exc()
            return time.time(), 0, 0

    def get_gpu(self):
        try:
            res = requests.get(G.pc_sdk_client.format(G.device.device_addr[0]) + "/gpu", params={"pid": G.device.pid})
            gpu_res: dict = json.loads(res.text)
            return gpu_res.get("time", time.time()), gpu_res.get("gpu_used", 0)
        except:
            traceback.print_exc()
            return time.time(), 0, 0

    def get_fps(self):
        try:
            res = requests.get(G.pc_sdk_client.format(G.device.device_addr[0]) + "/fps", params={"pid": G.device.pid})
            fps_res: dict = json.loads(res.text)
            if fps_res.get("cur_collect_start_time") and not ParsFPSInfo.PHONE_REAL_TIME_INTERVAL:
                ParsFPSInfo.PHONE_REAL_TIME_INTERVAL = fps_res.get("cur_collect_start_time")
            return fps_res.get("frametime", [])
        except:
            traceback.print_exc()
            return []

    def stop_fps(self):
        try:
            logger.info("join stop pc fps")
            res = requests.get(G.pc_sdk_client.format(G.device.device_addr[0]) + "/stopfps", params={"pid": G.device.pid})
            stop_fps_res: dict = json.loads(res.text)
            logger.info(stop_fps_res)
            return stop_fps_res.get("stop")
        except:
            traceback.print_exc()
            return []


    def _collect_package_pc_perf_cpu_thread(self, test_time):
        '''
        按照指定频率，循环搜集pc 性能的信息 cpu
        :return:
        '''
        end_time = time.time() + float(self.test_time)
        saver_dir = self.save_dir
        cur_time, cpu_core_num, cpu_core = self.get_cpu_core()
        property_all = {
            "cpu": (os.path.join(saver_dir, "cpu.csv"), ["timestamp", "cpu%"]),
            # "cpu_core": (os.path.join(saver_dir, "cpu_core.csv"), ["timestamp"]),
            # "memory": (os.path.join(saver_dir, "memory.csv"), ["timestamp", "memory"]),
            # "fps": (os.path.join(saver_dir, "fps.csv"),
            #         ["timestamp", "FPS", "lag_number", "FPS_full_number", "jank_number", "big_jank_number"]),
            # "gpu": (os.path.join(saver_dir, "gpu.csv"), ["timestamp", "gpu%"]),
            # "devicebattery": (os.path.join(saver_dir, "devicebattery.csv"),
            #                   ["timestamp", "devicetemperature", "devicebatterylevel", "charge"])
            # "network": (os.path.join(self.save_dir, "network.csv"), ["timestamp", "downFlow", "upFlow", "sumFlow"]),
        }
        # property_all.get("cpu_core")[1].extend(["cpu{0}".format(i) for i in range(len(cpu_core))])
        for k, v in property_all.items():
            with open(v[0], 'w+') as df:
                csv.writer(df, lineterminator='\n').writerow(v[1])
        G.monitor_pause.wait()
        while not self._stop_event.is_set() and not G.stop_event.is_set():
            try:
                logging.debug("---------------开始获取性能信息" + str(
                    threading.current_thread().name))
                before_time = time.time()
                cur_time, cpu_avg, cpu_core = self.get_cpu()  # 可超时的任务
                logging.info("---pc perf 获取到数据 cpu {0}{1}".format(cpu_avg, cpu_core))
                # cur_time_core, cpu_core_num, cpu_core = self.get_cpu_core()
                file_path = property_all.get("cpu", None)
                # file_path_core = property_all.get("cpu_core", None)
                if not file_path:
                    continue
                # if not file_path_core:
                #     continue
                write_info = []
                write_info.append(cur_time)
                write_info.append(cpu_avg)
                # write_info_core = []
                # write_info_core.append(cur_time_core)
                # write_info_core.extend(cpu_core)
                if G.monitor_pause.is_set():
                    with open(file_path[0], 'a+', encoding="utf-8") as df:
                        logging.info("write {0}".format(write_info))
                        csv.writer(df, lineterminator='\n').writerow(write_info)
                        del write_info[:]
                    # with open(file_path_core[0], 'a+', encoding="utf-8") as df:
                    #     logging.info("write {0}".format(write_info_core))
                    #     csv.writer(df, lineterminator='\n').writerow(write_info_core)
                    #     del write_info_core[:]
                after = time.time()
                time_consume = after - before_time
                delta_inter = self.interval - time_consume
                if delta_inter > 0:
                    time.sleep(delta_inter)
            except Exception as e:
                logging.error("an exception hanpend in ios perf thread , reason unkown!, e: pcperf cpu")
                logging.error(e)
                logging.error(traceback.format_exc())
                time.sleep(0.2)
            logging.error("not self._stop_event.is_set(): {0}  not G.stop_event.is_set(): {1} cpu".format(
                not self._stop_event.is_set(), not G.stop_event.is_set()))
        logging.debug("stop event is set or timeout pcperf")

    def _collect_package_pc_perf_cpu_core_thread(self, test_time):
        '''
        按照指定频率，循环搜集pc 性能的信息 cpu
        :return:
        '''
        end_time = time.time() + float(self.test_time)
        saver_dir = self.save_dir
        cur_time, cpu_core_num, cpu_core = self.get_cpu_core()
        property_all = {
            # "cpu": (os.path.join(saver_dir, "cpu.csv"), ["timestamp", "cpu%"]),
            "cpu_core": (os.path.join(saver_dir, "cpu_core.csv"), ["timestamp"]),
            # "memory": (os.path.join(saver_dir, "memory.csv"), ["timestamp", "memory"]),
            # "fps": (os.path.join(saver_dir, "fps.csv"),
            #         ["timestamp", "FPS", "lag_number", "FPS_full_number", "jank_number", "big_jank_number"]),
            # "gpu": (os.path.join(saver_dir, "gpu.csv"), ["timestamp", "gpu%"]),
            # "devicebattery": (os.path.join(saver_dir, "devicebattery.csv"),
            #                   ["timestamp", "devicetemperature", "devicebatterylevel", "charge"])
            # "network": (os.path.join(self.save_dir, "network.csv"), ["timestamp", "downFlow", "upFlow", "sumFlow"]),
        }
        property_all.get("cpu_core")[1].extend(["cpu{0}".format(i) for i in range(len(cpu_core))])
        for k, v in property_all.items():
            with open(v[0], 'w+') as df:
                csv.writer(df, lineterminator='\n').writerow(v[1])
        G.monitor_pause.wait()
        while not self._stop_event.is_set() and not G.stop_event.is_set():
            try:
                logging.debug("---------------开始获取性能信息" + str(
                    threading.current_thread().name))
                before_time = time.time()
                # cur_time, cpu_avg, cpu_core = self.get_cpu()  # 可超时的任务
                # logging.info("---pc perf 获取到数据 cpu {0}{1}".format(cpu_avg, cpu_core))
                cur_time_core, cpu_core_num, cpu_core = self.get_cpu_core()
                # file_path = property_all.get("cpu", None)
                file_path_core = property_all.get("cpu_core", None)
                # if not file_path:
                #     continue
                if not file_path_core:
                    continue
                # write_info = []
                # write_info.append(cur_time)
                # write_info.append(cpu_avg)
                write_info_core = []
                write_info_core.append(cur_time_core)
                write_info_core.extend(cpu_core)
                if G.monitor_pause.is_set():
                    # with open(file_path[0], 'a+', encoding="utf-8") as df:
                    #     logging.info("write {0}".format(write_info))
                    #     csv.writer(df, lineterminator='\n').writerow(write_info)
                    #     del write_info[:]
                    with open(file_path_core[0], 'a+', encoding="utf-8") as df:
                        logging.info("write {0}".format(write_info_core))
                        csv.writer(df, lineterminator='\n').writerow(write_info_core)
                        del write_info_core[:]
                after = time.time()
                time_consume = after - before_time
                delta_inter = self.interval - time_consume
                if delta_inter > 0:
                    time.sleep(delta_inter)
            except Exception as e:
                logging.error("an exception hanpend in cpu core perf thread , reason unkown!, e: pcperf cpu")
                logging.error(e)
                logging.error(traceback.format_exc())
                time.sleep(0.2)
            logging.error("not self._stop_event.is_set(): {0}  not G.stop_event.is_set(): {1} cpu".format(
                not self._stop_event.is_set(), not G.stop_event.is_set()))
        logging.debug("stop event is set or timeout pcperf")

    def _collect_package_pc_perf_memory_thread(self, test_time):
        '''
        按照指定频率，循环搜集pc 性能的信息 memory
        :return:
        '''
        end_time = time.time() + float(self.test_time)
        saver_dir = self.save_dir
        property_all = {
            # "cpu": (os.path.join(saver_dir, "cpu.csv"), ["timestamp", "cpu%"]),
            "memory": (os.path.join(saver_dir, "memory.csv"), ["timestamp", "memory"]),
            # "fps": (os.path.join(saver_dir, "fps.csv"),
            #         ["timestamp", "FPS", "lag_number", "FPS_full_number", "jank_number", "big_jank_number"]),
            # "gpu": (os.path.join(saver_dir, "gpu.csv"), ["timestamp", "gpu%"]),
            # "devicebattery": (os.path.join(saver_dir, "devicebattery.csv"),
            #                   ["timestamp", "devicetemperature", "devicebatterylevel", "charge"])
        }
        for k, v in property_all.items():
            with open(v[0], 'w+') as df:
                csv.writer(df, lineterminator='\n').writerow(v[1])
        G.monitor_pause.wait()
        while not self._stop_event.is_set() and not G.stop_event.is_set():
            try:
                logging.debug("---------------开始获取性能信息" + str(
                    threading.current_thread().name))
                before_time = time.time()
                cur_time, process_memory_info, total_memory, percentage_used = self.get_memory()  # 可超时的任务
                logging.info("---pcperf 获取到数据 {0}".format((cur_time, process_memory_info, total_memory, percentage_used)))
                file_path = property_all.get("memory")
                if not file_path:
                    continue
                write_info = []
                write_info.append(cur_time)
                write_info.append(process_memory_info)
                if G.monitor_pause.is_set():
                    with open(file_path[0], 'a+', encoding="utf-8") as df:
                        logging.info("write {0}".format(write_info))
                        csv.writer(df, lineterminator='\n').writerow(write_info)
                        del write_info[:]
                after = time.time()
                time_consume = after - before_time
                delta_inter = self.interval - time_consume
                if delta_inter > 0:
                    time.sleep(delta_inter)
            except Exception as e:
                logging.error("an exception hanpend in ios perf thread , reason unkown!, e: pcperf cpu")
                logging.error(e)
                logging.error(traceback.format_exc())
                time.sleep(0.2)
            logging.error("not self._stop_event.is_set(): {0}  not G.stop_event.is_set(): {1} cpu".format(
                not self._stop_event.is_set(), not G.stop_event.is_set()))
        logging.debug("stop event is set or timeout pcperf")

    def _collect_package_pc_perf_network_thread(self, test_time):
        '''
         按照指定频率，循环搜集pc 性能的信息 cpu
         :return:
         '''
        property_all = {
            # "cpu": (os.path.join(saver_dir, "cpu.csv"), ["timestamp", "cpu%"]),
            # "memory": (os.path.join(saver_dir, "memory.csv"), ["timestamp", "memory"]),
            # "fps": (os.path.join(saver_dir, "fps.csv"),
            #         ["timestamp", "FPS", "lag_number", "FPS_full_number", "jank_number", "big_jank_number"]),
            # "gpu": (os.path.join(saver_dir, "gpu.csv"), ["timestamp", "gpu%"]),
            # "devicebattery": (os.path.join(saver_dir, "devicebattery.csv"),
            #                   ["timestamp", "devicetemperature", "devicebatterylevel", "charge"])
            "network": (os.path.join(self.save_dir, "network.csv"), ["timestamp",
                                                                     "realtime_downFlow", "realtime_upFlow",
                                                                     "sum_realtimeFlow",
                                                                     "accumulate_downFlow", "accumulate_upFlow",
                                                                     "sum_accumFlow", ]),
        }
        for k, v in property_all.items():
            with open(v[0], 'w+') as df:
                csv.writer(df, lineterminator='\n').writerow(v[1])
        G.monitor_pause.wait()
        base_recv_value = 0
        base_send_value = 0
        before_recv_value = 0
        before_send_value = 0
        while not self._stop_event.is_set() and not G.stop_event.is_set():
            try:
                logging.debug("---------------开始获取性能信息" + str(
                    threading.current_thread().name))
                before_time = time.time()
                cur_time, recv_data, send_data = self.get_network()
                if not base_send_value:
                    base_send_value = send_data
                if not base_recv_value:
                    base_recv_value = recv_data
                if not before_recv_value:
                    before_recv_value = recv_data
                if not before_send_value:
                    before_send_value = send_data
                #实时流量
                realtime_downFlow = recv_data - before_recv_value
                realtime_upFlow = send_data - before_send_value
                sum_realtimeFlow = realtime_downFlow + realtime_upFlow
                #累计流量
                accumulate_downFlow = recv_data - base_recv_value
                accumulate_upFlow = send_data - base_send_value
                sum_accumFlow = accumulate_downFlow + accumulate_upFlow
                before_recv_value = recv_data
                before_send_value = send_data
                write_info = [cur_time, realtime_downFlow, realtime_upFlow, sum_realtimeFlow, accumulate_downFlow, accumulate_upFlow, sum_accumFlow]
                file_path = property_all.get("network")
                if G.monitor_pause.is_set():
                    with open(file_path[0], 'a+', encoding="utf-8") as df:
                        logging.info("write {0}".format(write_info))
                        csv.writer(df, lineterminator='\n').writerow(write_info)
                        del write_info[:]
                if time.time() - before_time < self.interval:
                    time.sleep(self.interval - (time.time() - before_time))
            except Exception as e:
                logging.error("an exception hanpend in ios perf thread , reason unkown!, e: pcperf cpu")
                logging.error(e)
                logging.error(traceback.format_exc())
            logging.error("not self._stop_event.is_set(): {0}  not G.stop_event.is_set(): {1} cpu".format(
                not self._stop_event.is_set(), not G.stop_event.is_set()))
        logging.debug("stop event is set or timeout pcperf")


    def _collect_package_pc_perf_gpu_thread(self, test_time):
        '''
        按照指定频率，循环搜集pc 性能的信息 gpu
        :return:
        '''
        end_time = time.time() + float(self.test_time)
        saver_dir = self.save_dir
        property_all = {
            # "cpu": (os.path.join(saver_dir, "cpu.csv"), ["timestamp", "cpu%"]),
            # "memory": (os.path.join(saver_dir, "memory.csv"), ["timestamp", "memory"]),
            # "fps": (os.path.join(saver_dir, "fps.csv"),
            #         ["timestamp", "FPS", "lag_number", "FPS_full_number", "jank_number", "big_jank_number"]),
            "gpu": (os.path.join(saver_dir, "gpu.csv"), ["timestamp", "gpu%"]),
            # "devicebattery": (os.path.join(saver_dir, "devicebattery.csv"),
            #                   ["timestamp", "devicetemperature", "devicebatterylevel", "charge"])
            # "network": (os.path.join(self.save_dir, "network.csv"), ["timestamp", "downFlow", "upFlow", "sumFlow"]),
        }
        for k, v in property_all.items():
            with open(v[0], 'w+') as df:
                csv.writer(df, lineterminator='\n').writerow(v[1])
        G.monitor_pause.wait()
        while not self._stop_event.is_set() and not G.stop_event.is_set():
            try:
                logging.debug("---------------开始获取性能信息" + str(
                    threading.current_thread().name))
                before_time = time.time()
                cur_time, gpu_used = self.get_gpu()  # 可超时的任务
                logging.info("---pc perf 获取到数据 gpu_used {0}".format(gpu_used))
                file_path = property_all.get("gpu", None)
                if not file_path:
                    continue
                write_info = []
                write_info.append(cur_time)
                write_info.append(gpu_used)
                if G.monitor_pause.is_set():
                    with open(file_path[0], 'a+', encoding="utf-8") as df:
                        logging.info("write {0}".format(write_info))
                        csv.writer(df, lineterminator='\n').writerow(write_info)
                        del write_info[:]
                after = time.time()
                time_consume = after - before_time
                delta_inter = self.interval - time_consume
                if delta_inter > 0:
                    time.sleep(delta_inter)
            except Exception as e:
                logging.error("an exception hanpend in ios perf thread , reason unkown!, e: pcperf cpu")
                logging.error(e)
                logging.error(traceback.format_exc())
                time.sleep(0.2)
            logging.error("not self._stop_event.is_set(): {0}  not G.stop_event.is_set(): {1} cpu".format(
                not self._stop_event.is_set(), not G.stop_event.is_set()))
        logging.debug("stop event is set or timeout pcperf")

    def _collect_package_io_perf_thread(self, test_time):
        '''
        按照指定频率，循环搜集pc 性能的信息 gpu
        :return:
        '''
        end_time = time.time() + float(self.test_time)
        saver_dir = self.save_dir
        property_all = {
            # "cpu": (os.path.join(saver_dir, "cpu.csv"), ["timestamp", "cpu%"]),
            # "memory": (os.path.join(saver_dir, "memory.csv"), ["timestamp", "memory"]),
            # "fps": (os.path.join(saver_dir, "fps.csv"),
            #         ["timestamp", "FPS", "lag_number", "FPS_full_number", "jank_number", "big_jank_number"]),
            # "gpu": (os.path.join(saver_dir, "gpu.csv"), ["timestamp", "gpu%"]),
            # "devicebattery": (os.path.join(saver_dir, "devicebattery.csv"),
            #                   ["timestamp", "devicetemperature", "devicebatterylevel", "charge"])
            # "network": (os.path.join(self.save_dir, "network.csv"), ["timestamp", "downFlow", "upFlow", "sumFlow"]),
            "io": (os.path.join(saver_dir, "io.csv"), ["timestamp", "disk_read_mb", "disk_write_mb"])
        }
        for k, v in property_all.items():
            with open(v[0], 'w+') as df:
                csv.writer(df, lineterminator='\n').writerow(v[1])
        G.monitor_pause.wait()
        while not self._stop_event.is_set() and not G.stop_event.is_set():
            try:
                logging.debug("---------------开始获取性能信息" + str(
                    threading.current_thread().name))
                before_time = time.time()
                cur_time, disk_read_mb, disk_write_mb = self.get_io()  # 可超时的任务
                logging.info("---pc perf 获取到数据 io_used read {0} write {1}".format(disk_read_mb, disk_write_mb))
                file_path = property_all.get("io", None)
                if not file_path:
                    continue
                write_info = []
                write_info.append(cur_time)
                write_info.append(disk_read_mb)
                write_info.append(disk_write_mb)
                if G.monitor_pause.is_set():
                    with open(file_path[0], 'a+', encoding="utf-8") as df:
                        logging.info("write {0}".format(write_info))
                        csv.writer(df, lineterminator='\n').writerow(write_info)
                        del write_info[:]
                after = time.time()
                time_consume = after - before_time
                delta_inter = self.interval - time_consume
                if delta_inter > 0:
                    time.sleep(delta_inter)
            except Exception as e:
                logging.error("an exception hanpend in ios perf thread , reason unkown!, e: pcperf io")
                logging.error(e)
                logging.error(traceback.format_exc())
                time.sleep(0.2)
            logging.error("not self._stop_event.is_set(): {0}  not G.stop_event.is_set(): {1} io".format(
                not self._stop_event.is_set(), not G.stop_event.is_set()))
        logging.debug("stop event is set or timeout pcperf")

    def _collect_package_thread_num_perf_thread(self, test_time):
        '''
        按照指定频率，循环搜集pc 性能的信息 gpu
        :return:
        '''
        end_time = time.time() + float(self.test_time)
        saver_dir = self.save_dir
        property_all = {
            # "cpu": (os.path.join(saver_dir, "cpu.csv"), ["timestamp", "cpu%"]),
            # "memory": (os.path.join(saver_dir, "memory.csv"), ["timestamp", "memory"]),
            # "fps": (os.path.join(saver_dir, "fps.csv"),
            #         ["timestamp", "FPS", "lag_number", "FPS_full_number", "jank_number", "big_jank_number"]),
            # "gpu": (os.path.join(saver_dir, "gpu.csv"), ["timestamp", "gpu%"]),
            # "devicebattery": (os.path.join(saver_dir, "devicebattery.csv"),
            #                   ["timestamp", "devicetemperature", "devicebatterylevel", "charge"])
            # "network": (os.path.join(self.save_dir, "network.csv"), ["timestamp", "downFlow", "upFlow", "sumFlow"]),
            # "io": (os.path.join(saver_dir, "io.csv"), ["timestamp", "disk_read_mb", "disk_write_mb"])
            "thread_num": (os.path.join(saver_dir, "thread_num.csv"), ["timestamp", "process_num_thread"])
        }
        for k, v in property_all.items():
            with open(v[0], 'w+') as df:
                csv.writer(df, lineterminator='\n').writerow(v[1])
        G.monitor_pause.wait()
        while not self._stop_event.is_set() and not G.stop_event.is_set():
            try:
                logging.debug("---------------开始获取性能信息" + str(
                    threading.current_thread().name))
                before_time = time.time()
                cur_time, process_num_thread = self.get_thread_num()  # 可超时的任务
                logging.info("---pc perf 获取到数据 thread {0}".format(process_num_thread))
                file_path = property_all.get("thread_num", None)
                if not file_path:
                    continue
                write_info = []
                write_info.append(cur_time)
                write_info.append(process_num_thread)
                if G.monitor_pause.is_set():
                    with open(file_path[0], 'a+', encoding="utf-8") as df:
                        logging.info("write {0}".format(write_info))
                        csv.writer(df, lineterminator='\n').writerow(write_info)
                        del write_info[:]
                after = time.time()
                time_consume = after - before_time
                delta_inter = self.interval - time_consume
                if delta_inter > 0:
                    time.sleep(delta_inter)
            except Exception as e:
                logging.error("an exception hanpend in ios perf thread , reason unkown!, e: pcperf process thread num")
                logging.error(e)
                logging.error(traceback.format_exc())
                time.sleep(0.2)
            logging.error("not self._stop_event.is_set(): {0}  not G.stop_event.is_set(): {1} io".format(
                not self._stop_event.is_set(), not G.stop_event.is_set()))
        logging.debug("stop event is set or timeout pcperf")

    def _collect_package_handle_num_perf_thread(self, test_time):
        '''
        按照指定频率，循环搜集pc 性能的信息 gpu
        :return:
        '''
        end_time = time.time() + float(self.test_time)
        saver_dir = self.save_dir
        property_all = {
            # "cpu": (os.path.join(saver_dir, "cpu.csv"), ["timestamp", "cpu%"]),
            # "memory": (os.path.join(saver_dir, "memory.csv"), ["timestamp", "memory"]),
            # "fps": (os.path.join(saver_dir, "fps.csv"),
            #         ["timestamp", "FPS", "lag_number", "FPS_full_number", "jank_number", "big_jank_number"]),
            # "gpu": (os.path.join(saver_dir, "gpu.csv"), ["timestamp", "gpu%"]),
            # "devicebattery": (os.path.join(saver_dir, "devicebattery.csv"),
            #                   ["timestamp", "devicetemperature", "devicebatterylevel", "charge"])
            # "network": (os.path.join(self.save_dir, "network.csv"), ["timestamp", "downFlow", "upFlow", "sumFlow"]),
            # "io": (os.path.join(saver_dir, "io.csv"), ["timestamp", "disk_read_mb", "disk_write_mb"])
            # "thread_num": (os.path.join(saver_dir, "thread_num.csv"), ["timestamp", "process_num_thread"])
            "handle_num": (os.path.join(saver_dir, "handle_num.csv"), ["timestamp", "process_num_handle"])
        }
        for k, v in property_all.items():
            with open(v[0], 'w+') as df:
                csv.writer(df, lineterminator='\n').writerow(v[1])
        G.monitor_pause.wait()
        while not self._stop_event.is_set() and not G.stop_event.is_set():
            try:
                logging.debug("---------------开始获取性能信息" + str(
                    threading.current_thread().name))
                before_time = time.time()
                cur_time, process_num_handle = self.get_handle_num()  # 可超时的任务
                logging.info("---pc perf 获取到数据 handle {0} h".format(process_num_handle))
                file_path = property_all.get("handle_num", None)
                if not file_path:
                    continue
                write_info = []
                write_info.append(cur_time)
                write_info.append(process_num_handle)
                if G.monitor_pause.is_set():
                    with open(file_path[0], 'a+', encoding="utf-8") as df:
                        logging.info("write {0}".format(write_info))
                        csv.writer(df, lineterminator='\n').writerow(write_info)
                        del write_info[:]
                after = time.time()
                time_consume = after - before_time
                delta_inter = self.interval - time_consume
                if delta_inter > 0:
                    time.sleep(delta_inter)
            except Exception as e:
                logging.error("an exception hanpend in ios perf thread , reason unkown!, e: pcperf process thread num")
                logging.error(e)
                logging.error(traceback.format_exc())
                time.sleep(0.2)
            logging.error("not self._stop_event.is_set(): {0}  not G.stop_event.is_set(): {1} io".format(
                not self._stop_event.is_set(), not G.stop_event.is_set()))
        logging.debug("stop event is set or timeout pcperf")

    def get_FPS_info(self):
        pars_FPS_info = ParsFPSInfo(self.get_fps())
        self.FPS_info = pars_FPS_info
        return pars_FPS_info.FPS, pars_FPS_info.lag_number, pars_FPS_info.full_FPS_number,

    def _collect_package_pc_FPS_thread(self, test_time):
        '''
        按照指定频率，循环搜集FPS的信息
        '''
        saver_dir = self.save_dir
        property_all = {
            "fps": (os.path.join(saver_dir, "fps.csv"),
                    ["timestamp", "FPS", "lag_number", "FPS_full_number", "jank_number", "big_jank_number"]),
            "frametime": (os.path.join(saver_dir, "frametime.csv"),
                    [["timestamp", "interval_time", "relative_time"]]),
         }
        for k, v in property_all.items():
            with open(v[0], 'w+') as df:
                csv.writer(df, lineterminator='\n').writerow(v[1])
        G.monitor_pause.wait()
        ParsFPSInfo.start_collect_time = int(time.time())
        while not self._stop_event.is_set() and not G.stop_event.is_set():
            FPS_list = []
            try:
                logging.debug("---------------开始获取pcfps信息, into _collect_package_FPS_thread loop thread is : " + str(
                    threading.current_thread().name))
                before = time.time()
                try:
                    FPS_info_FPS, FPS_info_lag_number, FPS_full_number = self.get_FPS_info()
                except Exception as e:
                    logger.info(e)
                    traceback.print_exc()
                    FPS_info_FPS, FPS_info_lag_number, FPS_full_number = None, None, None
                logging.info(
                    "fps collect result {0} {1} {2}".format(FPS_info_FPS, FPS_info_lag_number, FPS_full_number))
                after = time.time()
                time_consume = after - before
                if not FPS_info_FPS:
                    delta_inter = self.interval - time_consume
                    if delta_inter > 0:
                        time.sleep(delta_inter)
                    continue
                logging.debug("  ============== time consume for fps info : " + str(time_consume))
                for front_index, (time_item, item_value_list) in enumerate(FPS_info_FPS.items()):
                    if not self.frametime_berfore_time:
                        self.frametime_berfore_time = int(time_item)
                        logger.info("初始化 berfor")
                    else:
                        if int(time_item) - self.frametime_berfore_time > 1:
                            for i in range(int(self.frametime_berfore_time + 1), int(time_item)):
                                with open(property_all.get("fps")[0], 'a+', encoding="utf-8") as df:
                                    csv.writer(df, lineterminator='\n').writerow([i, 0, 0, 0, 0, 0, 0])
                                with open(property_all.get("frametime")[0], "a+", encoding="utf-8") as df:
                                    csv.writer(df, lineterminator='\n').writerow([i, "", ""])
                                self.before_frame_time_data = None
                        self.frametime_berfore_time = int(time_item)
                    FPS_list.append(time_item)
                    FPS_list.append(len(item_value_list) if len(item_value_list) < FPS_full_number else FPS_full_number)
                    FPS_list.append(1 if len(item_value_list) < 24 else 0)
                    FPS_list.append(FPS_full_number)

                    try:
                        FPS_list.append(
                            self.FPS_info.jank_number[front_index] if len(
                                self.FPS_info.jank_number) > front_index else 0)
                    except Exception as e:
                        FPS_list.append(0)
                        logger.info(e)
                    try:
                        FPS_list.append(self.FPS_info.big_jank_number[front_index] if len(
                            self.FPS_info.big_jank_number) > front_index else 0)
                    except Exception as e:
                        FPS_list.append(0)
                        logger.info(e)
                    try:
                        FPS_list.append(ParsFPSInfo.FTIMEGE100)
                    except Exception as e:
                        FPS_list.append(0)
                        logger.info(e)
                    # ----------------------------frametime-----------------------------
                    frame_list_result = self.write_frame_time(item_value_list, time_item)
                    with open(property_all.get("frametime")[0], "a+", encoding="utf-8") as df:
                        if frame_list_result:
                            df.writelines(frame_list_result)
                    # -----------------------fps-------------------------------------
                    with open(property_all.get("fps")[0], 'a+', encoding="utf-8") as df:
                        csv.writer(df, lineterminator='\n').writerow(FPS_list)
                        del FPS_list[:]
                    delta_inter = self.interval - time_consume
                    if delta_inter > 0:
                        time.sleep(delta_inter)
            except Exception as e:
                logging.error("an exception hanpend in FPS thread , reason unkown!, e:")
                logging.error(e)
                logging.error(traceback.format_exc())
                G.device.get_pid()
            G.monitor_pause.wait()
        logging.debug("FPS stop event is set or timeout")


    def write_frame_time(self, frame_time_list, time_item):
        result_list = []
        s_io = io.StringIO()
        for i in frame_time_list:
            # logger.info("i: {0}, self.before_frame_time {1}".format(i, frame_time_list))
            if not self.before_frame_time_data:
                self.before_frame_time_data = i
                continue
            else:
                # real_timestamp = ParsFPSInfo.PHONE_REAL_TIME_INTERVAL + i
                interval_time = round((i - self.before_frame_time_data) * 1000, 4)
                if interval_time < 0:
                    logger.error("数据间隔异常 {0} {1}".format(self.before_frame_time_data, i))
                    self.before_frame_time_data = None
                    continue
                csv.writer(s_io, lineterminator='\n').writerow([time_item, interval_time, i])
                result_list.append(s_io.getvalue())
                s_io.seek(0)
                s_io.truncate()
                self.before_frame_time_data = i
        return result_list

class ParsFPSInfo(object):
    FPS_queue: list = []  # FPS collect, 每个帧对象的结果都汇集在这里，这里每次只留最后一个不完整的帧
    before_time: list = []  # 存第一秒前3帧的
    PHONE_REAL_TIME_INTERVAL: int = None  # 真实时间和手机时间的相对差值
    start_collect_time: float = None  # 开始时间测试的真实时间

    def __init__(self, surface_info):
        logger.info("star instance {0}".format(ParsFPSInfo.FPS_queue))
        self.lag_number = 0  # 每秒小于24帧的次数
        self.FTIMEGE100 = 0  # 增量耗时
        self.surface_info = surface_info
        self.jank_number = [0]
        self.big_jank_number = [0]
        self.front_FPS_list = []  # 第一个完整的秒的 FPS
        self.FPS_res_info_dict: dict = {}  # 真正返回的FPS结果集 {时间：帧信息, 时间+1s: 帧信息}
        self.FPS = self.get_FPS()
        logger.info("end instance {0}".format(ParsFPSInfo.FPS_queue))

    def get_FPS(self):
        self.add_new_FPS(self.surface_info)
        logger.info("end get new fps")
        self.get_front_FPS()
        logger.info("log get fps result")
        logger.info(ParsFPSInfo.FPS_queue)
        full_FPS_number = 1000
        self.full_FPS_number = full_FPS_number
        return self.FPS_res_info_dict

    def add_new_FPS(self, new_FPS):
        if ParsFPSInfo.FPS_queue:
            self.FPS_queue.extend(new_FPS)
            logger.info("find result")
            logger.info("剩余帧{0} , {1}".format(len(ParsFPSInfo.FPS_queue), ParsFPSInfo.FPS_queue))
            if not ParsFPSInfo.PHONE_REAL_TIME_INTERVAL:
                if len(new_FPS) > 126 and new_FPS[-1] != 0.0:
                    ParsFPSInfo.PHONE_REAL_TIME_INTERVAL = int(time.time()) - new_FPS[-1]
                    logger.info("时间间隔-new-{0}, {1}".format(ParsFPSInfo.PHONE_REAL_TIME_INTERVAL, new_FPS[-1]))
        else:
            ParsFPSInfo.FPS_queue.extend(new_FPS)
            if not ParsFPSInfo.PHONE_REAL_TIME_INTERVAL:
                first_time = 0.0  #拿到第一个有值的数据和真实时间对应
                for i in ParsFPSInfo.FPS_queue:
                    if float(i) != 0.0 and first_time == 0.0:
                        first_time = i
                logger.info("first_time {0}".format(first_time))
                if first_time != 0.0:
                    if ParsFPSInfo.start_collect_time:
                        ParsFPSInfo.PHONE_REAL_TIME_INTERVAL = ParsFPSInfo.start_collect_time - int(first_time)
                        # ParsFPSInfo.start_collect_time = None, 不会中断开始收集时间有一个就够了
                    else:
                        ParsFPSInfo.PHONE_REAL_TIME_INTERVAL = int(time.time()) - int(first_time)
                    logger.info(
                        "时间间隔 {0} {1} {2} {3}".format(ParsFPSInfo.PHONE_REAL_TIME_INTERVAL, time.time(), first_time,
                                                      ParsFPSInfo.FPS_queue))
                else:
                    ParsFPSInfo.FPS_queue = []
                    ParsFPSInfo.PHONE_REAL_TIME_INTERVAL = None
                    logger.info("第一个时间戳有误")
                    logger.info(ParsFPSInfo.FPS_queue)

    def get_front_FPS(self):
        """
        PerfDog Jank计算方法：
        同时满足两条件，则认为是一次卡顿Jank.
        ①Display FrameTime>前三帧平均耗时2倍。
        ②Display FrameTime>两帧电影帧耗时 (1000ms/24*2=84ms)。
        同时满足两条件，则认为是一次严重卡顿BigJank.
        ①Display FrameTime >前三帧平均耗时2倍。
        ②Display FrameTime >三帧电影帧耗时(1000ms/24*3=125ms)。
        """
        # 拿到了队列里所有的完整帧
        while ParsFPSInfo.FPS_queue:
            logger.info("join get front fps")
            tmp = []
            time_flag = ParsFPSInfo.FPS_queue.pop(0)
            time_second = int(time_flag)
            tmp.append(time_flag)
            while ParsFPSInfo.FPS_queue and int(ParsFPSInfo.FPS_queue[0]) == time_second:
                header_ele = ParsFPSInfo.FPS_queue.pop(0)
                tmp.append(header_ele)
            if not ParsFPSInfo.FPS_queue:
                ParsFPSInfo.FPS_queue.extend(tmp)
                break
            else:
                self.front_FPS_list.append(tmp)
        res_dict = {}
        try:
            for item_list in self.front_FPS_list:
                # print(item_list[0], ParsFPSInfo.PHONE_REAL_TIME_INTERVAL)
                # 如果当前帧都是空就跳过
                if sum(item_list) == 0.0:
                    continue
                first_time_head = None  # 获取第一个帧第一个有时间的值
                for time_head in item_list:
                    first_time_head = time_head if time_head else None
                res_dict[int(first_time_head) + ParsFPSInfo.PHONE_REAL_TIME_INTERVAL] = item_list[0:]
        except Exception as e:
            logging.error(e)
            logger.info("front_FPS_list to dict err")
            traceback.print_exc()
        self.FPS_res_info_dict: dict = res_dict
        self.get_jank(self.FPS_res_info_dict)

    def get_jank(self, FPS_res_info_dict: dict):
        for front_index, (time_number, item_list_v) in enumerate(FPS_res_info_dict.items()):
            for index, v in enumerate(item_list_v):
                if len(ParsFPSInfo.before_time) < 4:
                    ParsFPSInfo.before_time.append(v)
                else:
                    interval = v - ParsFPSInfo.before_time[-1]
                    if interval > 0.1:
                        ParsFPSInfo.FTIMEGE100 = 1
                    else:
                        ParsFPSInfo.FTIMEGE100 = 0
                    if v - ParsFPSInfo.before_time[-1] > sum([
                        ParsFPSInfo.before_time[-1] - ParsFPSInfo.before_time[-2],
                        ParsFPSInfo.before_time[-2] - ParsFPSInfo.before_time[-3],
                        ParsFPSInfo.before_time[-3] - ParsFPSInfo.before_time[-4], ]) / 3 * 2:
                        if interval > 0.125:
                            if len(self.big_jank_number) <= front_index:
                                self.big_jank_number.append(1)
                            else:
                                self.big_jank_number[front_index] += 1
                            logger.info(" big jank： {0} - {1}  {2}".format(v, ParsFPSInfo.before_time[-1], FPS_res_info_dict))
                        elif interval > 0.084:
                            if len(self.jank_number) <= front_index:
                                self.jank_number.append(1)
                            else:
                                self.jank_number[front_index] += 1
                                logger.info(" big jank： {0} - {1}  {2}".format(v, ParsFPSInfo.before_time[-1],
                                                                               FPS_res_info_dict))
                    ParsFPSInfo.before_time.pop(0)
                    ParsFPSInfo.before_time.append(v)




if __name__ == "__main__":
    from device import PCDevice


    G.device =     pc_device = PCDevice(serialno="LF-0101000279", device_addr=["10.130.108.26", "9230"], save_dir="windows_perf_tool/", pid_id="15788", pid_name="pycharm64.exe")
    # G.device.start_app()
    pc_perf = PcPerf("windows_perf_tool/")
    pc_perf.start()
    time.sleep(60)
    pc_perf.stop()

