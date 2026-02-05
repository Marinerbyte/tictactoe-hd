import os
import io
import time
import requests
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ==========================================
# --- ⚙️ CONFIGURATION (Settings) ---
# ==========================================
MAX_WORKERS = 10      # Ek sath kitne heavy tasks (Upload/Art) chalenge
CACHE_SIZE = 200      # RAM me kitni images save rahengi (Speed ke liye)
RETRY_LIMIT = 3       # Internet fail hone par kitni baar try karega
FONT_PATHS = [        # Fonts dhundne ki locations
    "arial.ttf",
    "seguiemj.ttf",   # Windows Emoji Font
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "C:\\Windows\\Fonts\\arial.ttf"
]

# Popular Stickers (Naam se use karne ke liye)
STICKER_PACK = {
    "laugh": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f602.png",
    "cool": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f60e.png",
    "love": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f60d.png",
    "sad": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f62d.png",
    "fire": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f525.png",
    "win": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f3c6.png",
    "bot": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f916.png"
}

class HighPerformanceUtils:
    def __init__(self):
        # 1. Thread Safety (Race Condition Proof)
        self.lock = threading.Lock()
        
        # 2. Bulletproof Network (Keep-Alive + Auto Retry)
        self.session = requests.Session()
        retries = Retry(total=RETRY_LIMIT, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        # 3. Background Workers (Non-Blocking)
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="ArtWorker")

        # 4. Smart Asset Cache
        self._img_cache = {}
        self._font_cache = {}

    # ---------------------------------------------------------
    # 🌐 NETWORK LAYER (Download & Upload)
    # ---------------------------------------------------------

    def run_async(self, func, *args, **kwargs):
        """Background me task chalane ke liye"""
        return self.executor.submit(func, *args, **kwargs)

    def download_image(self, url):
        """Fast Download with Memory Cache"""
        if not url: return None
        
        # Check Cache (Thread Safe)
        with self.lock:
            if url in self._img_cache:
                return self._img_cache[url].copy()

        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                
                # Update Cache
                with self.lock:
                    if len(self._img_cache) > CACHE_SIZE:
                        self._img_cache.pop(next(iter(self._img_cache))) # Oldest hatao
                    self._img_cache[url] = img
                return img
        except Exception as e:
            print(f"[Utils] Download Error: {e}")
        return None

    def upload_image_fast(self, image_data, token, user_id, file_type='png'):
        """High-Performance Upload using Session Pool - CRASH PROOF VERSION"""
        import io
        
        # 🔥 CRITICAL SAFETY CHECK
        if image_data is None:
            print("[Utils] Error: Upload cancelled (Image data is None).")
            return None

        try:
            final_bytes = None

            # 1. Agar ye PIL Image hai (Standard plugins ke liye)
            if isinstance(image_data, Image.Image):
                img_byte_arr = io.BytesIO()
                image_data.save(img_byte_arr, format=file_type.upper())
                final_bytes = img_byte_arr.getvalue()
            
            # 2. Agar ye pehle se BytesIO hai (Gift Shop fix)
            elif isinstance(image_data, io.BytesIO):
                final_bytes = image_data.getvalue()
            
            # 3. Agar ye Raw Bytes hai
            elif isinstance(image_data, (bytes, bytearray)):
                final_bytes = image_data
            
            else:
                print(f"[Utils] Error: Unsupported image type {type(image_data)}")
                return None

            url = "https://api.howdies.app/api/upload"
            mime = 'image/gif' if file_type.lower() == 'gif' else 'image/png'
            
            # Requests needs a file-like object for upload
            upload_stream = io.BytesIO(final_bytes)
            
            files = {'file': (f'fast_up.{file_type}', upload_stream, mime)}
            data = {'token': token, 'uploadType': 'image', 'UserID': user_id}
            
            # Session ka use karke Fast Upload
            resp = self.session.post(url, files=files, data=data, timeout=20)
            
            if resp.status_code == 200:
                res = resp.json()
                return res.get('url') or res.get('data', {}).get('url')
            else:
                print(f"[Utils] Upload Fail: {resp.text}")
        except Exception as e:
            print(f"[Utils] Upload Error: {e}")
            traceback.print_exc()
        return None

    # ---------------------------------------------------------
    # 🎨 ASSET MANAGER (Emoji & Stickers)
    # ---------------------------------------------------------

    def get_emoji(self, char, size=64):
        """🔥 Emoji ko PNG Image banata hai (Internet se)"""
        try:
            # Unicode to Hex code (e.g. 🔥 -> 1f525)
            code = "-".join(f"{ord(c):x}" for c in char)
            url = f"https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{code}.png"
            img = self.download_image(url)
            if img:
                return img.resize((size, size), Image.Resampling.LANCZOS)
        except:
            pass
        return None

    def get_sticker(self, name, size=100):
        """Naam se Sticker uthata hai (e.g. 'laugh', 'fire')"""
        url = STICKER_PACK.get(name.lower())
        if url:
            img = self.download_image(url)
            if img:
                return img.resize((size, size), Image.Resampling.LANCZOS)
        return None

    # ---------------------------------------------------------
    # 🖌️ GRAPHICS ENGINE (The Artist)
    # ---------------------------------------------------------

    def get_font(self, size):
        key = f"font_{size}"
        if key in self._font_cache: return self._font_cache[key]
        
        font = ImageFont.load_default()
        for path in FONT_PATHS:
            try:
                font = ImageFont.truetype(path, size)
                break
            except: continue
        
        self._font_cache[key] = font
        return font

    def circle_crop(self, img, size=None):
        """Avatar Gol (Round) karta hai"""
        if size: img = img.resize((size, size), Image.Resampling.LANCZOS)
        else: size = min(img.size)
        
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        
        output = Image.new('RGBA', (size, size), (0,0,0,0))
        output.paste(img, (0,0), mask)
        return output

    def rounded_rect(self, width, height, radius, color, outline=None, outline_width=0):
        """Smooth Rounded Card Banata hai"""
        factor = 4 # High Quality Anti-Aliasing
        w, h = width * factor, height * factor
        r = radius * factor
        ow = outline_width * factor
        
        img = Image.new('RGBA', (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0, 0, w, h], radius=r, fill=color, outline=outline, width=ow)
        
        return img.resize((width, height), Image.Resampling.LANCZOS)

    def draw_text(self, draw_obj, xy, text, size=20, color="white", align="left", shadow=False):
        """Shadow ke sath Text likhta hai"""
        font = self.get_font(size)
        x, y = xy
        anchor = "la"
        if align == "center": anchor = "mm"
        elif align == "right": anchor = "ra"
        
        if shadow:
            draw_obj.text((x+2, y+2), text, font=font, fill=(0,0,0,180), anchor=anchor)
        
        draw_obj.text((x, y), text, font=font, fill=color, anchor=anchor)

    def make_gradient(self, width, height, c1, c2):
        """Vertical Gradient Background"""
        base = Image.new('RGB', (width, height), c1)
        top = Image.new('RGB', (width, height), c2)
        mask = Image.new('L', (width, height))
        mask_data = []
        for y in range(height):
            mask_data.extend([int(255 * (y / height))] * width)
        mask.putdata(mask_data)
        base.paste(top, (0, 0), mask)
        return base

