# Stage 1: The builder stage
# This stage installs all the Python dependencies.
FROM python:3.11-slim as builder

# Set the working directory
WORKDIR /app

# Install poetry for dependency management
# Using poetry is a modern best practice for managing Python dependencies
RUN pip install poetry

# Copy only the files needed to install dependencies
COPY poetry.lock pyproject.toml ./

# Install dependencies without installing the project's own code
# --no-root prevents installing the src/ package itself in this stage
RUN poetry install --no-root --no-dev


# Stage 2: The final runtime stage
# This stage creates the final, lightweight image.
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the installed virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Add the virtual environment to the system's PATH
# This allows running the installed packages directly
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application source code
COPY ./src ./src

# Expose the port that the application will run on
EXPOSE 8080

# Set the command to run the application using a production-grade server
# Gunicorn is a robust and widely used WSGI server for Python.
# We point it to the Flask app object inside src/main.py.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "src.main:app"]
