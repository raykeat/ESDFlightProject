I created a main docker-compose.yml file that we can use to start all our microservices. 
Just create a folder for your own microservice, add whatever code and dependencies is necessary and package it into a container using a docker file. 

Can refer to the record-microservice folder for example. The record-microservice database uses an sql database pulled from docker registry, so you don't have to install or configure sql on your end (for record-microservice db at least).
Thereafter, modify the docker-compose.yml file so that your own microservice can be started too with docker compose command.

1. To start up all the microservices, run docker-compose up -d
2. To stop all the microservices, run docker-compose down
3. To stop all the microservices and delete database data locally, run docker-compose down -v

To use the frontend,
1. cd into frontend
2. npm install
3. npm run dev

Under the api documentation folder lies the YAML files of the microservices (currently includes record, payment, and coupon microservices). to view the api documents,
1. Open https://editor.swagger.io
2. Copy-paste the YAML of the microservice you want to see

FYI, this is the api document for passenger service (since its created on outsystems):
https://personal-4whagfbm.outsystemscloud.com/Passenger_Srv/rest/PassengerAPI/#/

To run the service, run from project root folder:

