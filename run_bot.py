import sys
from vfbot import Bot

args = {}
for arg in sys.argv[1:]:
    if '=' in arg:
        key, value = arg.split('=', 1)
        args[key] = value

bot = Bot()
bot.run(**args)