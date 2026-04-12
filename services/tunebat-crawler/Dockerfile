FROM node:22-bookworm

# Xvfb for headful Chrome rendering on a headless server
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Clone BlackTip from GitHub and build
RUN git clone --depth 1 https://github.com/rester159/blacktip.git /opt/blacktip \
    && cd /opt/blacktip \
    && npm ci --ignore-scripts \
    && npm run build

# Install Playwright browsers (Chromium + deps)
RUN cd /opt/blacktip && npx playwright install chromium --with-deps

# Set up the crawler app
WORKDIR /app
COPY package.json /app/
RUN npm install

# Copy crawler script
COPY crawler.mjs /app/

# Entrypoint: start Xvfb then run the crawler
COPY start.sh /app/
RUN chmod +x /app/start.sh

ENV DISPLAY=:99
ENV NODE_ENV=production

CMD ["/app/start.sh"]
