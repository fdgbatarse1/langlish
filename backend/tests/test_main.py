from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_read_root() -> None:
    """Test the root endpoint returns correct status code and message.
    
    Returns:
        None
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}
