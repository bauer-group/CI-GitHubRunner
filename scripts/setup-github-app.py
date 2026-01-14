#!/usr/bin/env python3
"""
GitHub App Setup Tool
=====================
Automated GitHub App creation using the Manifest Flow.

This tool:
1. Starts a local web server
2. Opens GitHub to create the app with correct permissions
3. Receives the callback and exchanges the code for credentials
4. Saves App ID and Private Key automatically
5. Updates .env configuration

Usage:
    python3 scripts/setup-github-app.py

Requirements:
    - Python 3.6+
    - No external dependencies (uses only standard library)
"""

import html
import http.server
import json
import os
import re
import shutil
import socketserver
import ssl
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

# Configuration
PORT = 8765
CALLBACK_PATH = "/callback"
REPO_URL = "https://github.com/bauer-group/CI-GitHubRunner"  # Change this if you fork the repo

# Colors for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

    @classmethod
    def disable(cls):
        """Disable colors for non-TTY environments"""
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.CYAN = cls.NC = ''


# Disable colors if not a TTY
if not sys.stdout.isatty():
    Colors.disable()


def print_header(title: str):
    """Print a styled header"""
    print(f"\n{Colors.BLUE}{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}{Colors.NC}\n")


def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.NC}")


def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.NC}")


def print_info(msg: str):
    print(f"{Colors.CYAN}ℹ {msg}{Colors.NC}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.NC}")


