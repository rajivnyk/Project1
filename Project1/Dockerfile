# Base image
FROM python:3.12

# Set the working directory inside the container
WORKDIR /app

# Copy only the requirements first (this caches the pip install step)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project files into the container
COPY . .

# Expose port 3000 (Flask's port)
EXPOSE 3000

# Command to run the application
CMD ["python", "app.py"]