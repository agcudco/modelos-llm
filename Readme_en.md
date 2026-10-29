
[![Issues][issues-shield]][issues-url]
[![LinkedIn][linkedin-shield]][linkedin-url]

<!-- Introduction -->
<br />

<div align="center">
  <img src="img/oi.png" alt="Open WebUI Logo" height="100" />

  <h1>Open WebUI</h1>

  <a href="/src/">👨🏽‍💻 Explore the Code »</a>
  <br />
  <a href="https://www.youtube.com/watch?v=6L1YmTRZNxM&list=PLMUWTQHw13gbk738EGtr0fWwi40B81qEw">
    🎬 View Demo
  </a>
  ·
  <a href="https://github.com/jganggini/oci-functions/issues">
    💣 Report Bug
  </a>
  ·
  <a href="https://github.com/jganggini/oci-functions/pulls">
    🚀 Request Feature
  </a>

  <br /><br />

  <table align="center">
    <tr>
      <th colspan="5">AI Stack</th>
      <th colspan="2">LLM</th>
    </tr>
    <tr align="center">
      <td><img src="img/oi.png" width="50" height="50" /></td>
      <td><img src="img/docker.png" width="50" height="50" /></td>
      <td><img src="img/git.png" width="50" height="50" /></td>
      <td><img src="img/nginx.png" width="50" height="50" /></td>
      <td><img src="img/ollama.png" width="50" height="50" /></td>
      <td><img src="img/meta.png" width="50" height="50" /></td>
      <td><img src="img/deepseek.png" width="50" height="50" /></td>
    </tr>
    <tr align="center">
      <td>Open WebUI</td>
      <td>Docker</td>
      <td>Git</td>
      <td>Nginx</td>
      <td>Ollama</td>
      <td>Meta</td>
      <td>DeepSeek</td>
    </tr>
  </table>
</div>

---

## 💼 Use Case

This use case focuses on providing easy-to-deploy and user-friendly open-source artificial intelligence solutions, enabling businesses and developers to quickly access cutting-edge AI technologies.

The solution integrates **Open WebUI** as an intuitive interface for managing AI models, **Ollama** for running Large Language Models (LLMs) in CPU or GPU environments, and **Nginx** as a reverse proxy to secure HTTPS traffic.

All components are orchestrated using **Docker Compose**, enabling flexible deployment configurations through dedicated profiles and seamless integration into local or cloud-based environments.

This architecture provides a scalable, modular, and accessible environment for deploying and managing open-source LLMs.

## 🧩 Components

- 🔗 **Open WebUI** – An intuitive web interface for interacting with and managing AI models.
- 🦙 **Ollama** – A platform for running and managing Large Language Models (LLMs) on CPU or GPU.
- 🔒 **Nginx** – A reverse proxy server responsible for HTTPS traffic management and secure connections.
- 🐳 **Docker Compose** – A container orchestration tool that simplifies application deployment, configuration, and management.

---

## 🚀 Installation

### 1. Set Up Docker's APT Repository

Before installing Docker Engine, configure Docker's official APT repository.

```bash
# Update the package index and install prerequisites
sudo apt-get update
sudo apt-get install ca-certificates curl

# Create the directory for APT keyrings
sudo install -m 0755 -d /etc/apt/keyrings

# Add Docker's official GPG key
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker's repository to APT sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update the package index
sudo apt-get update
```

### 2. Install Docker Packages

Install Docker Engine, Docker CLI, containerd, and the Docker Compose plugin.

```bash
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 3. Verify Docker Installation

Run the following command to verify that Docker has been installed successfully:

```bash
sudo docker run hello-world
```

This command downloads a test image and runs it inside a container. If Docker is properly installed, the container displays a confirmation message and exits.

**Reference:** [Docker Engine Installation on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)

### 4. Install Git

Install Git using the following command:

```bash
sudo apt-get install git-all
```

### 5. Verify Git Installation

After the installation is complete, verify the installed Git version:

```bash
git --version
```

**Reference:** [Git Installation Guide](https://github.com/git-guides/install-git)

---

## 📥 Clone the Repository

### 6. Clone the Project Repository

Create a working directory and clone the repository:

```bash
sudo mkdir docker
cd docker

sudo git clone https://github.com/jganggini/open-ai.git

cd open-ai/docker-open-webui-auto-https
```

---

## 🐳 Run Open WebUI with Docker Compose

### 7. Start the Application

The application supports two deployment configurations depending on the available hardware.

### 🟢 Option A: Systems with NVIDIA GPU

For systems equipped with an NVIDIA graphics card, use the `gpu-nvidia` profile to enable GPU acceleration.

```bash
# Pull the required Docker images
sudo docker compose --profile gpu-nvidia pull

# Create the containers
sudo docker compose create

# Start the application with GPU support
sudo docker compose --profile gpu-nvidia up
```

### 🔵 Option B: Systems without GPU (CPU Only)

For systems without a dedicated NVIDIA GPU, use the `cpu` profile to run the application using CPU resources.

```bash
# Pull the required Docker images
sudo docker compose --profile cpu pull

# Create the containers
sudo docker compose create

# Start the application using CPU resources
sudo docker compose --profile cpu up
```

---

## 📚 References

- [Docker Official Documentation](https://docs.docker.com/)
- [Git Documentation](https://git-scm.com/doc)
- [Open WebUI](https://docs.openwebui.com/)
- [Ollama Documentation](https://docs.ollama.com/)
- [Nginx Documentation](https://nginx.org/en/docs/)
