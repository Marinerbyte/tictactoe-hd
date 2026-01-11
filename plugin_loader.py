import os
import importlib.util
import sys
import traceback

PLUGIN_DIR = "plugins"

class PluginManager:
    def __init__(self, bot):
        self.bot = bot
        self.plugins = {}  # {name: module}
        if not os.path.exists(PLUGIN_DIR):
            os.makedirs(PLUGIN_DIR)

    def load_plugins(self):
        loaded = []
        self.plugins.clear()
        for filename in os.listdir(PLUGIN_DIR):
            if filename.endswith(".py"):
                plugin_name = filename[:-3]
                try:
                    self.load_plugin(plugin_name)
                    loaded.append(plugin_name)
                except Exception as e:
                    print(f"[Plugins] Error loading {plugin_name}: {e}")
        return loaded

    def load_plugin(self, name):
        path = os.path.join(PLUGIN_DIR, f"{name}.py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        if hasattr(module, 'setup'):
            module.setup(self.bot)
        self.plugins[name] = module
        print(f"[Plugins] Loaded {name}")

    def unload_plugin(self, name):
        if name in self.plugins:
            del self.plugins[name]
            if name in sys.modules:
                del sys.modules[name]
            return True
        return False

    def handle_command(self, command, room_id, user, args, avatar_url=None, **kwargs):
        """Dispatch commands to loaded plugins safely with avatar support"""
        for name, module in self.plugins.items():
            if hasattr(module, 'handle_command'):
                try:
                    try:
                        # Try passing avatar_url (new plugins)
                        if module.handle_command(self.bot, command, room_id, user, args, avatar_url):
                            return True
                    except TypeError:
                        # Fallback for old plugins
                        if module.handle_command(self.bot, command, room_id, user, args):
                            return True
                except Exception as e:
                    print(f"[Plugin Error] {name}: {e}")
                    traceback.print_exc()
        return False
