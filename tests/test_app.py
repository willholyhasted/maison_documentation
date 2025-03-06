import pytest
from app import app, init_db, get_db_connection
import io


@pytest.fixture
def client():
    """Test client fixture that sets up and tears down test data"""
    app.config["TESTING"] = True
    with app.test_client() as client:
        # Set up test database
        conn = get_db_connection()
        cur = conn.cursor()

        # Create tables and clean existing test data
        init_db()
        cur.execute("DELETE FROM documents")
        cur.execute("DELETE FROM documents_buyer")  # Also clean buyer documents table
        conn.commit()

        # Create test file data
        test_file_content = b"Test file content"

        # Insert test document using multipart form data
        test_data = {
            "property_id": "999",
            "buyer_id": "888",
            "seller_id": "777",
            "uploaded_by": "buyer",
            "document_tag": "test_document",
            "file": (io.BytesIO(test_file_content), "test.pdf", "application/pdf"),
        }

        # Use data parameter with multipart/form-data content type
        response = client.post(
            "/documents", data=test_data, content_type="multipart/form-data"
        )

        assert response.status_code == 201

        conn.commit()
        cur.close()
        conn.close()

        yield client

        # Cleanup after tests
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM documents WHERE property_id = '999'")
        conn.commit()
        cur.close()
        conn.close()


def test_database_connection():
    """Test that database connection works"""
    conn = get_db_connection()
    assert conn is not None
    cur = conn.cursor()
    cur.execute("SELECT 1")
    result = cur.fetchone()
    assert result[0] == 1
    cur.close()
    conn.close()


def test_query_documents_empty(client):
    """Test querying documents with no filters returns all documents"""
    response = client.get("/documents/query")
    assert response.status_code == 200
    data = response.get_json()
    assert "count" in data
    assert "documents" in data
    assert data["count"] == 1  # Our test document
    assert len(data["documents"]) == 1
    # Verify the document has the expected fields
    doc = data["documents"][0]
    assert "filename" in doc
    assert "file_type" in doc
    assert "image_url" in doc
    assert doc["filename"] == "test.pdf"
    assert doc["file_type"] == "application/pdf"
    assert doc["property_id"] == "999"  # Note: property_id is now a string


def test_query_documents_by_property(client):
    """Test querying documents with property filter"""
    response = client.get("/documents/query?property_id=999")
    assert response.status_code == 200

    data = response.get_json()
    assert len(data["documents"]) == 1
    doc = data["documents"][0]
    assert doc["filename"] == "test.pdf"
    assert doc["property_id"] == "999"  # Note: property_id is now a string
    assert "image_url" in doc
    assert doc["image_url"].startswith("data:application/pdf;base64,")


def test_add_document(client):
    """Test adding a new document"""
    # Create test file
    file_content = b"New test file content"

    data = {
        "property_id": "999",
        "buyer_id": "888",
        "seller_id": "777",
        "uploaded_by": "seller",
        "document_tag": "test_contract",
        "file": (io.BytesIO(file_content), "new_test.pdf", "application/pdf"),
    }

    response = client.post("/documents", data=data, content_type="multipart/form-data")
    assert response.status_code == 201
    assert "document_id" in response.get_json()

    # Verify the document was added
    response = client.get("/documents/query?property_id=999")
    data = response.get_json()
    assert len(data["documents"]) == 2  # Now we should have 2 test documents
    assert any(doc["filename"] == "new_test.pdf" for doc in data["documents"])

    # Verify both documents have image_url
    for doc in data["documents"]:
        assert "image_url" in doc
        assert doc["image_url"].startswith("data:application/pdf;base64,")


def test_add_document_missing_file(client):
    """Test adding a document without a file"""
    data = {
        "property_id": "999",
        "buyer_id": "888",
        "seller_id": "777",
        "uploaded_by": "seller",
        "document_tag": "test_contract",
    }

    response = client.post("/documents", data=data)
    assert response.status_code == 400
    assert "No file provided" in response.get_json()["error"]


def test_add_document_missing_fields(client):
    """Test adding a document with missing required fields"""
    file_content = b"Test file content"

    # Missing property_id
    data = {
        "buyer_id": "888",
        "seller_id": "777",
        "uploaded_by": "seller",
        "document_tag": "test_contract",
        "file": (io.BytesIO(file_content), "test.pdf", "application/pdf"),
    }

    response = client.post("/documents", data=data, content_type="multipart/form-data")
    assert response.status_code == 400
    assert "Missing required fields" in response.get_json()["error"]


def test_add_document_buyer(client):
    """Test adding a document to the buyer table"""
    file_content = b"Buyer document content"

    data = {
        "buyer_id": "888",
        "document_tag": "identification",
        "file": (io.BytesIO(file_content), "id.jpg", "image/jpeg"),
    }

    response = client.post(
        "/documents/buyer", data=data, content_type="multipart/form-data"
    )
    assert response.status_code == 201
    assert "document_id" in response.get_json()

    # Verify the document was added
    response = client.get("/documents/query/buyer?buyer_id=888")
    data = response.get_json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["filename"] == "id.jpg"
    assert data["documents"][0]["document_tag"] == "identification"


def test_delete_document_buyer(client):
    """Test deleting a document from the buyer table"""
    # First, add a document to delete
    file_content = b"Buyer document to delete"

    data = {
        "buyer_id": "999",  # Using a different ID to avoid conflicts
        "document_tag": "passport",
        "file": (io.BytesIO(file_content), "passport.jpg", "image/jpeg"),
    }

    # Add the document
    response = client.post(
        "/documents/buyer", data=data, content_type="multipart/form-data"
    )
    assert response.status_code == 201

    # Verify it was added
    response = client.get("/documents/query/buyer?buyer_id=999")
    assert response.status_code == 200
    initial_data = response.get_json()
    assert initial_data["count"] >= 1

    # Delete the document
    response = client.delete(
        "/documents/buyer/delete?buyer_id=999&document_tag=passport"
    )
    assert response.status_code == 200
    assert "Document deleted successfully" in response.get_json()["message"]

    # Verify it was deleted
    response = client.get("/documents/query/buyer?buyer_id=999&document_tag=passport")
    assert response.status_code == 200
    final_data = response.get_json()
    assert final_data["count"] == 0
