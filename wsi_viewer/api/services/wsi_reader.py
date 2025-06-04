import re
from xmltodict import parse
import logging
import math
import os
from abc import abstractmethod
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import cv2
import numpy as np
import pyvips

logger = logging.getLogger(__name__)


IMPORTANT_WSI_PROPERTIES = ['width', 'height', 'tile_width', 'tile_height', 'mpp',
                            'magnification', 'level_count', 'level_downsamples']

REQUIRED_WSI_PROPERTIES = ['width', 'height', 'tile_size', 'mpp',
                           'level_count', 'level_downsamples', 'level_dimensions']

GENERAL_IMAGE_FORMATS = set(['.jpg', '.jpeg', '.tif', '.tiff', '.png', '.bmp'])
WSI_IMAGE_FORMAT_COMMON = ['.svs', '.tif', '.tiff',
                           '.ndpi', '.vms', '.vmu', '.scn', '.mrxs']
WSI_IMAGE_FORMAT_ZH = ['.sdpc', '.kfb', '.tmap']
WSI_IMAGE_FORMAT = set(WSI_IMAGE_FORMAT_COMMON + WSI_IMAGE_FORMAT_ZH)


def read_wsi_metadata(slide_path):
    """读取WSI文件的元数据

    [demo]

        # slide_path = "D:/zy/proj_zy/medical_ai/data/CMU-1.svs"
        slide_path = 'D:/zy/proj_zy/medical_ai/WSI-Viewer/wsi_viewer/static/slides/e5300f71-79ce-4390-bc0e-7748144aedf5.svs'
        metadata = read_wsi_metadata(slide_path)    

    """

    # # 定义需要读取的元数据键（OpenSlide 标准）
    # metadata_keys = {
    #     "width": "width",          # 基础属性（非元数据键）
    #     "height": "height",        # 基础属性（非元数据键）
    #     "mpp_x": "openslide.mpp-x",
    #     "mpp_y": "openslide.mpp-y",
    #     "level_count": "openslide.level-count"
    # }

    img = pyvips.Image.new_from_file(slide_path, access="sequential")

    available_keys = img.get_fields()

    metadata = {vips_key: img.get(vips_key) for vips_key in available_keys}

    # 删除一些属性

    del_keys = []
    for k, v in metadata.items():
        if not isinstance(v, (str, int, float)):
            logger.debug(
                f'[ read_wsi_metadata ] key type must be str, int, or float, delete it, key: {k}, value type : {type(v)}')
            del_keys.append(k)

    for k in del_keys:
        # v = metadata.pop(k)
        del metadata[k]

    # 获取 mpp
    # metadata['image-description']: 'Aperio Image Format\r\n88115x78739 [0,0 88115x78739] (256x256) JPEG/RGB Q=60|AppMag = 40|MPP = 0.247877'
    mpp_pat = r'MPP\s*=\s*([\d.]+)'
    match = re.search(mpp_pat, metadata['image-description'])
    mpp = float(match.group(1)) if match else None
    metadata['mpp'] = mpp

    # 获取放大倍数
    mag_pat = r'AppMag\s*=\s*([\d.]+)'
    match = re.search(mag_pat, metadata['image-description'])
    mag = float(match.group(1)) if match else None
    metadata['mag'] = mag

    if metadata:
        logger.debug("=== 元数据 ===")
        for key, value in metadata.items():
            logger.debug(f"{key}: {value}")

    return metadata


def generate_dzi_image(slide_path, outpath=None):
    """
    [demo]

        slide_path = 'D:/zy/proj_zy/medical_ai/data/CMU-1.svs'
        generate_dzi_image(slide_path, outpath=None)

    """

    # Load the slide
    image = pyvips.Image.new_from_file(slide_path)

    # Generate the DZI image
    outpath = outpath or Path(slide_path).name
    # pyvips: enum 'VipsForeignDzDepth' has no member 'all', should be one of: onepixel, onetile, one
    # 每层下采样 2 倍（默认值）
    image.dzsave(outpath, tile_size=512, overlap=0,
                 depth='onetile',
                 suffix='.jpg')


class BaseReader:
    def __init__(self, slide_path, cache_dir='cache_dir'):
        self.slide_path = slide_path
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.__slide_info = None
        self.pyramid = None

    @property
    def slide_info(self):
        return self.__slide_info

    @slide_info.setter
    def slide_info(self, value):
        self.__slide_info = value

    @abstractmethod
    def open_slide(self, slide_path: str) -> Tuple[bool, Optional[Dict]]:
        raise NotImplementedError

    @abstractmethod
    def get_tile(self, slide_id: str, x: int, y: int, level: int,
                 size: int = 512) -> Union[bytes, np.ndarray]:
        raise NotImplementedError


