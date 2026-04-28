FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# project root files needed by vite
COPY index.html vite.config.ts tsconfig*.json ./

# src/ is bind-mounted at runtime for hot reload
EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
