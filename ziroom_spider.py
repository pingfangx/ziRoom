# coding=utf-8
import json
import math
import queue
import threading
import time
import zipfile

import requests

API_URL = "http://www.ziroom.com/map/room/list?min_lng=%.6f&max_lng=%.6f&min_lat=%.6f&max_lat=%.6f&p=%d"


class Grid:
    """区块"""

    def __init__(self, lonlat):  # [lon_min,lon_max,lat_min,lat_max]
        self._lon_min = lonlat[0]
        self._lon_max = lonlat[1]
        self._lat_min = lonlat[2]
        self._lat_max = lonlat[3]
        self._page_one_cache = None
        "第一页的缓存"

    def __str__(self):
        return "%.6f,%.6f,%.6f,%.6f" % tuple(self.get_range())

    def get_range(self):
        return [self._lon_min, self._lon_max, self._lat_min, self._lat_max]

    def _json_request(self, lonlat, page_index):
        """联网请求或使用缓存"""
        if page_index == 1 and self._page_one_cache is not None:
            return self._page_one_cache

        url = API_URL % (lonlat[0], lonlat[1], lonlat[2], lonlat[3], page_index)
        retry_time = 0
        while True and retry_time < 10:
            retry_time += 1
            # sys.stdout.write('\r get %s ' % url)
            # sys.stdout.flush()
            try:
                json_str = requests.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, "
                                  "like Gecko) Chrome/62.0.3202.94 Safari/537.36",
                    "Referer": "http://www.ziroom.com/map/"
                }, timeout=1).text
                obj = json.loads(json_str)
                if obj["code"] == 200:
                    obj = json.loads(json_str)
                    self._page_one_cache = obj
                    return obj
                else:
                    print("error %s" % json_str)
            except requests.exceptions.ReadTimeout:
                pass
            except Exception as e:
                print(type(e))
                print('error:%s' % e)

    def status(self):
        obj = self._json_request((self._lon_min, self._lon_max, self._lat_min, self._lat_max), 1)
        if len(obj["data"]["rooms"]) == 0:
            return -1
        elif obj["data"]["pages"] == 1:
            # 只有一页，不需要划分
            return -2
        return 0

    def area(self):
        return (self._lon_max - self._lon_min) * 1e5 * (self._lat_max - self._lat_min) * 1e5

    def get_rooms(self, thread_id):
        """获取房间，会获取各页"""
        result = {}
        page_index = 1

        useless_count = 0

        while True:
            last_len = len(result)
            obj = self._json_request((self._lon_min, self._lon_max, self._lat_min, self._lat_max), page_index)

            if obj is None:
                print('线程 %d 结果为空,跳过 %d 页' % (thread_id, page_index))
                page_index += 1
                continue

            for item in obj["data"]["rooms"]:
                result[item["id"]] = item

            pages = obj["data"]["pages"]
            if page_index == pages:
                # 到达最后一页
                print('线程 %d 获取 %d/%d 页完成,获得 %d 处房源,添加 %d 房源' % (
                    thread_id, page_index, pages, len(obj['data']['rooms']), len(result) - last_len))
                return result
            if len(obj["data"]["rooms"]) == 0:
                # 没有数据
                print('线程 %d 获取 %d/%d 页，结果为空' % (thread_id, page_index, pages))
                return result
            if last_len == len(result):
                # 没有产生结果
                useless_count += 1
            if useless_count > 3:
                # 这里不太清原来的逻辑,可能是 result 更新时 id 相同导致相同数据数量没有添加
                print('线程 %d 获取 %d/%d 页，无效数据超限' % (thread_id, page_index, pages))
                return result
            page_index += 1
            print('线程 %d 获取 %d/%d 页完成,获得 %d 房源,添加 %d 房源' % (
                thread_id, page_index, pages, len(obj['data']['rooms']), len(result) - last_len))

    def split(self, count=2):
        """分割"""
        lon_step = (self._lon_max - self._lon_min) / count
        lat_step = (self._lat_max - self._lat_min) / count

        result = []

        for i in range(0, count):
            for j in range(0, count):
                temp = Grid([(self._lon_min + i * lon_step),
                             (self._lon_min + (i + 1) * lon_step),
                             (self._lat_min + j * lat_step),
                             (self._lat_min + (j + 1) * lat_step)])
                result.append(temp)
        return result


