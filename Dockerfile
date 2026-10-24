FROM python:3.11-slim

RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
       gcc libffi-dev musl-dev ffmpeg aria2 python3-pip curl wget tar unzip ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Automatically download & install N_m3u8DL-RE Linux binary on Render
RUN wget -qO /tmp/n_m3u8.tar.gz "https://github.com/nilaoda/N_m3u8DL-RE/releases/download/v0.6.0-beta/N_m3u8DL-RE_v0.6.0-beta_linux-x64_20260629.tar.gz" \
    && tar -xzf /tmp/n_m3u8.tar.gz -C /tmp/ \
    && mv /tmp/N_m3u8DL-RE /usr/local/bin/N_m3u8DL-RE \
    && chmod +x /usr/local/bin/N_m3u8DL-RE \
    && rm -rf /tmp/n_m3u8*

# Automatically download & install Bento4 mp4decrypt Linux binary
RUN wget -qO /tmp/bento4.zip "https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-641.x86_64-unknown-linux.zip" \
    && unzip -q /tmp/bento4.zip -d /tmp/bento4_tmp \
    && mv /tmp/bento4_tmp/Bento4-SDK-1-6-0-641.x86_64-unknown-linux/bin/mp4decrypt /usr/local/bin/mp4decrypt \
    && chmod +x /usr/local/bin/mp4decrypt \
    && rm -rf /tmp/bento4*

COPY . /app/
WORKDIR /app/

RUN pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir --upgrade -r requirements.txt \
    && python3 -m pip install -U yt-dlp

CMD ["python3", "modules/main.py"]
