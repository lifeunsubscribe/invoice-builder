import os
import sys
import json
from flask import Blueprint, jsonify, request

config_bp = Blueprint('config', __name__, url_prefix='/api')

def get_config_path():
    """
    Resolve config.json path for both dev and PyInstaller environments.
    Matches the path resolution logic from main.py.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - config.json is next to .exe
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running in dev mode - config.json is in project root
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_dir = os.path.dirname(app_dir)

    return os.path.join(base_dir, 'config.json')

def derive_save_folder(full_name):
    """
    Derive save folder path from user's full name.

    Logic matches frontend deriveSaveFolder (App.jsx lines 26-32):
    - Split name by whitespace, filter empty strings
    - If less than 2 parts (single name): ~/Documents/{name}-invoices
    - Otherwise: ~/Documents/{first}-{last-initial}-invoices

    Examples:
    - "Lisa Wadley" -> "~/Documents/lisa-w-invoices"
    - "Lisa Marie Wadley" -> "~/Documents/lisa-w-invoices"
    - "Jane" -> "~/Documents/jane-invoices"
    """
    parts = full_name.strip().split()
    parts = [p for p in parts if p]  # Filter empty strings

    if len(parts) < 2:
        # Single name edge case
        name = (parts[0] if parts else "user").lower()
        return f"~/Documents/{name}-invoices"

    # Multiple parts: first name + first letter of last part
    first = parts[0].lower()
    last = parts[-1]
    return f"~/Documents/{first}-{last[0].lower()}-invoices"

@config_bp.route('/config', methods=['GET'])
def get_config():
    """
    GET /api/config

    Returns the contents of config.json.
    Returns 500 error if file is missing or invalid JSON.
    """
    config_path = get_config_path()

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        return jsonify(config_data), 200
    except FileNotFoundError:
        return jsonify({
            "error": "Configuration file not found",
            "message": "config.json does not exist"
        }), 500
    except json.JSONDecodeError:
        return jsonify({
            "error": "Invalid JSON in configuration file",
            "message": "The configuration file contains malformed JSON"
        }), 500
    except Exception:
        return jsonify({
            "error": "Failed to read configuration",
            "message": "An error occurred while reading the configuration file"
        }), 500

@config_bp.route('/config', methods=['POST'])
def update_config():
    """
    POST /api/config

    Accepts JSON payload and writes it to config.json.
    Returns 400 for invalid JSON, 500 for write errors.
    """
    config_path = get_config_path()

    try:
        # Flask automatically parses JSON if Content-Type is application/json
        # request.json will be None if parsing fails
        config_data = request.get_json()

        if config_data is None:
            return jsonify({
                "error": "Invalid JSON",
                "message": "Request body must be valid JSON"
            }), 400

        # Validate that config is a dict (not array or primitive)
        if not isinstance(config_data, dict):
            return jsonify({
                "error": "Invalid configuration format",
                "message": "Configuration must be a JSON object"
            }), 400

        # Add size limit (1MB) to prevent abuse
        config_json = json.dumps(config_data)
        if len(config_json.encode('utf-8')) > 1024 * 1024:
            return jsonify({
                "error": "Configuration too large",
                "message": "Configuration must be less than 1MB"
            }), 400

        # Write to config.json
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        return jsonify({
            "success": True,
            "message": "Configuration saved successfully"
        }), 200

    except Exception:
        return jsonify({
            "error": "Failed to write configuration",
            "message": "An error occurred while saving the configuration"
        }), 500
