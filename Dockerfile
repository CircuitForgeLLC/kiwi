FROM continuumio/miniconda3:latest

WORKDIR /app

# Install system dependencies for OpenCV + pyzbar
RUN apt-get update && apt-get install -y --no-install-recommends \
    libzbar0 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install circuitforge-core from sibling directory (compose sets context: ..)
COPY circuitforge-core/ ./circuitforge-core/
RUN conda run -n base pip install --no-cache-dir -e ./circuitforge-core

# Create kiwi conda env and install app
COPY kiwi/environment.yml .
RUN conda env create -f environment.yml

COPY kiwi/ ./kiwi/
# Install cf-core into the kiwi env BEFORE installing kiwi (kiwi lists it as a dep)
RUN conda run -n kiwi pip install --no-cache-dir -e /app/circuitforge-core
WORKDIR /app/kiwi
RUN conda run -n kiwi pip install --no-cache-dir -e .

EXPOSE 8512
CMD ["conda", "run", "--no-capture-output", "-n", "kiwi", \
     "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8512"]
