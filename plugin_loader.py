import os
import importlib.util
import sys
import traceback

PLUGIN_DIR = "plugins"

class PluginManager:
    def __init__(self, bot):
        self.bot = bot
        self.plugins = {} 
        if not os.path.exists(PLUGIN_DIR): os.makedirs(PLUGIN_DIR)

    def load_plugins(self):
        loaded = []
        self.plugins.clear()
        for filename in os.listdir(PLUGIN_DIR):
            if filename.endswith(".py"):
                name = filename[:-3]
                try:
                    self.load_plugin(name)
                    loaded.append(name)
                except Exception as e:
                    print(f"[Plugins] Error {name}: {e}")
        return loaded

    def load_plugin(self, name):
        path = os.path.join(PLUGIN_DIR, f"{name}.py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        if hasattr(module, 'setup'): module.setup(self.bot)
        self.plugins[name] = module

    def process_message(self, data):
        """
        Ye function raw data leta hai, parse karta hai,
        aur plugins ko 'raw_data' ke sath call karta hai.
        """
        text = data.get("text", "")
        room_id = data.get("roomid")
        user = data.get("username", "Unknown")
        
        if not text: return

        # Parse Command
        cmd = ""
        args = []
        if text.startswith("!"):
            parts = text[1:].split(" ")
            cmd = parts[0]
            args = parts[1:]
        else:
            cmd = text.strip() # For game inputs
        
        # Dispatch to Plugins
        for name, module in self.plugins.items():
            if hasattr(module, 'handle_command'):
                try:
                    # NEW STANDARD: Pass 'data' as the last argument
                    # Plugins can access data['userid'], data['avatar'], etc.
                    if module.handle_command(self.bot, cmd, room_id, user, args, data):
                        return True
                except Exception as e:
                    print(f"[Plugin Error] {name}: {e}")
                    traceback.print_exc()
        return False
