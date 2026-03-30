FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --only=production

COPY src/ ./src/

EXPOSE 5008

CMD ["node", "src/index.js"]