import os
import sys
import subprocess
import time
import threading

# Force the working directory to be the script's directory
# This ensures that relative paths (like static/ or ../models) work correctly
# regardless of where the command is run from.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    from pyngrok import ngrok
except ImportError:
    print("Installing pyngrok...")
    install("pyngrok")
    from pyngrok import ngrok

from app import app

def run_app():
    # Disable reloader to avoid main thread issues
    app.run(port=5001, use_reloader=False)

if __name__ == "__main__":
    print("----------------------------------------------------------------")
    print("Starting Mob Violation App with Public Access...")
    print("----------------------------------------------------------------")

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_app)
    flask_thread.daemon = True
    flask_thread.start()

    # Give Flask a second to start
    time.sleep(2)

    try:
        # Open a HTTP tunnel on the default port 5001
        public_url = ngrok.connect(5001).public_url
        print("\n" + "="*60)
        print(f" >> PUBLIC URL: {public_url}")
        print(f" >> SEND THIS LINK TO YOUR CLIENT")
        print("="*60 + "\n")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        print("If you see an authentication error, you may need to sign up at ngrok.com and run: ngrok config add-authtoken <token>")
