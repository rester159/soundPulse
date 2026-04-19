FROM node:24-slim AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# Vite bakes import.meta.env.VITE_API_BASE_URL into the bundle at build
# time. The site runs in open-access mode (no API key) so this is the
# only build-arg the frontend needs. On Railway: set VITE_API_BASE_URL
# as a build-time variable.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

FROM node:24-slim
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist

EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