class GridManager:
    def __init__(self, lonlat, min_area=1e6, split_count=2, thread_num=4):
        self._q = queue.Queue()
        "队列"

        root_grid = Grid(lonlat)
        self._q.put(root_grid)
        self._total_area = root_grid.area()
        self._min_area = min_area
        self._split_count = split_count
        self._thread_num = thread_num
        self._result = {}
        self._scan_start_time = 0
        self._scanned_area = 0

    def run(self):
        """
        分析这一段算法，出列，如果不为空，则分割，再入列，取下一个
        这样的结果是，当到达第一个最小区域时，整个队列中都是最小区域块，其中一些可能仍没有房源
        """
        self._scan_start_time = time.time()

        # 第一步，划分区块

        # 求需要划分多少轮
        # 最大面积除以最小面积，得到倍数，再对 划分数量的平方求对数，取 ceil
        num = int(math.ceil(math.log(self._total_area / self._min_area, self._split_count ** 2)))
        print('划分区块，共需要划分 %d 轮' % num)

        # 划分至最小块
        for i in range(num):
            scan_size = self._q.qsize()
            print('\n划分第 %d/%d 轮，本轮共需划分 %d 个区块' % (i + 1, num, scan_size))

            smaller_area_queue = queue.Queue()
            temp_index = 0
            while not self._q.empty():
                temp_index += 1
                grid = self._q.get()
                status = grid.status()
                if status == -1:
                    # 为空
                    print('第 %d/%d 个区块为空，移除' % (temp_index, scan_size))
                elif status == -2:
                    print('第 %d/%d 个区块只有一页，加进队列' % (temp_index, scan_size))
                    smaller_area_queue.put(grid)
                else:
                    # 需要划分
                    print('第 %d/%d 个区块不为空，进行划分' % (temp_index, scan_size))
                    for item in grid.split(count=self._split_count):
                        smaller_area_queue.put(item)
            # 经过上一层循环，q 已为空，新划分的小块全部位于 smaller_area_queue 中
            self._q = smaller_area_queue

        # 第二步，对划分的所有最小区块抓取房源

        size = self._q.qsize()
        print('划分区块结束，花费时间 %ds，开始抓取房源，共有 %d 个区块' % (time.time() - self._scan_start_time, size))
        self._scan_start_time = time.time()
        self._scanned_area = 0
        threads = []
        for i in range(0, self._thread_num):
            worker = threading.Thread(target=self.get_rooms_in_thread, args=(i + 1,))
            worker.start()
            threads.append(worker)
        # 这里好像不需要 thread 的 join，queue 的 join 也会阻塞，但还是加上线程的 join，以使线程结束后再继续执行
        # https://docs.python.org/3/library/queue.html
        # http://blog.csdn.net/xiao_huocai/article/details/74781820
        # block until all tasks are done
        self._q.join()
        for t in threads:
            t.join()
        print("获取结束")
        return self._result

    def get_rooms_in_thread(self, thread_id):
        while True:
            try:
                self.get_rooms(thread_id)
            except queue.Empty:
                print('线程 %d 结束' % thread_id)
                break

    def get_rooms(self, thread_id):
        area = self._q.get(block=True, timeout=1)  # 不设置阻塞的话会一直去尝试获取资源
        self._scanned_area += 1
        print('线程 %d 获取第 %d 个区块' % (thread_id, self._scanned_area))
        self._result.update(area.get_rooms(thread_id))
        remain_time = (time.time() - self._scan_start_time) / self._scanned_area * self._q.qsize()
        print('线程 %d 获取完成，当前共 %d 个房源，队列剩余 %d 个区块，花费时间 %ds，预计剩余时间 %ds ' % (
            thread_id, len(self._result), self._q.qsize(), time.time() - self._scan_start_time, remain_time))
        # 告知结束一个任务
        self._q.task_done()


if __name__ == '__main__':
    grid_range = [115.7, 117.4, 39.4, 41.6]  # 北京市范围，扫描别的城市，只要修改经纬度范围即可 参数格式["lon_min,lon_max,lat_min,lat_max"]

    # 测试
    # gm = GridManager(grid_range, min_area=1e9)
    gm = GridManager(grid_range, thread_num=16)
    all_rooms = gm.run()
    rooms = list(filter(lambda x: x["room_status"] != "ycz" and x["room_status"] != "yxd", all_rooms.values()))
    share_rooms = list(filter(lambda x: x["is_whole"] == 0, rooms))
    whole_rooms = list(filter(lambda x: x["is_whole"] == 1, rooms))

    print("整租房源: %d     合租房源:%d" % (len(whole_rooms), len(share_rooms)))

    with zipfile.ZipFile('web/all_rooms.zip', 'w', zipfile.ZIP_DEFLATED) as f:
        f.writestr('all_rooms.json', json.dumps(all_rooms))
    with zipfile.ZipFile('web/share_rooms.zip', 'w', zipfile.ZIP_DEFLATED) as f:
        f.writestr('share_rooms.json', json.dumps(share_rooms))
    with zipfile.ZipFile('web/whole_rooms.zip', 'w', zipfile.ZIP_DEFLATED) as f:
        f.writestr('whole_rooms.json', json.dumps(whole_rooms))
    print('保存结果完成')
