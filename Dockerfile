FROM python:3.11-slim-bookworm

# 1. Derleme araçlarını kur
RUN apt-get update && apt-get install -y \
    build-essential \
    swig \
    libasound2-dev \
    libssl-dev \
    wget \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. PJSIP Source derle
WORKDIR /usr/src
RUN wget https://github.com/pjsip/pjproject/archive/refs/tags/2.14.tar.gz && \
    tar -xzf 2.14.tar.gz && cd pjproject-2.14 && \
    ./configure --enable-shared --disable-sound --disable-video --disable-opencore-amr && \
    make dep && make && make install && \
    ldconfig && \
    cd pjsip-apps/src/swig/python && \
    make && \
    python setup.py install

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Shared library yolunu belirt
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
