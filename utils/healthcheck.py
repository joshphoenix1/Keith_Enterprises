"""Health check engine with auto-healing and background monitoring loop."""

import json
import os
import shutil
import socket
import threading
import time
import traceback
import importlib
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))

DEFAULT_ACCOUNTS = {
    "seller_assistant": {
        "enabled": False, "api_key": "", "plan": "Pro", "webhook_url": "",
        "google_sheet_id": "", "auto_sync": False, "sync_frequency": "Hourly",
        "sync_products": True, "sync_restrictions": True, "sync_ip_alerts": True,
        "sync_competitors": True, "account_email": "", "account_password": "",
    },
    "claude_code": {
        "enabled": False, "model": "claude-sonnet-4-6",
        "process_on_ingest": True, "auto_process": False,
        "tasks": ["summarize", "extract_metrics", "sentiment"],
    },
    "whatsapp": {
        "enabled": False, "bridge_url": "http://localhost:8085",
        "api_key": "keith-enterprises-wa-key", "phone_number": "",
        "auto_process_images": True, "notifications": True,
    },
    "email": {
        "enabled": False, "provider": "Gmail", "email_address": "",
        "smtp_server": "", "smtp_port": 587, "username": "", "password": "",
        "use_tls": True, "notifications": True,
    },
    "google_drive": {
        "enabled": False, "account_email": "", "client_id": "",
        "client_secret": "", "folder_id": "", "auto_backup": False,
        "backup_frequency": "Daily",
    },
}

REQUIRED_DEPS = ["dash", "plotly", "pandas", "dash_bootstrap_components", "anthropic"]

PAGE_MODULES = [
    "home", "inbox", "scanner", "offers",
    "buyers", "accounts", "health",
]

DATA_FILES_LIST = {
    "offers.json": [],
    "buyers.json": [],
    "activity.json": [],
    "inbox.json": {"messages": []},
    "scans.json": [],
    "accounts.json": DEFAULT_ACCOUNTS,
    "rules.json": {},
}


