FROM python:alpine

EXPOSE 5000

WORKDIR app

COPY * /app/

RUN pip install -r requirements.txt
# Add the script to the Docker Image
ADD subscribe.py /subscribe.py

# Give execution rights on the cron scripts
RUN chmod 0644 /subscribe.py

#Install Cron
RUN apt-get update
RUN apt-get -y install cron

# Add the cron job
RUN crontab -l | { cat; echo "0 0 * * * python subscribe.py"; } | crontab -

# Run the command on container startup
CMD cron
CMD flask run