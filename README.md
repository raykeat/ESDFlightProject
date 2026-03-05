I created a main docker-compose.yml file that we can use to start all our microservices. 
Just create a folder for your own microservice, add whatever code and dependencies is necessary and package it into a container using a docker file. 
Can refer to the booking-microservice folder for example. The booking-microservice database uses an sql database pulled from docker registry, so you don't have to install or configure sql on your end (for booking-microservice db at least).
Thereafter, modify the docker-compose.yml file so that your own microservice can be started too with docker compose command.

1. To start up all the microservices, run docker-compose up -d
2. To stop all the microservices, run docker-compose down
3. To stop all the microservices and delete database data locally, run docker-compose down -v
