# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory in container
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create templates directory
RUN mkdir -p templates

# Copy the templates directory
COPY templates/ /app/templates/

# Copy the rest of the application
COPY . .

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PORT=5001

# Expose the port the app runs on
EXPOSE 5001

# Command to run the application
CMD ["python", "app.py"] 