import io
import requests
import threading
import traceback
from PIL import Image, ImageDraw, ImageFont

# --- CONFIG ---
CACHE_SIZE = 200
_img_cache = {} 
lock = threading.Lock()

# ==========================================
# 🛠️ THE ULTIMATE IMAGE DOWNLOADER
# ==========================================
def get_image(url):
    """
    Downloads User DP specifically for Howdies CDN.
    Handles redirects and missing extensions.
    """
    if not url: return None
    
    # 1. Check RAM Cache (Agar pehle download kiya hai to wahi use karo)
    with lock:
        if url in _img_cache: 
            return _img_cache[url].copy()

    try:
        # 2. Browser Headers (Bahut Zaroori)
        # Iske bina server request reject kar deta hai
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Referer': 'https://howdies.app/'
        }
        
        # 3. Download Request
        # stream=True rakha hai taaki badi file memory na khaye
        response = requests.get(url, headers=headers, timeout=5, stream=True)
        
        if response.status_code == 200:
            # 4. Open Image safely
            img_data = io.BytesIO(response.content)
            img = Image.open(img_data)
            
            # 5. Convert to RGBA (Transparent layer fix)
            # Baaz dafa image 'P' mode me hoti hai jo crash karati hai
            img = img.convert("RGBA")
            
            # 6. Save to Cache
            with lock:
                if len(_img_cache) > CACHE_SIZE:
                    _img_cache.pop(next(iter(_img_cache)))
                _img_cache[url] = img
                
            return img
        else:
            print(f"[LudoUtils] Image Download Failed: Status {response.status_code}")
            
    except Exception as e:
        print(f"[LudoUtils] Image Error: {e}")
        
    return None

# ==========================================
# 🚀 ROBUST UPLOAD (Timeout Fixed)
# ==========================================
def upload(bot, image_data, ext='png'):
    try:
        if image_data is None: return None
        
        img_byte_arr = io.BytesIO()
        image_data.save(img_byte_arr, format=ext.upper())
        img_bytes = img_byte_arr.getvalue()

        url = "https://api.howdies.app/api/upload"
        files = {'file': (f'board.{ext}', img_bytes, 'image/png')}
        data = {
            'token': bot.token, 
            'uploadType': 'image', 
            'UserID': bot.user_id if bot.user_id else 0
        }
        
        # 45 Second Timeout (Render slow net handle karne ke liye)
        r = requests.post(url, files=files, data=data, timeout=45)
        
        if r.status_code == 200:
            res = r.json()
            return res.get('url') or res.get('data', {}).get('url')
        return None
    except:
        return None

# ==========================================
# 🎨 GRAPHICS HELPERS
# ==========================================
def create_canvas(w, h, color):
    return Image.new('RGBA', (w, h), color)

def circle_crop(img, size):
    """Image ko gol katne ka best tareeka"""
    if img is None: return None
    try:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new('L', (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        out = Image.new('RGBA', (size, size), (0,0,0,0))
        out.paste(img, (0,0), mask)
        return out
    except: return None

def write_text(d, xy, text, size=20, col="white", align="left", shadow=False):
    try: font = ImageFont.truetype("arial.ttf", size)
    except: font = ImageFont.load_default()
    x, y = xy
    if align == "center":
        w = len(text) * (size * 0.5)
        if hasattr(font, 'getlength'): w = font.getlength(text)
        x -= w // 2
    if shadow: d.text((x+2, y+2), text, font=font, fill="black")
    d.text((x, y), text, font=font, fill=col)

# Background Worker
def run_in_bg(task, *args):
    t = threading.Thread(target=task, args=args)
    t.daemon = True
    t.start()
