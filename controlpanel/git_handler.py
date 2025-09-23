import os
import base64
import subprocess
import tempfile

def handle_git_clone_and_docker(data):
    at = data.get('at')
    gu = data.get('gu') 
    print("access token and github url", at,gu)

    if not (at and gu):
        return {'error': 'Missing parameters'}, 400

    try:
        token = base64.b64decode(at).decode('utf-8')
    except Exception as e:
        return {'error': 'Invalid token encoding'}, 400

    if gu.startswith("https://"):
        parts = gu.split("https://", 1)
        secure_url = f"https://{token}@{parts[1]}"
    else:
        return {'error': 'Invalid GitHub URL'}, 400

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = os.path.join(tmpdir, "repo")
        clone_cmd = ["git", "clone", secure_url, repo_dir]
        clone_result = subprocess.run(clone_cmd, capture_output=True, text=True)

        if clone_result.returncode != 0:
            return {'error': 'Git clone failed', 'details': clone_result.stderr}, 500

        # Write Dockerfile
        dockerfile_content = """
        FROM node:20

        WORKDIR /app

        RUN npm install -g @angular/cli

        COPY package*.json ./

        RUN npm install

        COPY . .

        EXPOSE 4200

        CMD ["ng", "serve", "--host", "0.0.0.0"]
        """
        dockerfile_path = os.path.join(repo_dir, "Dockerfile")
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content.strip())

        # Write docker-compose.yml (optional, not used in this script)
        docker_compose_content = """
        version: '3.8'

        services:
          angular-app:
            build: .
            ports:
              - "8080:4200"
            volumes:
              - .:/app
              - /app/node_modules
            environment:
              - NODE_ENV=development
            restart: always
            command: ng serve --host 0.0.0.0
        """
        docker_compose_path = os.path.join(repo_dir, "docker-compose.yml")
        with open(docker_compose_path, "w") as f:
            f.write(docker_compose_content.strip())

        # Build Docker image
        image_name = "custom_image_from_repo"
        build_cmd = ["docker", "build", "-t", image_name, "."]
        build_result = subprocess.run(build_cmd, cwd=repo_dir, capture_output=True, text=True)

        if build_result.returncode != 0:
            return {'error': 'Docker build failed', 'details': build_result.stderr}, 500

        # Run container with exposed port 8080:4200
        container_name = "custom_container_from_repo"
        run_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", "8080:4200",  # Host:Container
            image_name
        ]
        run_result = subprocess.run(run_cmd, capture_output=True, text=True)

        if run_result.returncode != 0:
            return {'error': 'Docker run failed', 'details': run_result.stderr}, 500

        container_id = run_result.stdout.strip()

        return {
            'status': 'success',
            'container_id': container_id,
            'url': 'http://localhost:8080'
        }, 200
