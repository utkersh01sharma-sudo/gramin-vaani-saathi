# One image, three roles (web / worker / models) chosen by the compose command.
#
# torch is installed from the PyTorch index rather than requirements.txt, so
# the same Dockerfile builds a ~1 GB CPU image by default and a CUDA image when
# docker-compose.gpu.yml passes TORCH_INDEX=.../cu121.
FROM python:3.11-slim

ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/hf-cache

# libzbar0: pyzbar's QR fallback. libgl1 + libglib2.0-0: OpenCV's runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libzbar0 libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --index-url ${TORCH_INDEX} torch==2.5.1 torchvision==0.20.1 \
 && pip install -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY ml ./ml
COPY docs/samples ./docs/samples

# Never run as root inside the container.
RUN useradd --create-home app && mkdir -p /hf-cache /app/backend/media \
 && chown -R app /app /hf-cache
USER app

EXPOSE 8000 9000
CMD ["gunicorn", "--chdir", "backend", "config.wsgi:application", "-b", "0.0.0.0:8000", "-w", "2"]
