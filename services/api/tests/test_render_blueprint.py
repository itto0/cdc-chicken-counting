from pathlib import Path
import yaml


def test_render_blueprint_structure():
    root_dir = Path(__file__).resolve().parents[3]
    render_yaml_path = root_dir / "render.yaml"
    assert render_yaml_path.exists(), "render.yaml must exist at repository root"

    with open(render_yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 1. Database validation
    assert "databases" in config, "databases section is required"
    assert len(config["databases"]) >= 1
    db = config["databases"][0]
    assert db["name"] == "cdc-postgres"
    # Ensure reserved/invalid username 'postgres' is not used
    assert db.get("user") != "postgres", "postgres is a reserved system user in Render and must not be used"

    # 2. Services validation
    assert "services" in config, "services section is required"
    assert len(config["services"]) >= 2

    # API web service
    api_service = next((s for s in config["services"] if s.get("name") == "cdc-api"), None)
    assert api_service is not None, "cdc-api service is required"
    assert api_service["type"] == "web"
    assert api_service["runtime"] == "docker"
    assert api_service["healthCheckPath"] == "/healthz"

    # Frontend static site
    frontend_service = next((s for s in config["services"] if s.get("name") == "cdc-frontend"), None)
    assert frontend_service is not None, "cdc-frontend service is required"
    assert frontend_service["type"] == "web"
    assert frontend_service["runtime"] == "static"
    assert frontend_service["staticPublishPath"] == "./dist"

    # In Render Blueprint spec: Static sites are hosted on global CDN, so they cannot define a region or compute plan
    assert "region" not in frontend_service, "Static sites cannot have a region in Render Blueprint specification"
    assert "plan" not in frontend_service, "Static sites cannot have a compute plan in Render Blueprint specification"

    # SPA rewrite route rule
    routes = frontend_service.get("routes", [])
    assert any(
        r.get("type") == "rewrite" and r.get("source") == "/*" and r.get("destination") == "/index.html"
        for r in routes
    ), "Static site must include SPA rewrite rule /* -> /index.html"
