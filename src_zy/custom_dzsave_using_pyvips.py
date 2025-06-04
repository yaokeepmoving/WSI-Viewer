import pyvips
import os
from pathlib import Path

def custom_dzsave(original_image_path: str, output_name: str, downsize_factor: int = 3):
    """
    手动生成自定义下采样倍数的 DZI 文件
    
    :param original_image_path: 原始图像路径
    :param output_name: 输出 DZI 名称
    :param downsize_factor: 下采样倍数（如 3）
    """
    # 读取原始图像（level 0）
    image = pyvips.Image.new_from_file(original_image_path)
    levels = []
    current_image = image
    level = 0

    # 生成各层级图像（直到尺寸小于等于瓦片大小）
    tile_size = 256
    while True:
        width, height = current_image.width, current_image.height
        levels.append((level, width, height, current_image))
        
        # 下采样生成下一层级（使用 pyvips 的 resize 方法）
        next_width = max(1, width // downsize_factor)
        next_height = max(1, height // downsize_factor)
        if next_width <= tile_size and next_height <= tile_size:
            break  # 停止生成层级
        
        # 下采样（使用双线性插值）
        current_image = current_image.resize(1 / downsize_factor, kernel="linear")
        level += 1

    # 创建 DZI 目录和瓦片文件
    dzi_dir = Path(f"{output_name}_files")
    dzi_dir.mkdir(exist_ok=True)
    for level, width, height, img in levels:
        level_dir = dzi_dir / str(level)
        level_dir.mkdir(exist_ok=True)
        
        # 切割瓦片（使用 pyvips 的 dzsave 逻辑或手动切割）
        img.dzsave(
            str(level_dir / "tile"),  # 瓦片文件前缀
            tile_size=tile_size,
            overlap=0,
            suffix=".jpg"
        )

    # 生成 DZI XML 文件
    dzi_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Image Format="jpg" Overlap="0" TileSize="{tile_size}" xmlns="http://schemas.microsoft.com/deepzoom/2008">
  {"".join([f'  <Size Width="{w}" Height="{h}"/>' for _, w, h, _ in levels])}
</Image>
"""
    with open(f"{output_name}.dzi", "w") as f:
        f.write(dzi_xml)

    print(f"自定义 DZI 生成完成：{output_name}.dzi")

# 示例用法（下采样倍数 3）
custom_dzsave("large_image.tif", "custom_dzi", downsize_factor=3)