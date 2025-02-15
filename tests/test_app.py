import pytest
from app import app, init_db, get_db_connection


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
        conn.commit()

        # Insert test document
        test_doc = {
            "image": "test_blob_123",
            "property_id": 999,
            "buyer_id": 888,
            "seller_id": 777,
            "uploaded_by": "buyer",
            "document_type": "test_document",
        }

        cur.execute(
            """
            INSERT INTO documents 
            (image, property_id, buyer_id, seller_id, uploaded_by, document_type)
            VALUES (%s, %s, %s, %s, %s, %s)
        """,
            (
                test_doc["image"],
                test_doc["property_id"],
                test_doc["buyer_id"],
                test_doc["seller_id"],
                test_doc["uploaded_by"],
                test_doc["document_type"],
            ),
        )

        conn.commit()
        cur.close()
        conn.close()

        yield client

        # Cleanup after tests
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM documents WHERE property_id = 999")
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


def test_query_documents_by_property(client):
    """Test querying documents with property filter"""
    response = client.get("/documents/query?property_id=999")
    assert response.status_code == 200

    data = response.get_json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["image"] == "test_blob_123"
    assert data["documents"][0]["property_id"] == 999


def test_add_document(client):
    """Test adding a new document"""
    new_doc = {
        "image": "new_test_blob_456",
        "property_id": 999,
        "buyer_id": 888,
        "seller_id": 777,
        "uploaded_by": "seller",
        "document_type": "test_contract",
    }

    response = client.post("/documents", json=new_doc)
    assert response.status_code == 201

    # Verify the document was added
    response = client.get("/documents/query?property_id=999")
    data = response.get_json()
    assert len(data["documents"]) == 2  # Now we should have 2 test documents
    assert any(doc["image"] == "new_test_blob_456" for doc in data["documents"])


def test_get_blob_ids(client):
    """Test retrieving blob IDs"""
    response = client.get("/documents/blob_ids?property_id=999")
    assert response.status_code == 200

    data = response.get_json()
    assert "test_blob_123" in data["blob_ids"]
