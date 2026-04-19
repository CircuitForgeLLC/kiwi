FROM continuumio/miniconda3:latest

WORKDIR /app

# Install system dependencies for OpenCV + pyzbar
RUN apt-get update && apt-get install -y --no-install-recommends \
    libzbar0 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install circuitforge-core from sibling directory (compose sets context: ..)
COPY circuitforge-core/ ./circuitforge-core/
RUN conda run -n base pip install --no-cache-dir -e ./circuitforge-core

# Install circuitforge-orch — needed for the cf-orch-agent sidecar (compose.override.yml)
COPY circuitforge-orch/ ./circuitforge-orch/

# Create kiwi conda env and install app
COPY kiwi/environment.yml .
RUN conda env create -f environment.yml

COPY kiwi/ ./kiwi/

# Remove gitignored config files that may exist locally — defense-in-depth.
# The parent .dockerignore should exclude these, but an explicit rm guarantees
# they never end up in the cloud image regardless of .dockerignore placement.
RUN rm -f /app/kiwi/.env

# Install cf-core and cf-orch into the kiwi env BEFORE installing kiwi
RUN conda run -n kiwi pip install --no-cache-dir -e /app/circuitforge-core
RUN conda run -n kiwi pip install --no-cache-dir -e /app/circuitforge-orch
WORKDIR /app/kiwi
RUN conda run -n kiwi pip install --no-cache-dir -e .

EXPOSE 8512
CMD ["conda", "run", "--no-capture-output", "-n", "kiwi", \
     "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8512"]
