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
from flask import Flask, jsonify, request
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
    logger.info("Update check: local version = %r, exe=%s", local, sys.executable)
    if local == "dev":
        return jsonify({"updateAvailable": False, "currentVersion": "dev"}), 200
    # Skip update check if running from temp dir (just updated, waiting for copy back)
    import tempfile
    if getattr(sys, 'frozen', False) and sys.executable.startswith(tempfile.gettempdir()):
        logger.info("Running from temp dir, skipping update check")
        return jsonify({"updateAvailable": False, "currentVersion": local}), 200
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
    global _last_heartbeat, _shutdown_pending
    _last_heartbeat = time.time()
    _shutdown_pending = False
    return "", 204

@app.route("/api/self-update", methods=["POST"])
def self_update():
    """Download the latest exe and replace this one."""
    if not getattr(sys, 'frozen', False):
        return jsonify({"error": "Not supported in dev mode"}), 400
    import tempfile
    if sys.executable.startswith(tempfile.gettempdir()):
        return jsonify({"error": "Cannot update while running from temp dir"}), 400

    data = request.get_json() or {}
    download_url = data.get("downloadUrl", "")
    if not download_url:
        return jsonify({"error": "No download URL"}), 400

    exe_path = sys.executable
    exe_dir = os.path.dirname(exe_path)
    exe_name = os.path.basename(exe_path)
    # Use local temp dir to avoid OneDrive interference
    import tempfile
    update_dir = os.path.join(tempfile.gettempdir(), 'invoice-builder-update')
    # Clean out old update attempts
    import shutil
    if os.path.exists(update_dir):
        shutil.rmtree(update_dir, ignore_errors=True)
    os.makedirs(update_dir, exist_ok=True)
    new_exe = os.path.join(update_dir, exe_name)

    # Download the new exe using curl (built into Windows 10+, handles redirects reliably)
    try:
        import subprocess
        logger.info("Downloading update from %s", download_url)
        result = subprocess.run(
            ['curl.exe', '-L', '-o', new_exe, '-f', download_url],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0:
            logger.warning("curl download failed (exit %d): %s", result.returncode, result.stderr)
            return jsonify({"error": f"Download failed: {result.stderr}"}), 500
        import hashlib
        file_size = os.path.getsize(new_exe)
        with open(new_exe, 'rb') as f:
            file_data = f.read()
        header = file_data[:2]
        file_hash = hashlib.sha256(file_data).hexdigest()[:16]
        logger.info("Download complete: %d bytes, header=%r, sha256=%s, path=%s",
                     file_size, header, file_hash, new_exe)
        # Also log the currently running exe for comparison
        running_size = os.path.getsize(exe_path)
        with open(exe_path, 'rb') as f:
            running_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        logger.info("Currently running exe: %d bytes, sha256=%s, path=%s",
                     running_size, running_hash, exe_path)
        if header != b'MZ':
            logger.warning("Downloaded file is not a valid exe (header: %r)", header)
            os.remove(new_exe)
            return jsonify({"error": "Downloaded file is not a valid executable"}), 500
        if file_size < 10_000_000:
            os.remove(new_exe)
            return jsonify({"error": f"Download too small ({file_size} bytes), likely not a valid exe"}), 500
    except Exception as e:
        logger.warning("Download failed: %s", e)
        return jsonify({"error": f"Download failed: {e}"}), 500

    # Write a batch script in temp dir that swaps the exe after this process exits
    log_path = os.path.join(update_dir, "_update.log")
    old_exe = exe_path + ".old"
    bat_path = os.path.join(update_dir, "_update.bat")
    with open(bat_path, 'w') as f:
        f.write(f'''@echo off
echo Updating Invoice Builder... > "{log_path}"
echo Waiting for server to exit... >> "{log_path}"
timeout /t 5 /nobreak >nul

echo. >> "{log_path}"
echo --- Pre-swap diagnostics --- >> "{log_path}"
echo Old exe: "{exe_path}" >> "{log_path}"
for %%F in ("{exe_path}") do echo   size=%%~zF >> "{log_path}"
echo New exe: "{new_exe}" >> "{log_path}"
for %%F in ("{new_exe}") do echo   size=%%~zF >> "{log_path}"

echo. >> "{log_path}"
echo --- Swapping --- >> "{log_path}"
if exist "{old_exe}" del "{old_exe}" >nul 2>&1
set retries=0
:retry_rename
rename "{exe_path}" "{os.path.basename(old_exe)}" >nul 2>&1
if exist "{exe_path}" (
    set /a retries+=1
    echo Retry rename %retries%... >> "{log_path}"
    if %retries% GEQ 15 (
        echo Giving up after 15 retries >> "{log_path}"
        exit /b 1
    )
    timeout /t 2 /nobreak >nul
    goto retry_rename
)
echo Old exe renamed to .old >> "{log_path}"
echo Cleaning up old _MEI temp folders... >> "{log_path}"
for /d %%D in ("%TEMP%\\_MEI*") do rmdir /s /q "%%D" >nul 2>&1
echo Launching new exe from temp... >> "{log_path}"
start "" "{new_exe}"
echo Waiting for new exe to start... >> "{log_path}"
timeout /t 10 /nobreak >nul
echo Checking if server is running... >> "{log_path}"
curl.exe -s -o nul http://127.0.0.1:5001/ >nul 2>&1
if errorlevel 1 (
    echo CRASH DETECTED - server not responding >> "{log_path}"
    echo Restoring old exe... >> "{log_path}"
    if exist "{old_exe}" rename "{old_exe}" "{os.path.basename(exe_path)}" >nul 2>&1
    echo Saving crash log... >> "{log_path}"
    echo crash > "{os.path.join(exe_dir, '.crash_report_pending')}"
    copy /y "{log_path}" "{os.path.join(exe_dir, '.crash_log')}" >nul 2>&1
    echo Starting restored exe... >> "{log_path}"
    start "" "{exe_path}"
    exit /b 1
)
echo Copying new exe to desktop for next launch... >> "{log_path}"
copy /y "{new_exe}" "{exe_path}" >> "{log_path}" 2>&1
echo Cleaning up... >> "{log_path}"
del "{old_exe}" >nul 2>&1
if exist "{os.path.join(exe_dir, 'invoice_builder.log')}" del "{os.path.join(exe_dir, 'invoice_builder.log')}" >nul 2>&1
''')

    # Launch the update script and exit
    import subprocess
    logger.info("Self-update initiated, launching %s", bat_path)
    if sys.platform == 'win32':
        os.startfile(bat_path)
    else:
        subprocess.Popen(['bash', bat_path], start_new_session=True)
    logger.info("Batch script launched, exiting.")
    os._exit(0)

_shutdown_pending = False

@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    """Shut down the server when the user closes the app window.
    Delays 5 seconds so a reload can cancel via heartbeat."""
    global _shutdown_pending
    if _shutdown_pending:
        return "", 204
    _shutdown_pending = True
    logger.info("Shutdown requested, waiting 10s for possible reload...")
    def _delayed_shutdown():
        global _shutdown_pending
        time.sleep(10)
        if _shutdown_pending:
            logger.info("No reload detected, exiting.")
            os._exit(0)
    threading.Thread(target=_delayed_shutdown, daemon=True).start()
    return "", 204

def _heartbeat_watchdog():
    """Exit if no heartbeat received for 15 seconds after first ping."""
    global _last_heartbeat
    # Wait until the frontend has actually connected and sent a heartbeat
    while _last_heartbeat is None:
        time.sleep(1)
    while True:
        time.sleep(5)
        if time.time() - _last_heartbeat > 15:
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

def _check_and_send_crash_report():
    """If a previous update crashed, email the crash log to the developer."""
    if not getattr(sys, 'frozen', False):
        return
    exe_dir = os.path.dirname(sys.executable)
    marker = os.path.join(exe_dir, '.crash_report_pending')
    crash_log_path = os.path.join(exe_dir, '.crash_log')
    if not os.path.exists(marker):
        return
    logger.info("Crash report pending from failed update")
    crash_log = ""
    if os.path.exists(crash_log_path):
        with open(crash_log_path, 'r') as f:
            crash_log = f.read()
    try:
        from app.services.mail_service import send_invoice_email
        # Load config to get developer email
        config_path = os.path.join(exe_dir, 'config.json')
        dev_email = None
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            dev_email = config.get('personalEmail', '')
        if dev_email:
            subject = "Invoice Builder: Auto-update crash report"
            body = f"A self-update failed and was rolled back.\n\nCrash log:\n{crash_log}"
            # Send as plain text with a dummy PDF (mail service requires it)
            result = send_invoice_email(
                [dev_email], b'crash report', 'crash_log.txt', subject, body
            )
            if result.get('success'):
                logger.info("Crash report emailed to %s", dev_email)
            else:
                logger.warning("Failed to email crash report: %s", result.get('error'))
    except Exception as e:
        logger.warning("Could not send crash report: %s", e)
    # Clean up marker files regardless
    try:
        os.remove(marker)
        if os.path.exists(crash_log_path):
            os.remove(crash_log_path)
    except Exception:
        pass

if __name__ == "__main__":
    _check_and_send_crash_report()

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
