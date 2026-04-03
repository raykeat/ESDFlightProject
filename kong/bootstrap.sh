#!/bin/sh
set -eu

ADMIN_URL="${KONG_ADMIN_URL:-http://kong:8001}"

wait_for_kong() {
  echo "Waiting for Kong Admin API..."
  until curl -fsS "$ADMIN_URL/status" >/dev/null 2>&1; do
    sleep 2
  done
  echo "Kong Admin API is ready."
}

upsert_service() {
  name="$1"
  url="$2"
  curl -fsS -X PUT "$ADMIN_URL/services/$name" \
    --data "name=$name" \
    --data "url=$url" >/dev/null
}

upsert_route() {
  service_name="$1"
  route_name="$2"
  path="$3"
  strip_path="${4:-true}"

  curl -fsS -X PUT "$ADMIN_URL/services/$service_name/routes/$route_name" \
    --data "name=$route_name" \
    --data "paths[]=$path" \
    --data "strip_path=$strip_path" >/dev/null
}

ensure_service_rate_limit() {
  service_name="$1"
  minute_limit="$2"

  existing_id="$(curl -fsS "$ADMIN_URL/services/$service_name/plugins" | tr ',' '\n' | grep '"name":"rate-limiting"' | head -n 1 | sed -n 's/.*"id":"\([^"]*\)".*/\1/p' || true)"

  if [ -n "$existing_id" ]; then
    curl -fsS -X PATCH "$ADMIN_URL/plugins/$existing_id" \
      --data "config.minute=$minute_limit" \
      --data "config.policy=local" \
      --data "config.limit_by=ip" >/dev/null
  else
    curl -fsS -X POST "$ADMIN_URL/services/$service_name/plugins" \
      --data "name=rate-limiting" \
      --data "config.minute=$minute_limit" \
      --data "config.policy=local" \
      --data "config.limit_by=ip" >/dev/null
  fi
}

ensure_global_cors() {
  existing_id="$(curl -fsS "$ADMIN_URL/plugins" | tr ',' '\n' | grep '"name":"cors"' | head -n 1 | sed -n 's/.*"id":"\([^"]*\)".*/\1/p' || true)"

  if [ -n "$existing_id" ]; then
    curl -fsS -X PATCH "$ADMIN_URL/plugins/$existing_id" \
      --data "config.origins[]=http://localhost:5173" \
      --data "config.origins[]=http://localhost:5174" \
      --data "config.methods[]=GET" \
      --data "config.methods[]=POST" \
      --data "config.methods[]=PUT" \
      --data "config.methods[]=PATCH" \
      --data "config.methods[]=DELETE" \
      --data "config.methods[]=OPTIONS" \
      --data "config.headers[]=Accept" \
      --data "config.headers[]=Authorization" \
      --data "config.headers[]=Content-Type" \
      --data "config.headers[]=Origin" \
      --data "config.headers[]=X-Requested-With" \
      --data "config.exposed_headers[]=Content-Length" \
      --data "config.exposed_headers[]=Content-Type" \
      --data "config.credentials=true" \
      --data "config.max_age=3600" >/dev/null
  else
    curl -fsS -X POST "$ADMIN_URL/plugins" \
      --data "name=cors" \
      --data "config.origins[]=http://localhost:5173" \
      --data "config.origins[]=http://localhost:5174" \
      --data "config.methods[]=GET" \
      --data "config.methods[]=POST" \
      --data "config.methods[]=PUT" \
      --data "config.methods[]=PATCH" \
      --data "config.methods[]=DELETE" \
      --data "config.methods[]=OPTIONS" \
      --data "config.headers[]=Accept" \
      --data "config.headers[]=Authorization" \
      --data "config.headers[]=Content-Type" \
      --data "config.headers[]=Origin" \
      --data "config.headers[]=X-Requested-With" \
      --data "config.exposed_headers[]=Content-Length" \
      --data "config.exposed_headers[]=Content-Type" \
      --data "config.credentials=true" \
      --data "config.max_age=3600" >/dev/null
  fi
}

wait_for_kong

upsert_service "booking-api" "http://booking-composite-service:3001"
upsert_route "booking-api" "booking-api-bookings" "/api/bookings" "false"
upsert_route "booking-api" "booking-api-rebooking" "/api/rebooking" "false"

upsert_service "record-api" "http://record-service:3000/records"
upsert_route "record-api" "record-api-route" "/api/records" "true"

upsert_service "flight-api-flight" "http://flight-service:3000/flight"
upsert_route "flight-api-flight" "flight-api-flight-route" "/api/flight" "true"

upsert_service "flight-api-flights" "http://flight-service:3000/flights"
upsert_route "flight-api-flights" "flight-api-flights-route" "/api/flights" "true"

upsert_service "seats-api" "http://seats-service:5003/seats"
upsert_route "seats-api" "seats-api-route" "/api/seats" "true"

upsert_service "payment-api" "http://payment-service:5000/payment"
upsert_route "payment-api" "payment-api-route" "/api/payment" "true"

upsert_service "payments-api" "http://payment-service:5000/payments"
upsert_route "payments-api" "payments-api-route" "/api/payments" "true"

upsert_service "offer-api-offer" "http://offer-service:5000/offer"
upsert_route "offer-api-offer" "offer-api-offer-route" "/api/offer" "true"

upsert_service "offer-api-offers" "http://offer-service:5000/offers"
upsert_route "offer-api-offers" "offer-api-offers-route" "/api/offers" "true"

upsert_service "flight-search-api" "http://flight-search-composite:5011/flight-search"
upsert_route "flight-search-api" "flight-search-api-route" "/api/flight-search" "true"

upsert_service "flight-cancel-api" "http://flight-cancellation-composite:5010/cancel"
upsert_route "flight-cancel-api" "flight-cancel-api-route" "/api/cancel" "true"

ensure_global_cors
ensure_service_rate_limit "flight-search-api" "30"
ensure_service_rate_limit "flight-cancel-api" "5"

echo "Kong bootstrap completed."
