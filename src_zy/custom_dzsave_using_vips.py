import subprocess

def vips_cli_dzsave(input_path: str, output_name: str, downsize: int = 3):
    """
    通过 libvips 命令行调用 dzsave，支持 --downsize 参数
    """
    cmd = [
        "vips",
        "dzsave",
        input_path,
        output_name,
        f"--downsize={downsize}",
        "--tile-size=256",
        "--suffix=.jpg"
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"通过命令行生成 DZI 成功：{output_name}.dzi")
    except subprocess.CalledProcessError as e:
        print(f"命令行调用失败：{e}")

# 示例用法
vips_cli_dzsave("large_image.tif", "cli_dzi", downsize=3)