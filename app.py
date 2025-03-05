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
            property_id VARCHAR(50) NOT NULL,
            buyer_id VARCHAR(50),
            seller_id VARCHAR(50),
            uploaded_by VARCHAR(50) CHECK (uploaded_by IN ('buyer', 'seller')),
            document_tag VARCHAR(50) NOT NULL
        )
    """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents_buyer (
            document_id SERIAL PRIMARY KEY,
            filename VARCHAR(250) NOT NULL,
            file_type VARCHAR(50) NOT NULL,
            image BYTEA NOT NULL,  
            datetime_uploaded TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            buyer_id VARCHAR(50),
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


@app.route("/")
def route():
    return render_template("api_documentation.html")


"""
This function adds a document to the main documents table
It requires the following parameters/files:
- file: The document to add
- property_id: The ID of the property
- uploaded_by: The user who is uploading the document
- document_tag: The tag of the document

It returns the following:
- A message indicating that the document was added successfully
- The ID of the document in the table
"""


@app.route("/documents", methods=["POST"])
def add_document():
    print("Received request")
    print(f"Files: {request.files}")
    print(f"Form data: {request.form}")

    files = request.files
    data = request.form

    result, response = check_mandatory_paramters(files, data)
    if not result:
        return response

    file = files.get("file")
    file_type = file.content_type
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
                data.get("buyer_id"),
                data.get("seller_id"),
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


"""
This function adds a document to the buyer documents table.

This is a table that is used for generic documents for buyers not associated with a property.

It requires the following parameters/files:
- file: The document to add
- buyer_id: The ID of the buyer
- document_tag: The tag of the document

It returns the following:
- A message indicating that the document was added successfully
- The ID of the document in the table
"""


@app.route("/documents/buyer", methods=["POST"])
def add_document_buyer():
    print("Received request")
    print(f"Files: {request.files}")
    print(f"Form data: {request.form}")

    files = request.files
    data = request.form

    result, response = check_mandatory_paramters(files, data, buyer=True)
    if not result:
        return response

    file = files.get("file")
    file_type = file.content_type
    file_data = file.read()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO documents_buyer 
            (filename, file_type, image, buyer_id, document_tag)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING document_id
            """,
            (
                file.filename,
                file_type,
                psycopg2.Binary(file_data),  # Convert to binary
                data.get("buyer_id"),
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


def check_mandatory_paramters(files, data, buyer=False):
    if "file" not in files:
        print("No file in request")
        return False, (jsonify({"error": "No file provided"}), 400)

    file = files["file"]
    if file.filename == "":
        print("Empty filename")
        return False, (jsonify({"error": "No file selected"}), 400)

    # Get content type or default to octet-stream
    file_type = file.content_type or "application/octet-stream"
    if file_type == "None":  # Handle string 'None'
        file_type = "application/octet-stream"

    if not buyer:
        required_fields = [
            "property_id",
            "uploaded_by",
            "document_tag",
        ]
    else:
        required_fields = [
            "buyer_id",
            "document_tag",
        ]

    # Check that all the required fields are present
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        print(f"Missing fields: {missing_fields}")
        return False, (
            jsonify({"error": f"Missing required fields: {missing_fields}"}),
            400,
        )

    if not buyer:
        # Check that the uploaded_by field is either 'buyer', 'seller'
        if data["uploaded_by"] not in ["buyer", "seller"]:
            print(f"Invalid uploaded_by value: {data['uploaded_by']}")
            return False, (
                jsonify({"error": "uploaded_by must be either 'buyer' or 'seller'"}),
                400,
            )

        # Check that the buyer_id or seller_id field is present depending on the uploaded_by field
        if data["uploaded_by"] == "buyer":
            if "buyer_id" not in data:
                return False, (
                    jsonify(
                        {"error": "buyer_id is required when uploaded_by is 'buyer'"}
                    ),
                    400,
                )
        elif data["uploaded_by"] == "seller":
            if "seller_id" not in data:
                return False, (
                    jsonify(
                        {"error": "seller_id is required when uploaded_by is 'seller'"}
                    ),
                    400,
                )

    return True, None


"""
This function queries the main documents table.

It takes the following parameters:
- uploaded_by: buyer/seller (optional)
- property_id: The ID of the property (optional)
- buyer_id: The ID of the buyer (optional)
- seller_id: The ID of the seller (optional)
- document_tag: The tag of the document (optional)

It returns the following:
- A list of documents
- The number of documents in the list
"""


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


"""
This function queries the buyer documents table.

It takes the following parameters:
- buyer_id: The ID of the buyer (required)
- document_tag: The tag of the document (optional)

It returns the following:
- A list of documents
- The number of documents in the list
"""


@app.route("/documents/query/buyer", methods=["GET"])
def query_documents_buyer():
    # Get query parameters
    buyer_id = request.args.get("buyer_id", None)
    document_tag = request.args.get("document_tag", None)

    # Build query conditions
    conditions = []
    params = []

    if not buyer_id:
        return jsonify({"error": "buyer_id is required"}), 400

    conditions.append("buyer_id = %s")
    params.append(buyer_id)

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
                   buyer_id, document_tag
            FROM documents_buyer
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
