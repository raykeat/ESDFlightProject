1. To start up all the microservices: docker compose up -d --build
2. To stop all the microservices: docker compose down
3. To stop all the microservices and delete database data locally, run docker-compose down -v

To use the frontend,
1. cd into frontend
2. npm install
3. npm run dev

Under the api documentation folder lies the YAML files of the microservices. to view the api documents,
1. Open https://editor.swagger.io
2. Copy-paste the YAML of the microservice you want to see

FYI, this is the api document for passenger service (since its created on outsystems):
https://personal-4whagfbm.outsystemscloud.com/Passenger_Srv/rest/PassengerAPI/#/

Accessing Services
Frontend: http://localhost:5173
Kong Dashboard: http://localhost:8002