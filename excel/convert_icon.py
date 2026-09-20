from PIL import Image
import os

def convert_png_to_ico(png_path, ico_path):
    img = Image.open(png_path)
    # Windows icons usually contain multiple sizes: 16x16, 32x32, 48x48, 64x64, 128x128, 256x256
    icon_sizes = [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
    img.save(ico_path, format='ICO', sizes=icon_sizes)
    print(f"Converted {png_path} to {ico_path}")

if __name__ == "__main__":
    convert_png_to_ico("app_icon.png", "app_icon.ico")
