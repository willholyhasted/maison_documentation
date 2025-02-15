# app.py
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = Flask(__name__)

# Database connection parameters
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
    )


# Create the table if it doesn't exist
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            document_id SERIAL PRIMARY KEY,
            image TEXT NOT NULL,  -- This will store the blob ID
            datetime_uploaded TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            property_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            uploaded_by VARCHAR(50) CHECK (uploaded_by IN ('buyer', 'seller')),
            document_type VARCHAR(50) NOT NULL
        )
    """
    )
    conn.commit()
    cur.close()
    conn.close()


# Initialize the database when the app starts
with app.app_context():
    init_db()


@app.route("/documents", methods=["POST"])
def add_document():
    data = request.get_json()
    required_fields = [
        "image",
        "property_id",
        "buyer_id",
        "seller_id",
        "uploaded_by",
        "document_type",
    ]

    # Validate input
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    if data["uploaded_by"] not in ["buyer", "seller"]:
        return jsonify({"error": "uploaded_by must be either 'buyer' or 'seller'"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO documents 
            (image, property_id, buyer_id, seller_id, uploaded_by, document_type)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING document_id
        """,
            (
                data["image"],
                data["property_id"],
                data["buyer_id"],
                data["seller_id"],
                data["uploaded_by"],
                data["document_type"],
            ),
        )
        document_id = cur.fetchone()[0]
        conn.commit()
        return (
            jsonify(
                {"message": "Document added successfully", "document_id": document_id}
            ),
            201,
        )
    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@app.route("/documents/query", methods=["GET"])
def query_documents():
    # Get query parameters
    uploaded_by = request.args.get("uploaded_by")
    property_id = request.args.get("property_id")
    buyer_id = request.args.get("buyer_id")
    seller_id = request.args.get("seller_id")

    # Build query conditions
    conditions = []
    params = []

    if uploaded_by:
        conditions.append("uploaded_by = %s")
        params.append(uploaded_by)
    if property_id:
        conditions.append("property_id = %s")
        params.append(property_id)
    if buyer_id:
        conditions.append("buyer_id = %s")
        params.append(buyer_id)
    if seller_id:
        conditions.append("seller_id = %s")
        params.append(seller_id)

    # Construct the WHERE clause
    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = f"""
            SELECT document_id, image, datetime_uploaded, 
                   property_id, buyer_id, seller_id, 
                   uploaded_by, document_type
            FROM documents
            WHERE {where_clause}
            ORDER BY datetime_uploaded DESC
        """
        cur.execute(query, params)
        documents = cur.fetchall()

        # Convert datetime objects to string for JSON serialization
        for doc in documents:
            doc["datetime_uploaded"] = doc["datetime_uploaded"].isoformat()

        return jsonify({"count": len(documents), "documents": documents})
    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
