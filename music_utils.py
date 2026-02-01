import yt_dlp
import asyncio

async def get_stream_url(query):
    """Gane ka naam ya URL se real streaming link nikalta hai"""
    
    # Agar query URL nahi hai, to YouTube par search karo
    if not query.startswith("http"):
        query = f"ytsearch1:{query}"
        
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
    }
    
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(options) as ydl:
            # yt-dlp search karke result layega
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
            
            # Agar search result hai, to pehla item uthao
            if 'entries' in info:
                info = info['entries'][0]
                
            return info.get('url'), info.get('title', 'Audio Track')
    except Exception as e:
        print(f"YT-DLP Error: {e}")
        return None, None
