import requests


class PhpBridgeService:
    """HTTP JSON bridge from Python AI service to PHP backend."""

    def __init__(self, php_api_base_url: str = "http://127.0.0.1:8080/api") -> None:
        self.php_api_base_url = php_api_base_url.rstrip("/")

    def post_ai_update(self, payload: dict) -> dict:
        response = requests.post(
            f"{self.php_api_base_url}/ai-update",
            json=payload,
            timeout=3,
        )
        response.raise_for_status()
        return response.json()
