import asyncio
from adbutils import AdbDevice


class Fps(object):
    frame_que = list()
    surface_view = None
    before_get_view_data_status = False  # 上次获取view的结果，如果拿到了结果就不用修改view
    single_instance = None

    @staticmethod
    def check_queue_head_frames_complete():
        if not Fps.frame_que:
            return False
        head_time = int(Fps.frame_que[0])
        end_time = int(Fps.frame_que[-1])
        if head_time == end_time:
            return False
        return True

    @staticmethod
    def pop_complete_fps():
        head_time = int(Fps.frame_que[0])
        complete_fps = []
        while int(Fps.frame_que[0]) == head_time:
            complete_fps.append(Fps.frame_que.pop(0))
        return complete_fps

    def __init__(self, device: AdbDevice, package):
        self.package = package
        self.device = device
        self.device.shell("dumpsys SurfaceFlinger --latency-clear")

    def __new__(cls, *args, **kwargs):
        if not cls.single_instance:
            cls.single_instance = super().__new__(cls)
        cls.single_instance.device, cls.single_instance.package = args
        return cls.single_instance

    async def get_surface_view(self):
        all_list = await asyncio.to_thread(self.device.shell,
                                           "dumpsys SurfaceFlinger --list | grep {0}".format(self.package))
        views = all_list.split("\n")
        cur_view, view_data = await self.get_right_view(views)
        if cur_view:
            Fps.surface_view = cur_view
            Fps.before_get_view_data_status = True
        else:
            Fps.before_get_view_data_status = False
        return cur_view, view_data

    async def get_right_view(self, views):
        views = [i for i in views if not "Background for" in i]
        views_spec = [i for i in views if ("SurfaceView" in i) or ("BLAST" in i)]
        if views_spec:
            views = views_spec
        res = await asyncio.gather(*[self.get_view_res(view) for view in views])
        right_view = None
        right_view_data = []
        for index, view_res in enumerate(res):
            if not view_res:
                continue
            if len(view_res) < 127:
                continue
            if not ((view_res[-1] > 0) and (view_res[-2] > 0)):
                continue
            right_view = views[index]
            right_view_data = view_res
        return right_view, right_view_data

    async def get_view_res(self, view):
        if view:
            res_str = await asyncio.to_thread(self.device.shell, "dumpsys SurfaceFlinger --latency '{0}' ".format(view))
            return [float(i.split()[1]) / 1e9 for i in res_str.split("\n") if len(i.split()) >= 3]
        else:
            return []

    async def fps(self):
        while not self.check_queue_head_frames_complete():
            cur_frames = []
            if not Fps.before_get_view_data_status:
                view, cur_frames = await self.get_surface_view()
            else:
                cur_frames = await self.get_view_res(Fps.surface_view)
            new_frames = [i for i in cur_frames if (not Fps.frame_que) or (i > Fps.frame_que[-1])]
            if not cur_frames or cur_frames[-1] <= 0:
                Fps.surface_view = None
                Fps.before_get_view_data_status = False
            Fps.frame_que.extend(new_frames)
            await asyncio.sleep(0.5)
        return self.pop_complete_fps()
