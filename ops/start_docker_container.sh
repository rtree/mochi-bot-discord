#!/bin/bash

# Name of the Docker container
CONTAINER_NAME="c-mochi-bot-discord"
FOLDER="/home/ubuntu/operations/mochi-bot-discord/"
ENVFILE="/home/ubuntu/operations/mochi-bot-discord/.env"

# Check if the container is already running
if [ $(docker ps -q -f name=^/${CONTAINER_NAME}$) ]; then
    echo "Container ${CONTAINER_NAME} is already running."
# Check if the container exists but is not running
elif [ $(docker ps -aq -f status=exited -f name=^/${CONTAINER_NAME}$) ]; then
    echo "Container ${CONTAINER_NAME} exists but stopped. Starting container..."
    docker start ${CONTAINER_NAME}
# If the container does not exist, run it
else
    echo "Container ${CONTAINER_NAME} does not exist. Running container..."
    cd ${FOLDER}
    
    # .envからLOG_DIRを読み取り
    LOG_DIR=$(grep -E '^LOG_DIR=' ${ENVFILE} | cut -d '=' -f2)
    if [ -n "${LOG_DIR}" ]; then
        mkdir -p ${LOG_DIR}
        VOLUME_OPT="-v ${LOG_DIR}:${LOG_DIR}"
    else
        VOLUME_OPT=""
    fi
    
    docker build -t mochi-bot-discord .
    docker run -d --env-file=${ENVFILE} ${VOLUME_OPT} --name ${CONTAINER_NAME} mochi-bot-discord
fi
docker update --restart unless-stopped $(docker ps -q)
