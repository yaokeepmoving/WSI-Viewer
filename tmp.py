import pyvips
from pathlib import Path


def generate_dzi_image(slide_path, outpath=None):
    slide_id = Path(slide_path).stem
    # Load the slide
    image = pyvips.Image.new_from_file(slide_path)

    # Generate the DZI image
    outpath = outpath or slide_id
    image.dzsave(outpath, tile_size=256, overlap=0, depth='onetile')


slide_path = 'D:/zy/proj_zy/medical_ai/data/CMU-1.svs'
generate_dzi_image(slide_path, outpath=None)
