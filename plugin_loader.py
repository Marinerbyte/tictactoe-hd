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
        Yeh function chat messages ko process karke plugins tak bhejta hai.
        """
        text = data.get("text", "")
        room_id = data.get("roomid")
        user = data.get("username", "Unknown")
        
        if not text: return

        # Command Parse Karta Hai
        cmd = ""
        args = []
        if text.startswith("!"):
            parts = text[1:].split(" ")
            cmd = parts[0]
            args = parts[1:]
        else:
            cmd = text.strip()
        
        # Plugins ko Command Bhejta Hai
        for name, module in self.plugins.items():
            if hasattr(module, 'handle_command'):
                try:
                    if module.handle_command(self.bot, cmd, room_id, user, args, data):
                        return True
                except Exception as e:
                    print(f"[Plugin Error] {name}: {e}")
                    traceback.print_exc()
        return False

    # --- NEW ---
    def process_system_message(self, data):
        """
        Yeh naya function hai jo non-chat messages (jaise 'roleslist') ko
        seedhe sabhi plugins ke paas bhejta hai.
        """
        for name, module in self.plugins.items():
            # Hum check karenge ki plugin me 'handle_system_message' naam ka function hai ya nahi.
            # Sirf 'admin.py' me hi yeh function hoga.
            if hasattr(module, 'handle_system_message'):
                try:
                    # Agar function hai, to data usko de do.
                    module.handle_system_message(self.bot, data)
                except Exception as e:
                    print(f"[Plugin System Error] {name}: {e}")
                    traceback.print_exc()
    # --- END NEW ---
