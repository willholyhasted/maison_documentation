# app.py
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Database connection parameters
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')

def get_db_connection():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
    except psycopg2.Error as e:
        print(f"Unable to connect to database: {e}")
        raise Exception(f"Database connection failed: {str(e)}")

# Create the table if it doesn't exist
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS persons (
                first_name VARCHAR(100) PRIMARY KEY,
                second_name VARCHAR(100) NOT NULL
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"Database initialization failed: {e}")
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# Initialize the database when the app starts
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"Application startup failed: {e}")
        # You might want to exit the application here if DB init is critical
        # import sys
        # sys.exit(1)

@app.route('/person', methods=['POST'])
def add_person():
    data = request.get_json()
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO persons (first_name, second_name) VALUES (%s, %s)",
            (data['first_name'], data['second_name'])
        )
        conn.commit()
        return jsonify({"message": "Person added successfully"}), 201
    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

@app.route('/person/<first_name>', methods=['GET'])
def get_person(first_name):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM persons WHERE first_name = %s", (first_name,))
    person = cur.fetchone()
    cur.close()
    conn.close()
    
    if person:
        return jsonify(person)
    return jsonify({"error": "Person not found"}), 404

@app.route('/persons', methods=['GET'])
def get_all_persons():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM persons")
    persons = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(list(persons))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)