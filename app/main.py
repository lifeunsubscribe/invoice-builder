import os
import sys
import socket
import threading
import time
import webbrowser
import urllib.request
import urllib.error
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

def is_this_app_running_on_port(port):
    """
    Check if this specific Flask app is running on the given port.
    Returns True if the app is running on the port, False otherwise.

    Attempts to connect to the port and verify it's serving our React app
    by checking if the index.html endpoint responds successfully.
    """
    try:
        url = f"http://localhost:{port}/"
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=2) as response:
            # If we get a 200 response, check if it looks like our app
            # Our app serves index.html at the root, which should contain React-specific content
            content = response.read().decode('utf-8', errors='ignore')
            # Check for indicators that this is our React app
            # (looking for common React/Vite patterns in index.html)
            return ('<!doctype html>' in content.lower() or '<!DOCTYPE html>' in content) and \
                   ('div id="root"' in content or '<div id="root">' in content)
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout, ConnectionRefusedError):
        return False
    except Exception:
        # Any other error means it's not our app
        return False

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

# Configure Jinja2 to explicitly enable autoescape for XSS protection
app.jinja_env.autoescape = True

@app.route("/")
def index():
    """Serve the React app's index.html as the entry point."""
    return app.send_static_file("index.html")

# Blueprint registration
from app.api.config_api import config_bp
from app.api.scan_api import scan_bp

app.register_blueprint(config_bp)
app.register_blueprint(scan_bp)

# Phase 3 blueprints (to be added later)
# from app.api.submit_api import submit_bp
# app.register_blueprint(submit_bp)

if __name__ == "__main__":
    # Check if this app is already running on port 5000
    if not is_port_available(5000):
        if is_this_app_running_on_port(5000):
            print("Lisa Invoice Builder is already running on port 5000.")
            if not os.getenv('NO_BROWSER'):
                print("Opening browser to existing instance...")
                webbrowser.open("http://localhost:5000")
            print("Exiting.")
            sys.exit(0)
        else:
            print("Port 5000 is occupied by another application.")
            print("Looking for alternative port...")

    # Find an available port (will skip 5000 if occupied by another app)
    port = find_available_port(5000, 11)

    if port is None:
        print("ERROR: No available ports in range 5000-5010. Please close other applications.")
        sys.exit(1)

    # Launch browser in background thread (unless NO_BROWSER env var is set)
    if not os.getenv('NO_BROWSER'):
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Start Flask server
    print(f"Starting Lisa Invoice Builder on port {port}...")
    print(f"Config directory: {BASE_DIR}")
    print(f"Static files directory: {DIST_FOLDER}")
    app.run(port=port, debug=False)
