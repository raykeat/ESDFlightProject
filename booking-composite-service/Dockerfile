FROM node:18-alpine

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm install --only=production

# Copy source code
COPY src/ ./src/

# Expose port
EXPOSE 3001

# Start the app
CMD ["node", "src/index.js"]