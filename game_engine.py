import time
import threading

class GameEngine:
    def __init__(self, bot):
        self.bot = bot
        self.games = {} # {room_id: {game_type: 'xyz', state: {}, last_act: 0}}
        self.lock = threading.Lock()
        self.running = True
        
        # Start cleanup thread
        self.cleaner = threading.Thread(target=self.cleanup_loop, daemon=True)
        self.cleaner.start()

    def start_game(self, room_id, game_type, initial_data):
        with self.lock:
            self.games[room_id] = {
                "type": game_type,
                "state": initial_data,
                "players": {},
                "started_at": time.time(),
                "last_activity": time.time()
            }

    def update_game(self, room_id, user_id, action):
        with self.lock:
            if room_id in self.games:
                game = self.games[room_id]
                game["last_activity"] = time.time()
                game["players"][user_id] = game["players"].get(user_id, 0) + 1
                return game
        return None

    def end_game(self, room_id, reason="finished"):
        with self.lock:
            if room_id in self.games:
                game = self.games.pop(room_id)
                return game
        return None

    def get_game(self, room_id):
        return self.games.get(room_id)

    def cleanup_loop(self):
        while self.running:
            time.sleep(10)
            now = time.time()
            to_remove = []
            
            with self.lock:
                for room_id, game in self.games.items():
                    if now - game["last_activity"] > 90:
                        to_remove.append(room_id)
            
            for room_id in to_remove:
                game = self.end_game(room_id, "timeout")
                if game:
                    players = ", ".join(game["players"].keys())
                    msg = f"Game {game['type']} ended due to inactivity. Players: {players}"
                    self.bot.send_message(room_id, msg)
