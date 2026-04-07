const express = require('express');
const amqp = require('amqplib');
const { WebSocketServer, WebSocket } = require('ws');

const PORT = Number(process.env.PORT || 5012);
const RABBITMQ_URL = process.env.RABBITMQ_URL || 'amqp://guest:guest@rabbitmq:5672';
const RABBITMQ_EXCHANGE = process.env.RABBITMQ_EXCHANGE || 'airline_events';
const SEAT_EVENTS_KEY = process.env.SEAT_EVENTS_KEY || 'seat.updated';

const app = express();
app.get('/health', (_req, res) => {
  res.json({ status: 'OK', service: 'realtime-gateway' });
});

const server = app.listen(PORT, () => {
  console.log(`Realtime gateway listening on ${PORT}`);
});

const wss = new WebSocketServer({ server, path: '/ws' });
const flightRooms = new Map();

function joinRoom(ws, flightID) {
  const room = String(flightID || '').trim();
  if (!room) return;

  if (ws.flightRoom && flightRooms.has(ws.flightRoom)) {
    flightRooms.get(ws.flightRoom).delete(ws);
  }

  ws.flightRoom = room;

  if (!flightRooms.has(room)) {
    flightRooms.set(room, new Set());
  }
  flightRooms.get(room).add(ws);
}

function leaveRoom(ws) {
  if (!ws.flightRoom) return;
  const bucket = flightRooms.get(ws.flightRoom);
  if (!bucket) return;

  bucket.delete(ws);
  if (bucket.size === 0) {
    flightRooms.delete(ws.flightRoom);
  }
}

function broadcastSeatUpdate(eventPayload) {
  const room = String(eventPayload.flightID || '').trim();
  if (!room || !flightRooms.has(room)) {
    return;
  }

  const message = JSON.stringify({ type: 'seat.update', payload: eventPayload });
  for (const client of flightRooms.get(room)) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
    }
  }
}

wss.on('connection', (ws) => {
  ws.on('message', (rawMessage) => {
    try {
      const message = JSON.parse(rawMessage.toString());
      if (message.type === 'join' && message.flightID) {
        joinRoom(ws, message.flightID);
        ws.send(JSON.stringify({ type: 'joined', flightID: String(message.flightID) }));
      }
    } catch (err) {
      ws.send(JSON.stringify({ type: 'error', message: 'Invalid websocket message payload' }));
    }
  });

  ws.on('close', () => {
    leaveRoom(ws);
  });
});

async function startRabbitConsumer() {
  while (true) {
    let connection;
    let channel;

    try {
      connection = await amqp.connect(RABBITMQ_URL);
      channel = await connection.createChannel();

      await channel.assertExchange(RABBITMQ_EXCHANGE, 'topic', { durable: true });
      const queue = await channel.assertQueue('seat_realtime_gateway_queue', { durable: true });
      await channel.bindQueue(queue.queue, RABBITMQ_EXCHANGE, SEAT_EVENTS_KEY);

      console.log('Realtime gateway connected to RabbitMQ');

      channel.consume(queue.queue, (msg) => {
        if (!msg) return;

        try {
          const payload = JSON.parse(msg.content.toString());
          broadcastSeatUpdate(payload);
          channel.ack(msg);
        } catch (err) {
          console.error('Invalid seat event payload:', err.message);
          channel.nack(msg, false, false);
        }
      });

      await new Promise((resolve) => {
        connection.on('close', resolve);
        connection.on('error', resolve);
      });
    } catch (err) {
      console.error('RabbitMQ connection failed:', err.message);
    } finally {
      try {
        if (channel) await channel.close();
      } catch (_) {
        // Ignore channel close errors during reconnect.
      }
      try {
        if (connection) await connection.close();
      } catch (_) {
        // Ignore connection close errors during reconnect.
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
}

startRabbitConsumer().catch((err) => {
  console.error('Realtime consumer crashed:', err.message);
});
