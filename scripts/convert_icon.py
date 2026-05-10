from PIL import Image, ImageDraw, ImageOps
import os

def convert_to_perfect_circular():
    img_path = "app_logo.png"
    png_path = "app_logo_circular.png"
    icon_path = "app_icon.ico"
    
    if not os.path.exists(img_path):
        print(f"Error: {img_path} not found")
        return

    # Open and convert to RGBA
    img = Image.open(img_path).convert("RGBA")
    
    # 1. Detect the tightest possible bounding box of the logo content
    # Convert to grayscale and invert to find the most extreme non-white pixels
    grayscale = img.convert("L")
    inverted = ImageOps.invert(grayscale)
    bbox = inverted.getbbox()
    
    if bbox:
        # Crop EXACTLY to the bounding box (no padding)
        img = img.crop(bbox)

    # 2. Force the image to be a perfect square before masking
    width, height = img.size
    size = min(width, height)
    img = img.crop(((width - size) // 2, (height - size) // 2, (width + size) // 2, (height + size) // 2))
    size = img.size[0]

    # 3. Create an anti-aliased mask that is slightly "shrunk" (1px) 
    # to ensure the grey outline is the absolute edge.
    mask_size = size * 4
    mask = Image.new('L', (mask_size, mask_size), 0)
    draw = ImageDraw.Draw(mask)
    
    # We draw the circle slightly smaller than the full size (shrink by 4px at 4x scale = 1px at 1x)
    # This ensures we don't catch any white pixels from the outer edge of the original grey border
    shrink = 4 
    draw.ellipse((shrink, shrink, mask_size - shrink, mask_size - shrink), fill=255)
    
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)
    
    # 4. Apply the mask
    circular_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    circular_img.paste(img, (0, 0), mask=mask)

    # Save outputs
    circular_img.save(png_path, "PNG")
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    circular_img.save(icon_path, format="ICO", sizes=icon_sizes)
    
    print(f"Successfully created perfect circular branding:")
    print(f" - PNG: {png_path}")
    print(f" - ICO: {icon_path}")

if __name__ == "__main__":
    convert_to_perfect_circular()
