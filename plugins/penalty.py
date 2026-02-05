import random
import math
import io
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# --- CONFIGURATION ---
W, H = 700, 700
TURF_COLORS = [(15, 45, 15), (30, 80, 30)]  # Deep turf green
NEON_PINK = "#EC4899"
NEON_BLUE = "#4facfe"
GOLD = "#FFD700"

# Target Coordinates for Ball/Goalie
POS_MAP = {
    1: {"ball": (180, 280), "gk": (180, 260)},  # Left
    2: {"ball": (350, 260), "gk": (350, 260)},  # Center
    3: {"ball": (520, 280), "gk": (520, 260)}   # Right
}

SHOOTER_POS = (350, 600) # Starting point of the ball

class PenaltyVisuals:
    @staticmethod
    def get_gradient_canvas(w, h, c1, c2):
        base = Image.new('RGB', (w, h), c1)
        top = Image.new('RGB', (w, h), c2)
        mask = Image.new('L', (w, h))
        for y in range(h):
            mask.putpixel((0, y), int(255 * (y / h)))
        mask = mask.resize((w, h))
        base.paste(top, (0, 0), mask)
        return base.convert("RGBA")

    @staticmethod
    def draw_motion_trail(draw, start, end, color):
        """Draws a cinematic trail from shooter to target"""
        steps = 10
        for i in range(steps):
            t = i / steps
            curr_x = start[0] + (end[0] - start[0]) * t
            curr_y = start[1] + (end[1] - start[1]) * t
            size = int(10 + (20 * t))
            opacity = int(150 * t)
            draw.ellipse([curr_x-size, curr_y-size, curr_x+size, curr_y+size], 
                         fill=(*color, opacity))

    @staticmethod
    def draw_impact_glow(img, pos, color):
        """Creates a soft flash/glow effect at the impact point"""
        glow = Image.new("RGBA", (W, H), (0,0,0,0))
        d = ImageDraw.Draw(glow)
        for r in range(100, 0, -10):
            alpha = int(100 * (1 - r/100))
            d.ellipse([pos[0]-r, pos[1]-r, pos[0]+r, pos[1]+r], fill=(*color, alpha))
        glow = glow.filter(ImageFilter.GaussianBlur(15))
        return Image.alpha_composite(img, glow)

    @staticmethod
    def create_card(username, user_av, result="VS", user_pos=None, bot_pos=None):
        # 1. Base Background
        img = PenaltyVisuals.get_gradient_canvas(W, H, TURF_COLORS[0], TURF_COLORS[1])
        d = ImageDraw.Draw(img, 'RGBA')

        # Border Color Logic
        border_col = (255, 255, 255)
        if result == "GOAL": border_col = (0, 255, 127) # Spring Green
        if result == "SAVED": border_col = (255, 68, 68) # Red

        # 2. Goal Area
        gx1, gy1, gx2, gy2 = 120, 180, 580, 450
        # Shadow/Depth
        d.rectangle([gx1+5, gy1+5, gx2+5, gy2+5], fill=(0,0,0,80))
        # Goal Frame Neon
        d.rectangle([gx1, gy1, gx2, gy2], outline=(*border_col, 200), width=6)
        # Net Pattern
        for i in range(gx1, gx2, 20): d.line([i, gy1, i, gy2], fill=(255,255,255,30), width=1)
        for i in range(gy1, gy2, 20): d.line([gx1, i, gx2, i], fill=(255,255,255,30), width=1)

        # 3. Goalkeeper Visuals
        gk_x, gk_y = POS_MAP[bot_pos or 2]["gk"]
        # Diver blur effect if result is SAVED
        gk_glow_col = (255, 255, 255, 100) if result != "SAVED" else (255, 0, 0, 150)
        d.ellipse([gk_x-90, gk_y-90, gk_x+90, gk_y+90], outline=gk_glow_col, width=4)
        
        # Placeholder for Goalkeeper Avatar (Bot)
        d.ellipse([gk_x-75, gk_y-75, gk_x+75, gk_y+75], fill=(40, 40, 50))
        d.text((gk_x, gk_y), "GK", fill="white", anchor="mm")

        # 4. Action Logic (Ball & Trails)
        if user_pos:
            target_xy = POS_MAP[user_pos]["ball"]
            
            if result == "GOAL":
                # Ball trail
                PenaltyVisuals.draw_motion_trail(d, SHOOTER_POS, target_xy, (255, 255, 255))
                # Celebration particles
                for _ in range(30):
                    px, py = random.randint(gx1, gx2), random.randint(gy1, gy2)
                    d.point((px, py), fill=random.choice(["#white", "#FFD700", "#00FF7F"]))
                # Net Impact Glow
                img = PenaltyVisuals.draw_impact_glow(img, target_xy, (255, 255, 255))
            
            # Draw Ball (⚽)
            ball_size = 40
            d.ellipse([target_xy[0]-ball_size, target_xy[1]-ball_size, 
                       target_xy[0]+ball_size, target_xy[1]+ball_size], fill="white")
            d.text(target_xy, "⚽", fill="black", anchor="mm", font_size=40)

        # 5. SAVED Specific Visuals (Darken overlay)
        if result == "SAVED":
            dark_ov = Image.new("RGBA", (W, H), (0,0,0,100))
            img = Image.alpha_composite(img, dark_ov)
            d = ImageDraw.Draw(img)

        # 6. Player Avatar Section (Bottom)
        ux, uy = 80, 580
        # Multi-ring border
        d.ellipse([ux-70, uy-70, ux+70, uy+70], outline=GOLD, width=5)
        d.ellipse([ux-62, uy-62, ux+62, uy+62], outline="white", width=2)
        # Placeholder for user avatar
        d.ellipse([ux-60, uy-60, ux+60, uy+60], fill=(60, 60, 80))
        # Username
        d.text((ux, uy+85), username.upper(), fill="white", anchor="mm")

        # 7. Cinematic Result Overlay
        if result != "VS":
            res_col = "#00FF7F" if result == "GOAL" else "#FF4444"
            # Text Shadow
            d.text((W//2 + 4, H//2 + 4), result, fill=(0,0,0,150), anchor="mm", font_size=120)
            # Main Text
            d.text((W//2, H//2), result, fill=res_col, anchor="mm", font_size=120)
            # Subtext
            d.text((W//2, H//2 + 80), "STRIKE COMPLETE", fill="white", anchor="mm", font_size=25)

        # 8. Final Card Polish (Rounded edges)
        mask = Image.new('L', (W, H), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle([0, 0, W, H], radius=50, fill=255)
        
        final_img = Image.new("RGBA", (W, H), (0,0,0,0))
        final_img.paste(img, (0,0), mask)
        
        # Soft Outer Glow
        draw_glow = ImageDraw.Draw(final_img)
        draw_glow.rounded_rectangle([2, 2, W-2, H-2], radius=50, outline=(*border_col, 100), width=4)
        
        return final_img

# --- EXAMPLE USAGE ---
# visual = PenaltyVisuals.create_card("Striker07", None, "GOAL", user_pos=3, bot_pos=1)
# visual.show()