# --- SINGLETON INSTANCE (Memory Efficient) ---
utils_instance = HighPerformanceUtils()

# =========================================================
# --- ✅ PUBLIC COMMANDS (PLUGINS KE LIYE) ---
# =========================================================

# 1. Uploading
def upload(bot, image_data, ext='png'):
    """Image Upload karke URL deta hai - CRASH PROOF"""
    return utils_instance.upload_image_fast(
        image_data, 
        bot.token, 
        bot.user_id, 
        ext
    )

# 2. Asset Fetching
def get_image(url): return utils_instance.download_image(url)
def get_emoji(char, size=64): return utils_instance.get_emoji(char, size)
def get_sticker(name, size=100): return utils_instance.get_sticker(name, size)

def get_circle_avatar(url, size=100):
    img = utils_instance.download_image(url)
    if img: return utils_instance.circle_crop(img, size)
    return None

# 3. Graphics Tools
def create_canvas(w, h, color=(20,20,20)): return Image.new('RGBA', (w, h), color)
def get_gradient(w, h, c1, c2): return utils_instance.make_gradient(w, h, c1, c2)
def draw_rounded_card(w, h, r, col, out=None, wth=0): return utils_instance.rounded_rect(w, h, r, col, out, wth)
def write_text(draw, xy, text, size=20, col="white", align="left", shadow=True): 
    utils_instance.draw_text(draw, xy, text, size, col, align, shadow)

# 4. Background Task
def run_in_bg(task, *args): return utils_instance.run_async(task, *args)
