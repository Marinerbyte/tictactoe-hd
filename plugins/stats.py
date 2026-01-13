import sys
import os
import traceback
import math

# --- DB IMPORT ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import db
except Exception as e:
    print(f"DB Import Error: {e}")

# --- FONT CONVERTER ---
def fancy(text):
    """Converts text to Small Caps"""
    normal = "abcdefghijklmnopqrstuvwxyz"
    small  = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return text.lower().translate(trans)

# --- RANK SYSTEM ---
def get_rank(score):
    if score < 500: return "🥚 ɴᴇᴡʙɪᴇ"
    elif score < 2000: return "💸 ʜᴜsᴛʟᴇʀ"
    elif score < 5000: return "🛡️ ᴡᴀʀʀɪᴏʀ"
    elif score < 10000: return "🎩 ʙᴏss"
    elif score < 50000: return "👑 ᴋɪɴɢ"
    else: return "💎 ᴇᴍᴘᴇʀᴏʀ"

def handle_command(bot, command, room_id, user, args, data):
    user_id = data.get('userid', user) 
    cmd = command.lower().strip()
    ph = "%s" if db.DATABASE_URL.startswith("postgres") else "?"

    # --- 1. VIEW SCORE ---
    if cmd in ["score", "balance", "bal", "coins", "stats", "profile"]:
        target_uid = str(user_id)
        target_name = user

        try:
            conn = db.get_connection()
            cur = conn.cursor()

            # Get Global Stats
            cur.execute(f"SELECT global_score, wins FROM users WHERE user_id = {ph}", (target_uid,))
            row = cur.fetchone()

            if not row:
                # Auto-Register
                try:
                    cur.execute(f"INSERT INTO users (user_id, username, global_score, wins) VALUES ({ph}, {ph}, 0, 0)", (target_uid, target_name))
                    conn.commit()
                    global_score, total_wins = 0, 0
                except:
                    return True
            else:
                global_score, total_wins = row

            # Get Game Stats
            cur.execute(f"SELECT game_name, wins, earnings FROM game_stats WHERE user_id = {ph} ORDER BY earnings DESC", (target_uid,))
            game_rows = cur.fetchall()
            conn.close()

            rank_title = get_rank(global_score)

            # --- FANCY OUTPUT ---
            msg = f"👤 **{fancy('profile')}: @{target_name}**\n"
            msg += f"🏷️ **{fancy('rank')}:** {rank_title}\n"
            msg += f"💰 **{fancy('net worth')}:** {global_score}\n"
            msg += f"🏆 **{fancy('total wins')}:** {total_wins}\n"
            
            if game_rows:
                msg += "──────────────────\n"
                for g_name, g_wins, g_earn in game_rows:
                    icon = "🎮"
                    if "ludo" in g_name: icon = "🎲"
                    elif "tic" in g_name: icon = "❌"
                    elif "race" in g_name: icon = "🐎"
                    # Fancy Game Name
                    g_fancy = fancy(g_name)
                    msg += f"{icon} **{g_fancy}:** {g_earn} ({g_wins} ᴡɪɴs)\n"
            else:
                msg += f"\n_({fancy('play games to earn')})_"

            bot.send_message(room_id, msg)
            return True

        except Exception as e:
            traceback.print_exc()
            return True

    # --- 2. LEADERBOARD (PAGINATION ADDED) ---
    if cmd in ["top", "lb", "leaderboard"]:
        try:
            # Check Page Number (Default 1)
            page = 1
            if args and args[0].isdigit():
                page = int(args[0])
            
            if page < 1: page = 1
            limit = 10
            offset = (page - 1) * limit

            conn = db.get_connection()
            cur = conn.cursor()

            # Get Top 10 for specific page
            query = f"SELECT username, global_score FROM users ORDER BY global_score DESC LIMIT {limit} OFFSET {offset}"
            cur.execute(query)
            rows = cur.fetchall()
            
            # Check total count for pagination info
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()[0]
            conn.close()

            if not rows:
                bot.send_message(room_id, f"📉 {fancy('page empty')}.")
                return True

            total_pages = math.ceil(total_users / limit)
            
            # --- FANCY OUTPUT ---
            msg = f"🏆 **{fancy('global leaderboard')}** 🏆\n"
            msg += f"📄 {fancy('page')} {page}/{total_pages}\n"
            msg += "──────────────────\n"
            
            for idx, (name, score) in enumerate(rows):
                # Calculate actual rank based on page
                actual_rank = offset + idx + 1
                
                icon = "🔹"
                if actual_rank == 1: icon = "🥇"
                elif actual_rank == 2: icon = "🥈"
                elif actual_rank == 3: icon = "🥉"
                
                msg += f"{icon} `#{actual_rank}` **{name}**: {score}\n"

            # Footer for Next Page
            if page < total_pages:
                msg += "──────────────────\n"
                msg += f"👉 {fancy('type')} `!top {page+1}` {fancy('for next page')}"

            bot.send_message(room_id, msg)
            return True

        except Exception as e:
            traceback.print_exc()
            return True

    return False
