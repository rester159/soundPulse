FROM node:22-bookworm

# Xvfb for headful Chrome rendering on a headless server (BlackTip
# uses a real visible Chrome to defeat automation detection)
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Clone BlackTip from GitHub and build — same pattern as tunebat-crawler
RUN git clone --depth 1 https://github.com/rester159/blacktip.git /opt/blacktip \
    && cd /opt/blacktip \
    && npm ci --ignore-scripts \
    && npm run build

# Install Playwright browsers (Chromium + deps). Lives under /opt/blacktip
# so the BlackTip library picks it up transparently.
RUN cd /opt/blacktip && npx playwright install chromium --with-deps

# Set up the worker app
WORKDIR /app
COPY package.json /app/
RUN npm install

COPY worker.mjs /app/
COPY portals /app/portals
COPY start.sh /app/
RUN chmod +x /app/start.sh

ENV DISPLAY=:99
ENV NODE_ENV=production

CMD ["/app/start.sh"]
