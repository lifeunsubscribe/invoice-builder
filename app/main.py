import os
import sys
import socket
import threading
import time
import webbrowser
from flask import Flask

def get_base_paths():
    """
    Resolve config and dist paths for both dev and PyInstaller environments.

    In dev: config.json and .env are in project root, dist/ is sibling to app/
    In PyInstaller: config.json and .env are next to the .exe, dist/ is bundled into _MEIPASS
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        base_dir = os.path.dirname(sys.executable)
        dist_folder = os.path.join(sys._MEIPASS, 'dist')
    else:
        # Running in dev mode
        app_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(app_dir)
        dist_folder = os.path.join(base_dir, 'dist')

    return base_dir, dist_folder

def is_port_available(port):
    """
    Check if a port is available by attempting to bind to it.
    Returns True if port is available, False if occupied.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('localhost', port))
        sock.close()
        return True
    except OSError:
        return False

def find_available_port(start_port=5000, max_attempts=11):
    """
    Find an available port starting from start_port.
    Tries ports from start_port to start_port + max_attempts - 1.
    Returns port number if found, None otherwise.
    """
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    return None

def open_browser(port):
    """
    Open the default browser to the Flask app URL after a short delay.
    Delay allows Flask server to fully initialize.
    """
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{port}")

# Get paths for current environment
BASE_DIR, DIST_FOLDER = get_base_paths()

# Create Flask app with static file serving from dist/
app = Flask(__name__, static_folder=DIST_FOLDER, static_url_path="")

@app.route("/")
def index():
    """Serve the React app's index.html as the entry point."""
    return app.send_static_file("index.html")

# Blueprint registration placeholders (Phase 1-3)
# from app.api.config_api import config_bp
# from app.api.scan_api import scan_bp
# from app.api.submit_api import submit_bp
# app.register_blueprint(config_bp)
# app.register_blueprint(scan_bp)
# app.register_blueprint(submit_bp)

if __name__ == "__main__":
    # Check if app is already running on default port range
    port = find_available_port(5000, 11)

    if port is None:
        print("ERROR: No available ports in range 5000-5010. Please close other applications.")
        sys.exit(1)

    # If port is not 5000, another instance might be running
    if port != 5000:
        print(f"Port 5000 is occupied. Checking if it's another instance of this app...")
        # Open browser to existing instance and exit
        webbrowser.open("http://localhost:5000")
        print("Opened browser to existing instance on port 5000. Exiting.")
        sys.exit(0)

    # Launch browser in background thread
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Start Flask server
    print(f"Starting Lisa Invoice Builder on port {port}...")
    print(f"Config directory: {BASE_DIR}")
    print(f"Static files directory: {DIST_FOLDER}")
    app.run(port=port, debug=False)
