from pathlib import Path
import yaml


def test_counter_compose_structure():
    root_dir = Path(__file__).resolve().parents[3]
    compose_path = root_dir / "docker-compose.counter.yml"
    assert compose_path.exists(), "docker-compose.counter.yml must exist at repository root"

    with open(compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert "services" in config, "services key is required"
    assert "counter" in config["services"], "counter service must be defined"

    counter = config["services"]["counter"]
    assert counter["build"]["context"] in ("./services/counter", "services/counter")
    assert counter["build"]["dockerfile"] == "Dockerfile"
    assert counter["restart"] == "unless-stopped"

    # Environment checks
    env = counter.get("environment", [])
    env_keys = [e.split("=")[0] if isinstance(e, str) else list(e.keys())[0] for e in env]
    assert any("LINE_ID" in k for k in env_keys)
    assert any("API_SYNC_URL" in k for k in env_keys)
    assert any("VIDEO_PATH" in k for k in env_keys)
    assert any("DB_PATH" in k for k in env_keys)
    assert any("API_TOKEN" in k for k in env_keys)

    # Volume checks
    volumes = counter.get("volumes", [])
    assert any("counter_data:/data" in v for v in volumes)
    assert any(":/samples:ro" in v for v in volumes)

    # Security check: Zero inbound ports exposed
    assert "ports" not in counter, "Edge counter must not expose any inbound ports"
    assert "expose" not in counter, "Edge counter must not expose any inbound ports"

    # Named volume definition
    assert "volumes" in config and "counter_data" in config["volumes"]


def test_env_counter_example_exists():
    root_dir = Path(__file__).resolve().parents[3]
    env_example_path = root_dir / ".env.counter.example"
    assert env_example_path.exists(), ".env.counter.example must exist at repository root"

    content = env_example_path.read_text(encoding="utf-8")
    assert "API_SYNC_URL=" in content
    assert "LINE_ID=" in content
    assert "VIDEO_PATH=" in content
    assert "API_TOKEN=" in content


def test_main_docker_compose_frontend_port_configurable():
    root_dir = Path(__file__).resolve().parents[3]
    compose_path = root_dir / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist at repository root"

    with open(compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    frontend = config["services"]["frontend"]
    ports = frontend.get("ports", [])
    # Verify port is parameterized to prevent Dokploy host port 3000 collision
    assert any("FRONTEND_PORT" in str(p) for p in ports), (
        "Frontend port must be parameterized with FRONTEND_PORT to avoid port 3000 collisions"
    )

