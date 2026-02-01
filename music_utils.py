import yt_dlp
import asyncio

async def get_stream_url(url):
    """YouTube URL se real audio streaming link nikalta hai"""
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    try:
        # Pura loop naya banate hain safety ke liye
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(options) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
            return info['url'], info.get('title', 'Audio Track')
    except Exception as e:
        print(f"YT-DLP Error: {e}")
        return None, None
