FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (SSH for tunnel, though we should avoid it in prod)
# We also need libmagic for some libraries if needed
RUN apt-get update && apt-get install -y \
    ssh \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create directory for SQLite database persistence
RUN mkdir -p /app/data

# Make sure the assets directory exists for uploads
RUN mkdir -p /app/assets

# Expose the dashboard port (Standard 8080)
EXPOSE 8080

# Set environment variables for production
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Create a non-root user (User 1000 required for HF)
RUN useradd -m -u 1000 user
# Give the user permission to the data and assets folders
RUN chown -R user:user /app
USER user

# Set DB_PATH to use the persistent volume
ENV DB_PATH=/app/data/bot_database.sqlite

# Start the application
CMD ["python", "main.py"]
