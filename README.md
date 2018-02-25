# ziroom_spider
forked from [yrjyrj123/ziRoom](https://github.com/yrjyrj123/ziRoom),thanks.

自如爬虫，按区域抓取自如房源，并使用百度地图可视化。

![房源可视化效果](https://github.com/yrjyrj123/image/raw/master/ziroom_map.png)

## 自行搜集房源

### 安装依赖的模块:

	pip install -r requirements.txt

### 使用方法：

修改 **ziroom_spider.py** 第一行中的经纬度范围为想要扫描的范围：

	grid_range = [115.7, 117.4, 39.4, 41.6] #北京市范围 
	#参数格式["lon_min,lon_max,lat_min,lat_max"]
	
参数说明:

- lon_min: 经度最小值
- lon_max: 经度最大值
- lat_min: 纬度最小值
- lat_max: 纬度最大值

运行：
	
	python ziroom_spider.py

如果一切正常，将看到类似输出：

	#已扫描面积 / 总面积 = 完成百分比 : 扫描到的房源
	9350000000 / 37400000000 = 25.00% : 0
	18700000000 / 37400000000 = 50.00% : 0
	21037500000 / 37400000000 = 56.25% : 0
	23375000000 / 37400000000 = 62.50% : 0
	25712500000 / 37400000000 = 68.75% : 0
	26296874999 / 37400000000 = 70.31% : 0
	26881249999 / 37400000000 = 71.87% : 0
	
扫描完成后，将在web目录下生成**share_rooms.zip**(合租) 和 **whole_rooms.zip**(整租) 两个文件。

由于浏览器限制，需要将web目录部署至一个HTTP服务器，才可以进行可视化。

启动一个简易HTTP服务器:
	
	cd web
	python -m http.server 5000

使用浏览器打开**http://localhost:5000**

不出意外的话，就可以看到一堆房源在地图上了。

红色是合租，绿色是整租。