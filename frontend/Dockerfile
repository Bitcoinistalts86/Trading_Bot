# frontend/Dockerfile
# --- Build stage ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Public API URLs are baked at build time (client-side fetch needs browser-reachable URLs)
ARG NEXT_PUBLIC_AUTH_URL=http://localhost:8000
ARG NEXT_PUBLIC_EXEC_URL=http://localhost:8080
ENV NEXT_PUBLIC_AUTH_URL=${NEXT_PUBLIC_AUTH_URL}
ENV NEXT_PUBLIC_EXEC_URL=${NEXT_PUBLIC_EXEC_URL}
RUN npm run build

# --- Production stage ---
FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["npm", "start"]
