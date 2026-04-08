import os
from PIL import Image, ImageDraw, ImageFont

# Crop 15% from each side
to_crop = [
    'cat_champagne.jpg',
    'cat_candy.jpg'
]

for img_name in to_crop:
    path = os.path.join('assets', img_name)
    if os.path.exists(path):
        try:
            with Image.open(path) as img:
                w, h = img.size
                
                left = int(w * 0.15)
                top = int(h * 0.15)
                right = int(w * 0.85)
                bottom = int(h * 0.85)
                
                cropped = img.crop((left, top, right, bottom))
                cropped = cropped.convert("RGB")
                cropped.save(path)
                print(f"Cropped {img_name}")
        except Exception as e:
            print(f"Failed to process {img_name}: {e}")

# Add transparent white text to cities
cities = {
    'bucuresti.jpg': 'Bucuresti',
    'craiova.jpg': 'Craiova'
}

for img_name, text in cities.items():
    path = os.path.join('assets', img_name)
    if os.path.exists(path):
        try:
            with Image.open(path) as img:
                img = img.convert("RGBA")
                txt_overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(txt_overlay)
                
                # Try load an italic or bold standard windows font so it looks good, sizing it based on image height
                try:
                    font = ImageFont.truetype("arialbd.ttf", int(img.size[1]*0.15))
                except:
                    try:
                        font = ImageFont.truetype("arial.ttf", int(img.size[1]*0.15))
                    except:
                        font = ImageFont.load_default()
                    
                # Get text bounding box
                if hasattr(font, 'getbbox'):
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]
                else:
                    text_w, text_h = draw.textsize(text, font=font)
                    
                x = (img.size[0] - text_w) / 2
                y = (img.size[1] - text_h) / 2
                
                # Draw text with transparency (180 out of 255 opacity)
                # Add a slight dark transparent shadow for pop
                draw.text((x+4, y+4), text, font=font, fill=(0, 0, 0, 100))
                draw.text((x, y), text, font=font, fill=(255, 255, 255, 180))
                
                out = Image.alpha_composite(img, txt_overlay)
                out = out.convert("RGB")
                out.save(path)
                print(f"Added transparent text to {img_name}")
        except Exception as e:
            print(f"Failed to process {img_name}: {e}")