def _backup_corrupt(filepath):
    """Back up a corrupt file before overwriting."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{filepath}.corrupt.{ts}"
    try:
        shutil.copy2(filepath, backup)
        return backup
    except Exception:
        return None


class HealthChecker:
    def __init__(self, app=None, interval=60, max_log_entries=200):
        self._app = app
        self._interval = interval
        self._max_log_entries = max_log_entries
        self._log_path = os.path.join(DATA_DIR, "health_log.json")
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._lock = threading.Lock()
        self._latest_report = None

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=10)

    def get_latest(self):
        with self._lock:
            return self._latest_report

    def get_history(self, n=50):
        try:
            with open(self._log_path) as f:
                logs = json.load(f)
            return logs[-n:]
        except Exception:
            return []

    def run_checks_now(self):
        """Run all checks immediately (called from callback)."""
        report = self._run_all_checks()
        with self._lock:
            self._latest_report = report
        self._persist_report(report)
        return report

    def _run_loop(self):
        # Initial check after 5 seconds
        self._stop_event.wait(timeout=5)
        while not self._stop_event.is_set():
            report = self._run_all_checks()
            with self._lock:
                self._latest_report = report
            self._persist_report(report)
            self._stop_event.wait(timeout=self._interval)

    def _run_all_checks(self):
        start = time.time()
        checks = []

        # Category 1: Data file integrity
        checks.extend(self._check_data_files())

        # Category 2: Directory structure
        checks.extend(self._check_directories())

        # Category 3: Page imports
        checks.extend(self._check_page_imports())

        # Category 4: Page renders
        checks.extend(self._check_page_renders())

        # Category 5: Dependencies
        checks.extend(self._check_dependencies())

        # Category 6: OAuth / credentials
        checks.extend(self._check_oauth())

        # Category 6b: WhatsApp connection
        checks.extend(self._check_whatsapp())

        # Category 7: Port / process
        checks.extend(self._check_port())

        # Category 8: Disk space
        checks.extend(self._check_disk_space())

        # Category 9: Callback registration
        checks.extend(self._check_callbacks())

        # Determine overall status
        statuses = [c["status"] for c in checks]
        if "fail" in statuses:
            overall = "critical"
        elif "warn" in statuses:
            overall = "degraded"
        else:
            overall = "healthy"

        duration_ms = round((time.time() - start) * 1000)

        return {
            "timestamp": datetime.now().isoformat(),
            "duration_ms": duration_ms,
            "overall_status": overall,
            "total_checks": len(checks),
            "passed": sum(1 for c in checks if c["status"] == "pass"),
            "warnings": sum(1 for c in checks if c["status"] == "warn"),
            "failures": sum(1 for c in checks if c["status"] == "fail"),
            "healed": sum(1 for c in checks if c.get("healed")),
            "checks": checks,
        }

    def _check_result(self, name, category, status, message, healed=False, heal_action=None):
        return {
            "name": name,
            "category": category,
            "status": status,
            "message": message,
            "healed": healed,
            "heal_action": heal_action,
        }

    # ── Category 1: Data Files ──

    def _check_data_files(self):
        results = []
        for filename, default in DATA_FILES_LIST.items():
            filepath = os.path.join(DATA_DIR, filename)
            name = f"data:{filename}"

            if not os.path.exists(filepath):
                # Auto-heal: create with default
                try:
                    with open(filepath, "w") as f:
                        json.dump(default, f, indent=2)
                    results.append(self._check_result(
                        name, "data", "pass",
                        f"File was missing — created with defaults",
                        healed=True, heal_action=f"Created {filename} with defaults"))
                except Exception as e:
                    results.append(self._check_result(
                        name, "data", "fail",
                        f"Missing and could not create: {e}"))
                continue

            # Try to parse
            try:
                with open(filepath) as f:
                    raw = f.read()
                data = json.loads(raw)

                # Validate type
                if filename == "accounts.json":
                    if not isinstance(data, dict):
                        raise ValueError("Expected dict")
                    # Check for missing top-level keys
                    missing = [k for k in DEFAULT_ACCOUNTS if k not in data]
                    if missing:
                        for k in missing:
                            data[k] = DEFAULT_ACCOUNTS[k]
                        with open(filepath, "w") as f:
                            json.dump(data, f, indent=2)
                        results.append(self._check_result(
                            name, "data", "pass",
                            f"Added missing keys: {', '.join(missing)}",
                            healed=True, heal_action=f"Added keys: {', '.join(missing)}"))
                        continue
                elif filename == "inbox.json":
                    if not isinstance(data, dict) or "messages" not in data:
                        raise ValueError("Expected dict with 'messages' key")
                else:
                    if not isinstance(data, list):
                        raise ValueError("Expected list")

                # Count records
                if isinstance(data, list):
                    count = len(data)
                elif isinstance(data, dict) and "messages" in data:
                    count = len(data["messages"])
                else:
                    count = len(data)

                results.append(self._check_result(
                    name, "data", "pass", f"Valid JSON, {count} records"))

            except (json.JSONDecodeError, ValueError) as e:
                # Auto-heal: backup and restore
                backup = _backup_corrupt(filepath)
                try:
                    with open(filepath, "w") as f:
                        json.dump(default, f, indent=2)
                    backup_msg = f" Backup: {os.path.basename(backup)}" if backup else ""
                    results.append(self._check_result(
                        name, "data", "warn",
                        f"Was corrupt ({e}) — restored to defaults.{backup_msg}",
                        healed=True,
                        heal_action=f"Restored {filename} from corrupt state"))
                except Exception as e2:
                    results.append(self._check_result(
                        name, "data", "fail",
                        f"Corrupt and could not restore: {e2}"))

            except Exception as e:
                results.append(self._check_result(
                    name, "data", "fail", f"Error reading file: {e}"))


        return results

    # ── Category 2: Directories ──

    def _check_directories(self):
        results = []
        dirs = [
            ("data", DATA_DIR),
            ("data/attachments", os.path.join(DATA_DIR, "attachments")),
            ("assets", os.path.join(PROJECT_DIR, "assets")),
            ("pages", os.path.join(PROJECT_DIR, "pages")),
            ("utils", os.path.join(PROJECT_DIR, "utils")),
            ("components", os.path.join(PROJECT_DIR, "components")),
        ]
        for name, path in dirs:
            if not os.path.exists(path):
                try:
                    os.makedirs(path, exist_ok=True)
                    results.append(self._check_result(
                        f"dir:{name}", "filesystem", "pass",
                        f"Directory was missing — created",
                        healed=True, heal_action=f"Created directory {name}"))
                except Exception as e:
                    results.append(self._check_result(
                        f"dir:{name}", "filesystem", "fail",
                        f"Missing and could not create: {e}"))
            elif not os.access(path, os.W_OK):
                results.append(self._check_result(
                    f"dir:{name}", "filesystem", "warn",
                    f"Directory exists but is not writable"))
            else:
                results.append(self._check_result(
                    f"dir:{name}", "filesystem", "pass", "Exists and writable"))

        return results

    # ── Category 3: Page Imports ──

    def _check_page_imports(self):
        results = []
        for page in PAGE_MODULES:
            name = f"import:pages.{page}"
            try:
                mod = importlib.import_module(f"pages.{page}")
                results.append(self._check_result(
                    name, "pages", "pass", f"Module imported successfully"))
            except Exception as e:
                tb = traceback.format_exc().split("\n")[-3:]
                results.append(self._check_result(
                    name, "pages", "fail",
                    f"Import error: {e}\n{''.join(tb)}"))
        return results

    # ── Category 4: Page Renders ──

    def _check_page_renders(self):
        results = []
        for page in PAGE_MODULES:
            name = f"render:pages.{page}"
            try:
                mod = importlib.import_module(f"pages.{page}")
                if not hasattr(mod, "layout"):
                    results.append(self._check_result(
                        name, "pages", "warn", "No layout() function found"))
                    continue
                result = mod.layout()
                if result is None:
                    results.append(self._check_result(
                        name, "pages", "warn", "layout() returned None"))
                else:
                    results.append(self._check_result(
                        name, "pages", "pass", "Renders successfully"))
            except Exception as e:
                tb = traceback.format_exc().split("\n")[-3:]
                results.append(self._check_result(
                    name, "pages", "fail",
                    f"Render error: {e}\n{''.join(tb)}"))
        return results

    # ── Category 5: Dependencies ──

    def _check_dependencies(self):
        results = []
        for dep in REQUIRED_DEPS:
            name = f"dep:{dep}"
            try:
                mod = importlib.import_module(dep)
                version = getattr(mod, "__version__", "unknown")
                results.append(self._check_result(
                    name, "dependencies", "pass", f"v{version}"))
            except ImportError as e:
                results.append(self._check_result(
                    name, "dependencies", "fail", f"Not installed: {e}"))
        return results

    # ── Category 6: OAuth ──

    def _check_oauth(self):
        results = []
        creds_path = os.path.expanduser("~/.claude/.credentials.json")

        if not os.path.exists(creds_path):
            results.append(self._check_result(
                "oauth:credentials_file", "oauth", "warn",
                "~/.claude/.credentials.json not found — run 'claude auth'"))
            results.append(self._check_result(
                "oauth:token", "oauth", "warn",
                "No OAuth token available"))
            return results

        try:
            with open(creds_path) as f:
                creds = json.load(f)
            results.append(self._check_result(
                "oauth:credentials_file", "oauth", "pass",
                "Credentials file exists and is valid JSON"))

            token = creds.get("claudeAiOauth", {}).get("accessToken", "")
            if token:
                # Show partial token for verification
                masked = token[:8] + "..." + token[-4:] if len(token) > 16 else "***"
                results.append(self._check_result(
                    "oauth:token", "oauth", "pass",
                    f"OAuth token present ({masked})"))

                # Token present — skip live validation to avoid rate limits
                results.append(self._check_result(
                    "oauth:validation", "oauth", "pass",
                    "Token present (skipping live validation to avoid rate limits)"))
            else:
                # Check for API key fallback
                try:
                    from utils.vision import _get_api_key_fallback
                    api_key = _get_api_key_fallback()
                    if api_key:
                        results.append(self._check_result(
                            "oauth:token", "oauth", "pass",
                            "No OAuth token but API key fallback is configured"))
                    else:
                        results.append(self._check_result(
                            "oauth:token", "oauth", "warn",
                            "No OAuth token and no API key fallback"))
                except Exception:
                    results.append(self._check_result(
                        "oauth:token", "oauth", "warn",
                        "Credentials file exists but no accessToken found"))

        except json.JSONDecodeError:
            results.append(self._check_result(
                "oauth:credentials_file", "oauth", "fail",
                "Credentials file is not valid JSON"))
            results.append(self._check_result(
                "oauth:token", "oauth", "fail",
                "Cannot read token — credentials file corrupt"))

        return results

    # ── Category 6b: WhatsApp ──

    def _check_whatsapp(self):
        results = []
        try:
            with open(os.path.join(DATA_DIR, "accounts.json")) as f:
                accounts = json.load(f)
            wa = accounts.get("whatsapp", {})

            if not wa.get("enabled"):
                results.append(self._check_result(
                    "whatsapp:status", "whatsapp", "pass",
                    "WhatsApp integration disabled (not configured)"))
                return results

            # Check required fields
            if not wa.get("bridge_url"):
                results.append(self._check_result(
                    "whatsapp:bridge_url", "whatsapp", "warn",
                    "WhatsApp enabled but no bridge URL configured"))
            elif not wa.get("api_key"):
                results.append(self._check_result(
                    "whatsapp:api_key", "whatsapp", "warn",
                    "WhatsApp enabled but no API key configured"))
            else:
                # Try a quick connection test
                try:
                    from utils.whatsapp import test_connection
                    result = test_connection()
                    if result.get("connected"):
                        phone = result.get("phone_number", "")
                        results.append(self._check_result(
                            "whatsapp:connection", "whatsapp", "pass",
                            f"Connected — {phone}"))
                    else:
                        results.append(self._check_result(
                            "whatsapp:connection", "whatsapp", "warn",
                            f"Connection failed: {result.get('error', 'unknown')}"))
                except Exception as e:
                    results.append(self._check_result(
                        "whatsapp:connection", "whatsapp", "warn",
                        f"Could not test connection: {e}"))
        except Exception:
            results.append(self._check_result(
                "whatsapp:status", "whatsapp", "pass",
                "WhatsApp config not found (not configured)"))

        return results

    # ── Category 7: Port ──

    def _check_port(self):
        results = []
        from config import APP_PORT

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex(("127.0.0.1", APP_PORT))
            if result == 0:
                results.append(self._check_result(
                    f"port:{APP_PORT}", "port", "pass",
                    f"App is listening on port {APP_PORT}"))
            else:
                results.append(self._check_result(
                    f"port:{APP_PORT}", "port", "fail",
                    f"Port {APP_PORT} is not responding"))
        except Exception as e:
            results.append(self._check_result(
                f"port:{APP_PORT}", "port", "fail", f"Port check error: {e}"))
        finally:
            sock.close()

        return results

    # ── Category 8: Disk Space ──

    def _check_disk_space(self):
        results = []
        try:
            usage = shutil.disk_usage(DATA_DIR)
            free_mb = usage.free / (1024 * 1024)
            total_mb = usage.total / (1024 * 1024)
            pct = (usage.used / usage.total) * 100

            if free_mb < 10:
                results.append(self._check_result(
                    "disk:space", "filesystem", "fail",
                    f"Critical: only {free_mb:.0f}MB free ({pct:.1f}% used)"))
            elif free_mb < 100:
                results.append(self._check_result(
                    "disk:space", "filesystem", "warn",
                    f"Low: {free_mb:.0f}MB free ({pct:.1f}% used)"))
            else:
                results.append(self._check_result(
                    "disk:space", "filesystem", "pass",
                    f"{free_mb:.0f}MB free ({pct:.1f}% used of {total_mb:.0f}MB)"))
        except Exception as e:
            results.append(self._check_result(
                "disk:space", "filesystem", "fail", f"Cannot check disk: {e}"))

        return results

    # ── Category 9: Callback Registration ──

    def _check_callbacks(self):
        results = []
        if not self._app:
            results.append(self._check_result(
                "callbacks:registry", "callbacks", "warn",
                "No app reference — cannot check callbacks"))
            return results

        from config import APP_PORT as _port
        try:
            # Try multiple sources for callback count
            total = 0

            # Method 1: app.callback_map (populated after first request)
            total = len(getattr(self._app, "callback_map", {}))

            # Method 2: GLOBAL_CALLBACK_MAP
            if total == 0:
                try:
                    from dash._callback import GLOBAL_CALLBACK_MAP
                    total = len(GLOBAL_CALLBACK_MAP)
                except ImportError:
                    pass

            # Method 3: _callback_list
            if total == 0:
                total = len(getattr(self._app, "_callback_list", []))

            # Method 4: Verify by HTTP — most reliable
            if total == 0:
                import requests as _req
                try:
                    resp = _req.get(f"http://127.0.0.1:{_port}/_dash-dependencies", timeout=5)
                    if resp.status_code == 200:
                        deps = resp.json()
                        total = len(deps) if isinstance(deps, list) else 0
                except Exception:
                    pass

            expected_min = 10
            if total >= expected_min:
                results.append(self._check_result(
                    "callbacks:registry", "callbacks", "pass",
                    f"{total} callbacks registered"))
            elif total > 0:
                results.append(self._check_result(
                    "callbacks:registry", "callbacks", "warn",
                    f"Only {total} callbacks registered (expected >= {expected_min})"))
            else:
                results.append(self._check_result(
                    "callbacks:registry", "callbacks", "warn",
                    "Cannot verify callback count"))

            # Verify page routing works by HTTP
            import requests as _req
            try:
                resp = _req.get(f"http://127.0.0.1:{_port}/health", timeout=5)
                if resp.status_code == 200:
                    results.append(self._check_result(
                        "callbacks:page_router", "callbacks", "pass",
                        "Page routing verified via HTTP"))
                else:
                    results.append(self._check_result(
                        "callbacks:page_router", "callbacks", "warn",
                        f"Page route returned {resp.status_code}"))
            except Exception as e:
                results.append(self._check_result(
                    "callbacks:page_router", "callbacks", "warn",
                    f"Cannot verify page routing: {e}"))

        except Exception as e:
            results.append(self._check_result(
                "callbacks:registry", "callbacks", "fail",
                f"Cannot inspect callbacks: {e}"))

        return results

    # ── Persistence ──

    def _persist_report(self, report):
        try:
            if os.path.exists(self._log_path):
                with open(self._log_path) as f:
                    logs = json.load(f)
            else:
                logs = []

            logs.append(report)

            # Prune to max entries
            if len(logs) > self._max_log_entries:
                logs = logs[-self._max_log_entries:]

            with open(self._log_path, "w") as f:
                json.dump(logs, f, indent=2)
        except Exception:
            pass  # Don't crash the health loop for logging failures