class GitHubAppSetup:
    """Handles the GitHub App creation process"""

    def __init__(self, org_name: str, project_root: Path, instance_name: str = ""):
        self.org_name = org_name
        self.project_root = project_root
        self.instance_name = instance_name

        # Build app name with optional instance identifier
        if instance_name:
            self.app_name = f"Self-Hosted Runner - {instance_name}"
        else:
            self.app_name = f"Self-Hosted Runner - {org_name}"

        self.callback_url = f"http://localhost:{PORT}{CALLBACK_PATH}"
        self.received_code = None
        self.server = None
        self.app_data = None

    def get_manifest(self) -> dict:
        """Generate the GitHub App manifest"""
        # Build description with optional instance name
        if self.instance_name:
            description = (
                f"Self-hosted GitHub Actions Runner ({self.instance_name}). "
                f"Ephemeral runners with Docker-in-Docker isolation for secure CI/CD builds."
            )
        else:
            description = (
                "Self-hosted GitHub Actions Runner. "
                "Ephemeral runners with Docker-in-Docker isolation for secure CI/CD builds."
            )

        return {
            "name": self.app_name,
            "description": description,
            "url": REPO_URL,
            "hook_attributes": {
                "url": REPO_URL,
                "active": False
            },
            "redirect_url": self.callback_url,
            "callback_urls": [self.callback_url],
            "public": False,
            "default_permissions": {
                "organization_self_hosted_runners": "write",
                "administration": "write"
            },
            "default_events": []
        }

    def get_redirect_html(self) -> str:
        """Generate HTML page that auto-submits manifest to GitHub"""
        # Create JSON and HTML-escape it for safe embedding in value attribute
        manifest_json = json.dumps(self.get_manifest())
        manifest_escaped = html.escape(manifest_json, quote=True)
        github_url = f"https://github.com/organizations/{self.org_name}/settings/apps/new"

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Creating GitHub App...</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #F2F2F2;
        }}
        .container {{
            background: #FFFFFF;
            border: 1px solid #EFEFEF;
            padding: 3rem;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            text-align: center;
            max-width: 500px;
        }}
        h1 {{
            color: #2E3236;
            margin-bottom: 1rem;
        }}
        p {{ color: #5B5B5B; line-height: 1.6; }}
        .spinner {{
            border: 4px solid #EFEFEF;
            border-top: 4px solid #FF8500;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 1rem auto;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body onload="document.getElementById('manifest-form').submit();">
    <div class="container">
        <div class="spinner"></div>
        <h1>Creating GitHub App</h1>
        <p>Redirecting to GitHub...<br>
        Please wait.</p>
    </div>
    <form id="manifest-form" action="{github_url}" method="post">
        <input type="hidden" name="manifest" value="{manifest_escaped}">
    </form>
</body>
</html>"""

    def create_callback_handler(self):
        """Create an HTTP request handler for the OAuth callback"""
        app_setup = self

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Suppress default logging
                pass

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)

                # Serve the redirect page that POSTs manifest to GitHub
                if parsed.path == "/" or parsed.path == "/start":
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(app_setup.get_redirect_html().encode('utf-8'))
                    return

                if parsed.path == CALLBACK_PATH:
                    query = urllib.parse.parse_qs(parsed.query)
                    code = query.get('code', [None])[0]

                    if code:
                        app_setup.received_code = code
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.end_headers()

                        html = """
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="UTF-8">
                            <title>GitHub App Created!</title>
                            <style>
                                body {
                                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                                    display: flex;
                                    justify-content: center;
                                    align-items: center;
                                    min-height: 100vh;
                                    margin: 0;
                                    background: #F2F2F2;
                                }
                                .container {
                                    background: #FFFFFF;
                                    border: 1px solid #EFEFEF;
                                    padding: 3rem;
                                    border-radius: 16px;
                                    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
                                    text-align: center;
                                    max-width: 500px;
                                }
                                h1 { color: #FF8500; margin-bottom: 1rem; }
                                p { color: #5B5B5B; line-height: 1.6; }
                                .icon { font-size: 4rem; margin-bottom: 1rem; }
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <div class="icon">✅</div>
                                <h1>GitHub App Created!</h1>
                                <p>The app has been created successfully.<br>
                                You can close this browser tab now.</p>
                                <p style="color: #888888; font-size: 0.9rem; margin-top: 2rem;">
                                    Return to the terminal to complete the setup.
                                </p>
                            </div>
                        </body>
                        </html>
                        """
                        self.wfile.write(html.encode())

                        # Signal to stop the server
                        threading.Thread(target=app_setup.stop_server).start()
                    else:
                        self.send_error(400, "No code received")
                else:
                    self.send_error(404, "Not Found")

        return CallbackHandler

    def start_server(self):
        """Start the local callback server"""
        handler = self.create_callback_handler()
        self.server = socketserver.TCPServer(("", PORT), handler)
        self.server.serve_forever()

    def stop_server(self):
        """Stop the local callback server"""
        if self.server:
            self.server.shutdown()

    def exchange_code_for_credentials(self, code: str) -> dict:
        """Exchange the temporary code for app credentials"""
        url = f"https://api.github.com/app-manifests/{code}/conversions"

        req = urllib.request.Request(
            url,
            method='POST',
            headers={
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'GitHub-App-Setup-Tool'
            }
        )

        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            raise Exception(f"GitHub API error: {e.code} - {error_body}")

    def save_private_key(self, pem_content: str) -> Path:
        """Save the private key to a file"""
        key_path = self.project_root / "github-app.pem"

        # Backup existing key if present
        if key_path.exists():
            backup_path = self.project_root / f"github-app.pem.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.move(str(key_path), str(backup_path))
            print_warning(f"Existing key backed up to: {backup_path.name}")

        with open(key_path, 'w') as f:
            f.write(pem_content)

        # Set restrictive permissions (Unix-like systems only)
        try:
            os.chmod(key_path, 0o600)
        except (OSError, AttributeError):
            pass  # Windows doesn't support chmod

        return key_path

    def update_env_file(self, app_id: int, key_path: Path):
        """Update the .env file with app credentials"""
        env_path = self.project_root / ".env"
        env_example = self.project_root / ".env.example"

        # Create .env from example if it doesn't exist
        if not env_path.exists():
            if env_example.exists():
                shutil.copy(str(env_example), str(env_path))
                print_info("Created .env from .env.example")
            else:
                # Create minimal .env
                with open(env_path, 'w') as f:
                    f.write("# GitHub Runner Configuration\n")

        # Read current content
        with open(env_path, 'r') as f:
            content = f.read()

        # Patterns to update or add
        # APP_PRIVATE_KEY_FILE is the host path to PEM file
        # The override file mounts it and reads content at container startup
        updates = {
            'APP_ID': str(app_id),
            'APP_LOGIN': self.org_name,
            'APP_PRIVATE_KEY_FILE': str(key_path),
            'RUNNER_SCOPE': 'org',
            'ORG_NAME': self.org_name,
        }

        for key, value in updates.items():
            # Check if key exists (commented or not)
            pattern_exists = rf'^#?\s*{key}=.*$'
            pattern_set = rf'^{key}=.*$'

            if re.search(pattern_set, content, re.MULTILINE):
                # Key exists and is set, update it
                content = re.sub(pattern_set, f'{key}={value}', content, flags=re.MULTILINE)
            elif re.search(pattern_exists, content, re.MULTILINE):
                # Key exists but is commented, replace with active version
                content = re.sub(pattern_exists, f'{key}={value}', content, flags=re.MULTILINE)
            else:
                # Key doesn't exist, add it
                content += f'\n{key}={value}'

        # Comment out GITHUB_ACCESS_TOKEN if it's set
        content = re.sub(
            r'^GITHUB_ACCESS_TOKEN=',
            '# GITHUB_ACCESS_TOKEN=',
            content,
            flags=re.MULTILINE
        )

        # Write updated content
        with open(env_path, 'w') as f:
            f.write(content)

    def run(self):
        """Run the complete setup process"""
        print_header("GitHub App Setup")

        print(f"Organization: {Colors.CYAN}{self.org_name}{Colors.NC}")
        if self.instance_name:
            print(f"Instance:     {Colors.CYAN}{self.instance_name}{Colors.NC}")
        print(f"App Name:     {Colors.CYAN}{self.app_name}{Colors.NC}")
        print()

        # Show manifest info
        print_info("Manifest created with permissions:")
        print(f"  - Organization Self-hosted Runners: write")
        print(f"  - Repository Administration: write")
        print()

        # Start server in background
        print_info(f"Starting callback server on port {PORT}...")
        server_thread = threading.Thread(target=self.start_server, daemon=True)
        server_thread.start()

        # Local URL that serves the redirect page
        local_url = f"http://localhost:{PORT}/"

        print()
        print(f"{Colors.GREEN}=" * 70 + Colors.NC)
        print(f"{Colors.GREEN}  Open this URL in your browser:{Colors.NC}")
        print(f"{Colors.GREEN}=" * 70 + Colors.NC)
        print()
        print(local_url)
        print()
        print(f"{Colors.GREEN}=" * 70 + Colors.NC)
        print()
        print(f"This page will automatically redirect to GitHub with the")
        print(f"app manifest pre-filled (name, permissions, etc.).")
        print()
        print(f"{Colors.CYAN}SSH Port Forwarding (if on remote server):{Colors.NC}")
        print(f"  ssh -L {PORT}:localhost:{PORT} user@server")
        print()

        # Try to open browser (will likely fail on remote server)
        browser_opened = False
        try:
            webbrowser.open(local_url)
            browser_opened = True
            print_success("Browser opened")
        except Exception:
            pass  # Expected on remote servers

        print(f"{Colors.YELLOW}Waiting for GitHub callback on port {PORT}...{Colors.NC}")
        print()

        # Wait for callback
        server_thread.join(timeout=300)  # 5 minute timeout

        if not self.received_code:
            print_error("Timeout waiting for callback. Please try again.")
            return False

        print_success("Received callback from GitHub!")
        print()

        # Exchange code for credentials
        print_info("Exchanging code for app credentials...")
        try:
            self.app_data = self.exchange_code_for_credentials(self.received_code)
        except Exception as e:
            print_error(f"Failed to get credentials: {e}")
            return False

        app_id = self.app_data.get('id')
        pem = self.app_data.get('pem')
        app_slug = self.app_data.get('slug', self.app_name)

        if not app_id or not pem:
            print_error("Invalid response from GitHub API")
            return False

        print_success(f"App created successfully!")
        print(f"  App ID:   {Colors.CYAN}{app_id}{Colors.NC}")
        print(f"  App Slug: {Colors.CYAN}{app_slug}{Colors.NC}")
        print()

        # Save private key
        print_info("Saving private key...")
        key_path = self.save_private_key(pem)
        print_success(f"Private key saved to: {key_path.name}")
        print()

        # Update .env
        print_info("Updating .env configuration...")
        self.update_env_file(app_id, key_path)
        print_success(".env file updated!")
        print()

        # Final instructions
        print_header("Setup Complete!")

        print(f"{Colors.GREEN}GitHub App has been created and configured!{Colors.NC}")
        print()
        print("Configuration:")
        print(f"  APP_ID={app_id}")
        print(f"  APP_LOGIN={self.org_name}")
        print(f"  APP_PRIVATE_KEY_FILE={key_path}")
        print()
        print(f"{Colors.YELLOW}Important: Install the app in your organization:{Colors.NC}")
        print(f"  https://github.com/organizations/{self.org_name}/settings/apps/{app_slug}/installations")
        print()
        print("Next steps:")
        print(f"  1. {Colors.CYAN}Install the app{Colors.NC} (link above)")
        print(f"  2. {Colors.CYAN}./runner.sh start{Colors.NC} to start runners")
        print()
        print(f"{Colors.BLUE}Optional: Add a logo to your app:{Colors.NC}")
        print(f"  https://github.com/organizations/{self.org_name}/settings/apps/{app_slug}")
        print(f"  (Scroll to 'Display information' section)")
        print()

        return True


def get_project_root() -> Path:
    """Get the project root directory"""
    script_path = Path(__file__).resolve()
    # Script is in scripts/, so parent is project root
    return script_path.parent.parent


def main():
    print_header("GitHub App Creator for Self-Hosted Runners")

    print("This tool will create a GitHub App with minimal permissions")
    print("for self-hosted runner authentication.")
    print()
    print(f"{Colors.CYAN}Advantages over PAT:{Colors.NC}")
    print("  - Minimal permissions (not full admin:org access)")
    print("  - Automatic token rotation")
    print("  - Better audit logs")
    print()

    # Get organization name
    org_name = input(f"Enter your GitHub organization name: ").strip()

    if not org_name:
        print_error("Organization name is required!")
        sys.exit(1)

    # Validate org name (basic check)
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$', org_name):
        print_error("Invalid organization name format")
        sys.exit(1)

    # Get optional instance name for multiple runners
    print()
    print(f"{Colors.CYAN}Multiple runner instances?{Colors.NC}")
    print("  If you have multiple self-hosted runner setups (e.g., dev, prod, gpu),")
    print("  enter an identifier to distinguish this app. Leave empty for single instance.")
    print()
    instance_name = input("Instance name (optional, e.g., 'prod', 'gpu'): ").strip().lower()

    # Validate instance name if provided
    if instance_name and not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', instance_name):
        print_error("Invalid instance name format (use lowercase letters, numbers, hyphens)")
        sys.exit(1)

    # Get project root
    project_root = get_project_root()
    print_info(f"Project directory: {project_root}")
    print()

    # Build app name for confirmation
    if instance_name:
        app_name = f"Self-Hosted Runner - {instance_name}"
    else:
        app_name = f"Self-Hosted Runner - {org_name}"

    # Confirm
    print(f"This will create a GitHub App named: {Colors.CYAN}{app_name}{Colors.NC}")
    confirm = input("Continue? (Y/n): ").strip().lower()

    if confirm and confirm != 'y':
        print("Aborted.")
        sys.exit(0)

    # Run setup
    setup = GitHubAppSetup(org_name, project_root, instance_name)
    success = setup.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
