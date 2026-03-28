FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --only=production

COPY src/ ./src/
COPY init.sql ./

EXPOSE 5003

CMD ["node", "src/index.js"]