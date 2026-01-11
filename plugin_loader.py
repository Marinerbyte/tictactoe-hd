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

    # ──────────────────────────────────────────
    # Load all plugins
    # ──────────────────────────────────────────

    def load_plugins(self):
        loaded = []

        for filename in os.listdir(PLUGIN_DIR):
            if not filename.endswith(".py"):
                continue

            plugin_name = filename[:-3]

            try:
                self.load_plugin(plugin_name)
                loaded.append(plugin_name)
            except Exception as e:
                print(f"[Plugins] Failed to load {plugin_name}: {e}")
                traceback.print_exc()

        return loaded

    # ──────────────────────────────────────────
    # Load single plugin
    # ──────────────────────────────────────────

    def load_plugin(self, name):
        path = os.path.join(PLUGIN_DIR, f"{name}.py")

        if not os.path.isfile(path):
            raise FileNotFoundError(path)

        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)

        sys.modules[name] = module
        spec.loader.exec_module(module)

        # Optional setup(bot)
        if hasattr(module, "setup"):
            module.setup(self.bot)

        self.plugins[name] = module
        print(f"[Plugins] Loaded: {name}")

    # ──────────────────────────────────────────
    # Unload plugin
    # ──────────────────────────────────────────

    def unload_plugin(self, name):
        if name not in self.plugins:
            return False

        del self.plugins[name]

        if name in sys.modules:
            del sys.modules[name]

        print(f"[Plugins] Unloaded: {name}")
        return True

    # ──────────────────────────────────────────
    # Command dispatcher (UPDATED)
    # ──────────────────────────────────────────

    def handle_command(self, cmd, room, user, args, avatar_url=None):
        """
        Dispatch command to plugins.

        Plugin handle_command signature:
        handle_command(bot, cmd, room, user, args, avatar_url=None) -> bool
        """

        for name, module in self.plugins.items():
            if not hasattr(module, "handle_command"):
                continue

            try:
                handled = module.handle_command(
                    self.bot,
                    cmd,
                    room,
                    user,
                    args,
                    avatar_url
                )

                if handled:
                    return True

            except TypeError:
                # Backward compatibility (old plugins without avatar_url)
                try:
                    handled = module.handle_command(
                        self.bot,
                        cmd,
                        room,
                        user,
                        args
                    )
                    if handled:
                        return True
                except Exception as e:
                    print(f"[Plugin Error] {name}: {e}")
                    traceback.print_exc()

            except Exception as e:
                print(f"[Plugin Error] {name}: {e}")
                traceback.print_exc()

        return False
