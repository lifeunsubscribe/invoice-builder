import json
import logging
import os
import sys
import socket
import threading
import time
import webbrowser
import urllib.request
import urllib.error
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

# On Windows PyInstaller bundles, point fontconfig at system fonts
# so WeasyPrint/Pango can find Georgia, emoji fonts, etc.
if getattr(sys, 'frozen', False) and sys.platform == 'win32':
    _fonts_conf = os.path.join(sys._MEIPASS, 'app', 'fonts.conf')
    if os.path.exists(_fonts_conf):
        os.environ['FONTCONFIG_FILE'] = _fonts_conf

from app.middleware.rate_limiter import get_rate_limiter
from app.middleware.request_validator import MAX_CONTENT_LENGTH_BYTES

if getattr(sys, 'frozen', False):
    # Log to file next to the exe so we can debug the packaged app
    _log_path = os.path.join(os.path.dirname(sys.executable), 'invoice_builder.log')
    logging.basicConfig(filename=_log_path, level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

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
    Uses SO_REUSEADDR so ports in TIME_WAIT (from a recent exit) are reusable.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

# Request size limits
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH_BYTES

# Rate limiting
limiter = get_rate_limiter()
limiter.init_app(app)

@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Handle all HTTP exceptions with JSON response."""
    # Log full exception details for debugging
    logger.warning("HTTP %d: %s", e.code, e)

    # Return generic message to avoid leaking internal details
    if 400 <= e.code < 500:
        generic_message = "The request could not be processed"
    else:
        generic_message = "An error occurred while processing your request"

    return jsonify({"error": e.name, "message": generic_message}), e.code

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors with JSON response."""
    # Log full exception details for debugging
    logger.warning("404: %s", e)
    # Return generic message to avoid leaking internal routing details
    return jsonify({"error": "Not found", "message": "The requested resource was not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors with JSON response."""
    logger.error("500: %s", e)
    return jsonify({"error": "Server error", "message": "An internal server error occurred"}), 500

@app.errorhandler(429)
def rate_limit_exceeded(e):
    """Handle 429 rate limit exceeded errors with JSON response."""
    logger.warning("Rate limit exceeded: %s", e)
    return jsonify({
        "error": "Rate limit exceeded",
        "message": "Too many requests. Please try again later."
    }), 429

@app.errorhandler(413)
def request_entity_too_large(e):
    """Handle 413 payload too large errors with JSON response."""
    logger.warning("Request too large: %s", e)
    return jsonify({
        "error": "Payload too large",
        "message": "Request body exceeds maximum allowed size"
    }), 413

_last_heartbeat = None  # None until first heartbeat received

# ── Update check ──────────────────────────────────────────────────────
DOWNLOAD_URL = "https://drive.google.com/file/d/1uQXorRDZiJPcaIId3_UBUN9JNOtGBbq5/view?usp=sharing"

def _get_local_version():
    """Read the baked-in build version."""
    if getattr(sys, 'frozen', False):
        ver_path = os.path.join(sys._MEIPASS, 'app', 'build_version.txt')
    else:
        ver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build_version.txt')
    try:
        with open(ver_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "dev"

@app.route("/api/check-update", methods=["GET"])
def check_update():
    """Check if a newer version is available on GitHub."""
    local = _get_local_version()
    logger.info("Update check: local version = %r", local)
    if local == "dev":
        return jsonify({"updateAvailable": False, "currentVersion": "dev"}), 200
    try:
        import ssl
        # PyInstaller bundles may not include CA certs; use unverified context
        if getattr(sys, 'frozen', False):
            ctx = ssl._create_unverified_context()
        else:
            ctx = ssl.create_default_context()
        req = urllib.request.Request(
            "https://api.github.com/repos/lifeunsubscribe/invoice-builder/releases/latest",
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "InvoiceBuilder"}
        )
        with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
            data = json.loads(resp.read().decode())
        remote = data.get("body", "").replace("Build ", "").strip()
        assets = data.get("assets", [])
        download_url = assets[0].get("browser_download_url", DOWNLOAD_URL) if assets else DOWNLOAD_URL
        if remote and remote != local:
            return jsonify({
                "updateAvailable": True,
                "currentVersion": local,
                "latestVersion": remote,
                "downloadUrl": download_url
            }), 200
    except Exception as e:
        logger.warning("Update check failed: %s", e)
    return jsonify({"updateAvailable": False, "currentVersion": local}), 200

@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    """Frontend pings this to signal it's still open."""
    global _last_heartbeat
    _last_heartbeat = time.time()
    return "", 204

@app.route("/api/self-update", methods=["POST"])
def self_update():
    """Download the latest exe and replace this one."""
    if not getattr(sys, 'frozen', False):
        return jsonify({"error": "Not supported in dev mode"}), 400

    data = request.get_json() or {}
    download_url = data.get("downloadUrl", "")
    if not download_url:
        return jsonify({"error": "No download URL"}), 400

    exe_path = sys.executable
    exe_dir = os.path.dirname(exe_path)
    exe_name = os.path.basename(exe_path)
    new_exe = os.path.join(exe_dir, exe_name + ".new")

    # Download the new exe
    try:
        import ssl
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(download_url, headers={"User-Agent": "InvoiceBuilder"})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            with open(new_exe, 'wb') as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
    except Exception as e:
        return jsonify({"error": f"Download failed: {e}"}), 500

    # Write a batch script that swaps the exe after this process exits
    bat_path = os.path.join(exe_dir, "_update.bat")
    with open(bat_path, 'w') as f:
        f.write(f'''@echo off
echo Updating Invoice Builder...
timeout /t 2 /nobreak >nul
del "{exe_path}"
move "{new_exe}" "{exe_path}"
del "{bat_path}" & start "" "{exe_path}"
''')

    # Launch the update script and exit
    import subprocess
    subprocess.Popen(['cmd', '/c', bat_path], creationflags=0x00000008)
    logger.info("Self-update initiated, exiting.")
    os._exit(0)

@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    """Shut down the server when the user closes the app window."""
    logger.info("Shutdown requested, exiting.")
    os._exit(0)

def _heartbeat_watchdog():
    """Exit if no heartbeat received for 60 seconds after first ping."""
    global _last_heartbeat
    # Wait until the frontend has actually connected and sent a heartbeat
    while _last_heartbeat is None:
        time.sleep(1)
    while True:
        time.sleep(5)
        if time.time() - _last_heartbeat > 60:
            logger.info("No heartbeat for 10s, exiting.")
            os._exit(0)

@app.route("/")
def index():
    """Serve the React app's index.html as the entry point."""
    if not os.path.exists(DIST_FOLDER):
        logger.error("Dist folder missing: %s", DIST_FOLDER)
        return jsonify({
            "error": "Static files not found",
            "message": "The frontend build directory does not exist. Run 'npm run build' in frontend/."
        }), 500

    index_path = os.path.join(str(DIST_FOLDER), "index.html")
    if not os.path.exists(index_path):
        logger.error("index.html not found in %s", DIST_FOLDER)
        return jsonify({
            "error": "Static file not found",
            "message": "index.html not found in the build directory. Run 'npm run build' in frontend/."
        }), 500

    try:
        return app.send_static_file("index.html")
    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.exception("index.html not found: %s", e)
        return jsonify({
            "error": "Static file not found",
            "message": "index.html is missing from the build directory"
        }), 500
    except PermissionError as e:
        logger.exception("Permission denied serving index.html: %s", e)
        return jsonify({
            "error": "Permission denied",
            "message": "Cannot read index.html due to insufficient permissions"
        }), 500
    except OSError as e:
        logger.exception("OS error serving index.html: %s", e)
        return jsonify({
            "error": "File system error",
            "message": "An error occurred reading the application files"
        }), 500
    except Exception as e:
        logger.exception("Unexpected error serving index.html: %s", e)
        return jsonify({
            "error": "Server error",
            "message": "An unexpected error occurred while serving the application"
        }), 500

# Blueprint registration
from app.api.config_api import config_bp
from app.api.scan_api import scan_bp
from app.api.submit_api import submit_bp
from app.api.email_config_api import email_config_bp

app.register_blueprint(config_bp)
app.register_blueprint(scan_bp)
app.register_blueprint(submit_bp)
app.register_blueprint(email_config_bp)

if __name__ == "__main__":
    # Check if this app is already running on port 5000
    if not is_port_available(5001):
        if is_this_app_running_on_port(5001):
            print("Lisa Invoice Builder is already running on port 5001.")
            if not os.getenv('NO_BROWSER'):
                print("Opening browser to existing instance...")
                webbrowser.open("http://localhost:5001")
            print("Exiting.")
            sys.exit(0)
        else:
            print("Port 5000 is occupied by another application.")
            print("Looking for alternative port...")

    # Find an available port (will skip 5000 if occupied by another app)
    port = find_available_port(5001, 10)

    if port is None:
        print("ERROR: No available ports in range 5000-5010. Please close other applications.")
        sys.exit(1)

    # Launch browser in background thread (unless NO_BROWSER env var is set)
    if not os.getenv('NO_BROWSER'):
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Start heartbeat watchdog — exits if browser stops pinging
    threading.Thread(target=_heartbeat_watchdog, daemon=True).start()

    # Start Flask server
    print(f"Starting Lisa Invoice Builder on port {port}...")
    print(f"Config directory: {BASE_DIR}")
    print(f"Static files directory: {DIST_FOLDER}")
    app.run(port=port, debug=False, threaded=True)
