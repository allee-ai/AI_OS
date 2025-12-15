# Frontend Dockerfile - React with Vite
FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend code
COPY frontend/ .

# Expose Vite dev server port
EXPOSE 5173

# Run Vite dev server (use --host to expose to Docker network)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
