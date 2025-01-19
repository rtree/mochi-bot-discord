# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.10-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies.
RUN pip install discord.py requests python-dotenv asyncio openai beautifulsoup4 lxml PyPDF2 pycryptodome

# Run the web service on container startup. Here we use the basic
# web server provided by Python. You should adjust the command to run
# your Discord bot script.

CMD ["python", "main.py"]