class PngLikeReader(BaseReader):
    def _build_pyramid(self, slide_path: str,
                       min_dimension=512  # 最小的tile尺寸
                       ):
        if not os.path.exists(slide_path):
            logger.error(f"文件不存在: {slide_path}")
            return False, None

        # 读取原始图像
        img = cv2.imread(str(slide_path))
        if img is None:
            logger.error(f"无法读取图像: {slide_path}")
            return False, None

        # 转换为RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # 获取图像尺寸
        height, width = img.shape[:2]
        logger.info(f"原始图像尺寸: {width}x{height}")

        # 计算金字塔层级数
        max_dimension = max(width, height)

        level_count = math.ceil(
            math.log2(max_dimension / min_dimension)) + 1

        # 生成金字塔层级信息
        level_dimensions = []
        level_downsamples = []
        current_width = width
        current_height = height

        for level in range(level_count):
            level_dimensions.append((current_width, current_height))
            level_downsamples.append(math.pow(2, level))

            # 计算下一级别的尺寸
            current_width = max(current_width // 2, min_dimension)
            current_height = max(current_height // 2, min_dimension)

        logger.info(f"生成{level_count}个层级:")
        for i, (w, h) in enumerate(level_dimensions):
            logger.info(
                f"Level {i}: {w}x{h}, 缩放比例: {level_downsamples[i]}")

        # 创建信息字典
        info = {
            'dimensions': (width, height),
            'level_count': level_count,
            'level_dimensions': level_dimensions,
            'level_downsamples': level_downsamples,
            'properties': {
                'openslide.level-count': str(level_count),
                'openslide.mpp-x': '0.2508',
                'openslide.mpp-y': '0.2508',
                'tiff.width': str(width),
                'tiff.height': str(height)
            },
            'format': 'tiff'
        }

        # 生成金字塔缓存
        pyramid = []
        current_image = img
        for level, (target_w, target_h) in enumerate(level_dimensions):
            if level == 0:
                pyramid.append(current_image)
            else:
                resized = cv2.resize(current_image, (target_w, target_h),
                                     interpolation=cv2.INTER_AREA)
                pyramid.append(resized)
                current_image = resized

        logger.info(f"成功打开图像文件: {slide_path}")
        self.slide_info = info
        self.pyramid = pyramid
        return True, info

    def open_slide(self, slide_path: str) -> Tuple[bool, Optional[Dict]]:
        # """
        if self.slide_info is None:
            try:
                return self._build_pyramid(slide_path)
            except Exception as e:
                logger.error(f"[ open_slide ] 打开图像失败: {str(e)}")
                return False, None

        return True, self.slide_info

    def get_tile(self,
                 slide_path: str,
                 x: int,
                 y: int,
                 level: int,
                 size: int = 512) -> Optional[str]:
        """获取指定位置的tile"""
        try:
            # 生成缓存文件名
            slide_id = Path(slide_path).stem
            cache_file = self.cache_dir / \
                f"{slide_id}_{level}_{x}_{y}_{size}.jpg"
            logger.debug(
                f'[ get_tile ] 请求tile: path={slide_path}, x={x}, y={y}, level={level}')

            # 检查缓存
            if cache_file.exists():
                logger.debug(f'[ get_tile ] 使用缓存: {cache_file}')
                return str(cache_file)

            # 获取切片信息
            slide_info = self.slide_info
            if slide_info is None:
                success, slide_info = self.open_slide(slide_path)
                if not success:
                    return None

            # 获取对应level的图像
            pyramid = self.pyramid

            if level >= len(pyramid):
                logger.error(
                    f'[ get_tile ] 无效的level: {level}, 最大level: {len(pyramid)-1}')
                return None

            # 获取当前level的图像和尺寸信息
            level_image = pyramid[level]
            level_width, level_height = level_image.shape[1], level_image.shape[0]

            # 计算tile范围
            tile_x = x * size
            tile_y = y * size
            end_x = min(tile_x + size, level_width)
            end_y = min(tile_y + size, level_height)

            # 检查范围是否有效
            if tile_x >= level_width or tile_y >= level_height:
                logger.error(
                    f'[ get_tile ] tile坐标超出范围: x={tile_x}/{level_width}, y={tile_y}/{level_height}')
                return None

            # 提取tile区域
            tile = level_image[tile_y:end_y, tile_x:end_x]

            # 处理边缘tile的填充
            if tile.shape[0] != size or tile.shape[1] != size:
                logger.debug(
                    f'[ get_tile ] 填充tile边缘: 从{tile.shape}到{size}x{size}')
                full_tile = np.full((size, size, 3), 255, dtype=np.uint8)
                full_tile[:tile.shape[0], :tile.shape[1]] = tile
                tile = full_tile

            # 保存为JPEG
            cv2.imwrite(str(cache_file), cv2.cvtColor(tile, cv2.COLOR_RGB2BGR))
            logger.debug(f'[ get_tile ] 保存 tile => {cache_file}')

            return str(cache_file)

        except Exception as e:
            logger.error(f'[ get_tile ] 获取tile失败: {str(e)}')
            return None


def _extract_slide_info_from_dzi(dzi_path: str) -> Optional[Dict]:
    # 从 dzi 文件中提取 slide 信息
    with open(dzi_path, 'r') as f:
        xml = f.read()

    xml_dict = parse(xml)
    dzi_info = dict(format=xml_dict['Image']['@Format'],
                    overlap=int(xml_dict['Image']['@Overlap']),
                    tile_size=int(xml_dict['Image']['@TileSize']),
                    width=int(xml_dict['Image']['Size']['@Width']),
                    height=int(xml_dict['Image']['Size']['@Height']))

    # 从 dzi 目录中提取 slide 信息
    dzi_dir = dzi_path[:-4] + '_files'
    level_count = len([p for p in Path(dzi_dir).glob('**/*') if p.is_dir()])
    dzi_info['level_count'] = level_count

    # 生成金字塔层级信息
    width, height = dzi_info['width'], dzi_info['height']
    tile_size = dzi_info['tile_size']

    level_dimensions = []
    level_downsamples = []
    current_width = width
    current_height = height

    for level in range(level_count):
        level_dimensions.append((current_width, current_height))
        level_downsamples.append(math.pow(2, level))

        # 计算下一级别的尺寸
        current_width = max(current_width // 2, tile_size)
        current_height = max(current_height // 2, tile_size)

    dzi_info['level_dimensions'] = level_dimensions
    dzi_info['level_downsamples'] = level_downsamples

    return dzi_info


class WSIReader(BaseReader):

    def open_slide(self, slide_path: str) -> Tuple[bool, Optional[Dict]]:

        # """
        if self.slide_info is None:
            try:

                # 构建金字塔
                status, dzi_path = self._build_pyramid(slide_path)

                # 从 dzi 读取 slide 信息
                dzi_info = _extract_slide_info_from_dzi(dzi_path)

                # 直接从原始图像中读取 slide 信息
                slide_info = read_wsi_metadata(slide_path)

                # 合并 slide 信息
                slide_info.update(dzi_info)

                self.slide_info = slide_info

                return status, slide_info

            except Exception as e:
                logger.error(f"[ open_slide ] 打开图像失败: {str(e)}")
                return False, None

        return True, self.slide_info

    def get_tile(self, slide_id: str, x: int, y: int, level: int,
                 size: int = 512):
        new_level = self.slide_info['level_count'] - 1 - level
        tile_path = f'{self.cache_dir}/{Path(slide_id).name}_files/{new_level}/{x}_{y}.jpg'
        return tile_path

    def _build_pyramid(self, slide_path: str):
        if not os.path.exists(slide_path):
            logger.error(f"文件不存在: {slide_path}")
            return False, None

        # 检查文件是否已经处理过
        dzi_path = f'{self.cache_dir}/{Path(slide_path).name}.dzi'
        if os.path.exists(dzi_path):
            logger.debug(f'[ build_pyramid ] 已存在: {dzi_path}')
            return True, dzi_path

        outpath = f'{self.cache_dir}/{Path(slide_path).name}'
        generate_dzi_image(slide_path, outpath=outpath)
        return True, dzi_path


def open_slide(slide_path: str) -> PngLikeReader | WSIReader:
    """Open a whole-slide or regular image.

    Return an OpenSlide object for whole-slide images and an ImageSlide
    object for other types of images."""
    if Path(slide_path).suffix in GENERAL_IMAGE_FORMATS:
        return PngLikeReader(slide_path)

    return WSIReader(slide_path)


if __name__ == '__main__':
    slide_path = 'D:/zy/proj_zy/medical_ai/WSI-Viewer/wsi_viewer/static/slides/e5300f71-79ce-4390-bc0e-7748144aedf5.svs'
    slide_path = 'C:/Users/yq/BaiduNetdiskDownload/Breast-Pathology-MRI/100-107-4439/BC2_412_HE_003.svs'
    slide_obj = open_slide(slide_path)
    status, slide_info = slide_obj.open_slide(slide_path)
    print(status, slide_info)
    tile_path = slide_obj.get_tile(slide_path, 6, 48, 7, 512)
    a = 0
