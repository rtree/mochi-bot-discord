#!/bin/bash

# Infinite loop to run 'docker container ls' every 10 seconds
clear
while true; do
  # Print the current date and time for reference
  echo "Checking running containers at $(date)"
  
  # Run the docker container listing command
  docker container ls
  
  # Wait for 10 seconds before the next iteration
  sleep 10
  
  # Clear the screen for readability, comment this line if you want to keep the history visible
  # clear
done
