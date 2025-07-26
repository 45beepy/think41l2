# Use a lightweight Python image as the base
FROM python:3.10-slim-buster

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
# We copy only requirements.txt first to leverage Docker's build cache
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the entire backend application code
# This copies everything from root/backend/backend/ to /app/backend/backend/
COPY backend/ ./backend/backend/
# Copy the .env file to the root of the app directory inside the container
# Ensure your .env is in root/backend/backend/
COPY backend/.env ./.env

# Copy the data folder and load_data.py if they are needed inside the container
# For production, you might mount these as volumes or load data separately
COPY data/ ./data/
COPY data/load_data.py ./data/load_data.py

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Expose the port FastAPI runs on
EXPOSE 8000

# Command to run the application
# Assumes main.py is inside backend/backend/
CMD ["uvicorn", "backend.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]