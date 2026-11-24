# Образ настольного приложения «Флористический центр» (PyQt5).
# Окно выводится через X11 хоста — см. сервис app в docker-compose.yml.
FROM python:3.12-slim

# Системные библиотеки, которые нужны Qt (платформа xcb) и шрифты с кириллицей.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libegl1 libglib2.0-0 libdbus-1-3 libfontconfig1 libfreetype6 \
        libx11-6 libx11-xcb1 libxext6 libxrender1 libxi6 libsm6 libice6 \
        libxkbcommon0 libxkbcommon-x11-0 \
        libxcb1 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
        libxcb-render0 libxcb-render-util0 libxcb-shape0 libxcb-shm0 libxcb-sync1 \
        libxcb-xfixes0 libxcb-xinerama0 libxcb-xinput0 libxcb-xkb1 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    QT_X11_NO_MITSHM=1 \
    XDG_RUNTIME_DIR=/tmp/runtime-app \
    LANG=C.UTF-8
RUN mkdir -m 700 /tmp/runtime-app

CMD ["python", "main.py"]
