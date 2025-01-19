#!/bin/bash
docker container ps
docker images
docker container stop c-mochi-bot-discord
docker container rm c-mochi-bot-discord
docker rmi $(docker images -q)
docker container ps
docker images
./start_docker_container.sh

