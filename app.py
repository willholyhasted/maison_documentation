# app.py
from flask import Flask, request, jsonify, render_template
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Database connection parameters
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        sslmode="require",  # Add this for Azure PostgreSQL
    )


# Create the table if it doesn't exist
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            document_id SERIAL PRIMARY KEY,
            filename VARCHAR(250) NOT NULL,
            file_type VARCHAR(50) NOT NULL,
            image BYTEA NOT NULL,  
            datetime_uploaded TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            property_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            uploaded_by VARCHAR(50) CHECK (uploaded_by IN ('buyer', 'seller')),
            document_tag VARCHAR(50) NOT NULL
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
    print("Received request")
    print(f"Files: {request.files}")
    print(f"Form data: {request.form}")

    if "file" not in request.files:
        print("No file in request")
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        print("Empty filename")
        return jsonify({"error": "No file selected"}), 400

    # Get content type or default to octet-stream
    file_type = file.content_type or "application/octet-stream"
    if file_type == "None":  # Handle string 'None'
        file_type = "application/octet-stream"

    # Get form data
    data = request.form
    required_fields = [
        "property_id",
        "buyer_id",
        "seller_id",
        "uploaded_by",
        "document_tag",
    ]

    # Check which fields are missing
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        print(f"Missing fields: {missing_fields}")
        return jsonify({"error": f"Missing required fields: {missing_fields}"}), 400

    if data["uploaded_by"] not in ["buyer", "seller", ""]:
        print(f"Invalid uploaded_by value: {data['uploaded_by']}")
        return (
            jsonify(
                {"error": "uploaded_by must be either 'buyer' or 'seller' or empty"}
            ),
            400,
        )

    # Read file binary data
    file_data = file.read()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO documents 
            (filename, file_type, image, property_id, buyer_id, seller_id, uploaded_by, document_tag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING document_id
            """,
            (
                file.filename,
                file_type,
                psycopg2.Binary(file_data),  # Convert to binary
                data["property_id"],
                data["buyer_id"],
                data["seller_id"],
                data["uploaded_by"],
                data["document_tag"],
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
    document_tag = request.args.get("document_tag")

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
    if document_tag:
        conditions.append("document_tag = %s")
        params.append(document_tag)

    # Construct the WHERE clause
    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = f"""
            SELECT document_id, filename, file_type, 
                   encode(image, 'base64') as image_data,
                   datetime_uploaded, 
                   property_id, buyer_id, seller_id, 
                   uploaded_by, document_tag
            FROM documents
            WHERE {where_clause}
            ORDER BY datetime_uploaded DESC
        """
        cur.execute(query, params)
        documents = cur.fetchall()

        # Convert datetime objects to string for JSON serialization
        for doc in documents:
            doc["datetime_uploaded"] = doc["datetime_uploaded"].isoformat()
            # Add content type for frontend handling
            doc["image_url"] = f"data:{doc['file_type']};base64,{doc['image_data']}"
            del doc["image_data"]  # Remove raw base64 data from response

        return jsonify({"count": len(documents), "documents": documents})
    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@app.route("/")
def route():
    return render_template("api_documentation.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
