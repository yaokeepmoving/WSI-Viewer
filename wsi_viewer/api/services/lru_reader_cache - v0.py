from collections import OrderedDict

class Reader:
    """模拟文件读取器对象（实际使用时可替换为具体实现）"""
    def __init__(self, file_path):
        self.file_path = file_path
        self.id = file_path  # 用文件路径作为唯一ID
        # 实际使用时可添加打开文件、初始化等逻辑
    
    def read(self):
        """模拟读取操作"""
        return f"读取内容：{self.file_path}"

class LRUReaderCache:
    """LRU策略的Reader对象缓存（最大容量5）"""
    def __init__(self, max_size=5):
        self.max_size = max_size
        self.cache = OrderedDict()  # 键：文件路径（唯一ID），值：Reader对象

    def get(self, file_path):
        """获取已存在的Reader对象（更新使用时间）"""
        if file_path not in self.cache:
            return None
        # 将对象移到末尾表示最近使用
        self.cache.move_to_end(file_path)
        return self.cache[file_path]

    def add(self, file_path):
        """添加新Reader对象（自动执行LRU淘汰）"""
        # 若已存在则直接返回并更新顺序
        if file_path in self.cache:
            return self.get(file_path)
        
        # 创建新Reader对象（实际使用时可替换为具体的读取器创建逻辑）
        new_reader = Reader(file_path)
        
        # 缓存已满时淘汰最久未使用的对象
        if len(self.cache) >= self.max_size:
            lru_key, _ = self.cache.popitem(last=False)
            print(f"LRU淘汰: {lru_key}")
        
        # 添加新对象并标记为最近使用（移到末尾）
        self.cache[file_path] = new_reader
        self.cache.move_to_end(file_path)
        return new_reader

    def __len__(self):
        """获取当前缓存大小"""
        return len(self.cache)

# 示例用法
if __name__ == "__main__":
    # 初始化容量为5的缓存
    cache = LRUReaderCache(max_size=5)
    
    # 定义测试文件路径（模拟不同文件）
    files = [f"file_{i}.wsi" for i in range(1, 8)]  # 7个文件
    
    # 模拟打开文件操作
    for idx, file in enumerate(files, 1):
        print(f"\n第{idx}次操作：打开 {file}")
        
        # 尝试获取已存在的Reader
        existing_reader = cache.get(file)
        if existing_reader:
            print(f"直接使用已存在的Reader: {existing_reader.id}")
            print(existing_reader.read())
            continue
        
        # 新增Reader对象
        new_reader = cache.add(file)
        print(f"创建新Reader: {new_reader.id}")
        print(new_reader.read())
        print(f"当前缓存内容: {list(cache.cache.keys())}")

    # 测试重复访问（验证LRU顺序更新）
    print("\n测试重复访问：")
    print("重新打开 file_3.wsi")
    cache.get("file_3.wsi")
    print(f"缓存顺序更新后: {list(cache.cache.keys())}")
    