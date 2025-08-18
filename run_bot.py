import sys
from vfbot import Bot

def parse_arguments():
    """Parse command line arguments and return a dictionary"""
    args = {}
    
    # Check for help argument first
    if len(sys.argv) == 1 or 'help' in sys.argv or '-h' in sys.argv or '--help' in sys.argv:
        from vfbot.bot import print_help
        print_help()
        sys.exit(0)
    
    for arg in sys.argv[1:]:
        if '=' in arg:
            key, value = arg.split('=', 1)
            args[key] = value
        else:
            print(f"Warning: Invalid argument format '{arg}'. Arguments should be in format KEY=VALUE")
            print("Use 'help' or '--help' for usage information.")
            sys.exit(1)
    
    return args

if __name__ == "__main__":
    try:
        args = parse_arguments()
        bot = Bot()
        bot.run(**args)
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"Error starting bot: {e}")
        sys.exit(1)