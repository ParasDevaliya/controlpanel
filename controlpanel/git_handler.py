import os
import base64
import subprocess
import uuid
import random
import string
import platform

# Constants
NGINX_PROJECTS_PATH = "/home/rbonweb/"
NGINX_SITES_AVAILABLE = "/etc/nginx/sites-available"
NGINX_SITES_ENABLED = "/etc/nginx/sites-enabled"
BASE_DOMAIN = "ipless.local"

def generate_random_subdomain(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def cleanup_broken_symlinks(sites_enabled_path):
    for filename in os.listdir(sites_enabled_path):
        filepath = os.path.join(sites_enabled_path, filename)
        if os.path.islink(filepath) and not os.path.exists(os.readlink(filepath)):
            print(f"Removing broken symlink: {filepath}")
            os.unlink(filepath)

def update_etc_hosts(full_domain):
    hosts_path = "/etc/hosts"
    entry = f"127.0.0.1    {full_domain}\n"

    try:
        with open(hosts_path, 'r') as f:
            lines = f.readlines()
            if any(full_domain in line for line in lines):
                print(f"{full_domain} already present in /etc/hosts")
                return True

        print(f"Adding {full_domain} to /etc/hosts...")
        process = subprocess.run(
            ['sudo', 'tee', '-a', hosts_path],
            input=entry,
            text=True,
            capture_output=True
        )

        if process.returncode != 0:
            print("Failed to update /etc/hosts:", process.stderr)
            return False

        print("Successfully updated /etc/hosts")
        return True

    except Exception as e:
        print("Exception while updating /etc/hosts:", e)
        return False

def handle_git_clone(data):
    try:
        at = data.get('at')
        gu = data.get('gu')
        print("Access token and GitHub URL:", at, gu)

        if not (at and gu):
            return {'error': 'Missing parameters'}, 400

        try:
            token = base64.b64decode(at).decode('utf-8')
            print("Decoded token:", token)
        except Exception as e:
            return {'error': 'Invalid token encoding', 'details': str(e)}, 400

        if not gu.startswith("https://"):
            return {'error': 'Invalid GitHub URL'}, 400

        parts = gu.split("https://", 1)
        secure_url = f"https://{token}@{parts[1]}"
        print("Secure Git URL:", secure_url)

        repo_name = gu.rstrip('/').split('/')[-1].replace('.git', '')
        unique_id = uuid.uuid4().hex[:8]
        project_folder_name = f"{repo_name}_{unique_id}"
        project_path = os.path.join(NGINX_PROJECTS_PATH, project_folder_name)
        print("Project path:", project_path)

        os.makedirs(project_path, exist_ok=False)

        clone_cmd = ["git", "clone", secure_url, project_path]
        print("Running:", " ".join(clone_cmd))
        clone_result = subprocess.run(clone_cmd, capture_output=True, text=True)

        if clone_result.returncode != 0:
            print("Git clone failed:", clone_result.stderr)
            return {'error': 'Git clone failed', 'details': clone_result.stderr}, 500

        print("Clone successful:", clone_result.stdout)

        subdomain = generate_random_subdomain()
        full_domain = f"{subdomain}.{BASE_DOMAIN}"
        print("Generated domain:", full_domain)

        nginx_conf_filename = f"{full_domain}.conf"
        nginx_conf_path = os.path.join(NGINX_SITES_AVAILABLE, nginx_conf_filename)

        nginx_conf_content = f"""
        server {{
            listen 80;
            server_name {full_domain};

            location / {{
                proxy_pass http://localhost:3000;
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection 'upgrade';
                proxy_set_header Host $host;
                proxy_cache_bypass $http_upgrade;
            }}
        }}
        """.strip()

        print("Writing nginx config to:", nginx_conf_path)
        with open(nginx_conf_path, 'w') as conf_file:
            conf_file.write(nginx_conf_content + "\n")

        symlink_path = os.path.join(NGINX_SITES_ENABLED, nginx_conf_filename)
        print("Symlink path:", symlink_path)

        if os.path.islink(symlink_path) and not os.path.exists(os.readlink(symlink_path)):
            print("Removing broken symlink:", symlink_path)
            os.unlink(symlink_path)

        if not os.path.exists(symlink_path):
            os.symlink(nginx_conf_path, symlink_path)
            print("Created symlink.")

        print("Cleaning up broken symlinks...")
        cleanup_broken_symlinks(NGINX_SITES_ENABLED)

        print("Testing nginx config...")
        test_result = subprocess.run(["sudo", "nginx", "-t"], capture_output=True, text=True)
        print("nginx -t output:", test_result.stdout, test_result.stderr)

        if test_result.returncode != 0:
            return {
                'error': 'Nginx configuration test failed',
                'details': test_result.stderr
            }, 500

        print("Reloading nginx...")
        reload_result = subprocess.run(["sudo", "systemctl", "reload", "nginx"], capture_output=True, text=True)
        if reload_result.returncode != 0:
            return {
                'error': 'Failed to reload nginx',
                'details': reload_result.stderr
            }, 500

        print("Nginx reloaded successfully.")

        # ✅ Add entry to /etc/hosts
        update_etc_hosts(full_domain)

        # ✅ Start the project in a new terminal window
        start_script = f'cd "{project_path}" && npm install && npm start'
        system = platform.system()

        if system == "Linux":
            subprocess.Popen(["gnome-terminal", "--", "bash", "-c", f'{start_script}; exec bash'])
        elif system == "Darwin":
            apple_script = f'''
            tell application "Terminal"
                do script "{start_script}"
            end tell
            '''
            subprocess.run(["osascript", "-e", apple_script])
        elif system == "Windows":
            subprocess.Popen(["cmd", "/c", f"start cmd /k \"{start_script}\""])
        else:
            print("Unsupported OS - running in background instead.")
            subprocess.Popen(["bash", "-c", start_script])

        # ✅ Open in browser
        subprocess.Popen(["xdg-open", f"http://{full_domain}"])

        return {
            'status': 'success',
            'repo_path': project_path,
            'domain': full_domain,
            'nginx_config': nginx_conf_path,
            'message': f'Repo cloned and served at http://{full_domain}'
        }, 200

    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        print("Unhandled exception:", traceback_str)
        return {
            'error': 'Internal Server Error',
            'details': str(e),
            'trace': traceback_str
        }, 500
