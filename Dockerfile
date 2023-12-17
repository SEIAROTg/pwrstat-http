FROM docker.io/library/python:3.11-slim

ARG PPL_DEB_URL=https://dl4jz3rbrsfum.cloudfront.net/software/PPL_64bit_v1.4.1.deb

WORKDIR /app
COPY . .

RUN apt-get update
RUN apt-get install -y curl initscripts
RUN curl -SL "${PPL_DEB_URL}" -o /tmp/ppl.deb
RUN dpkg -i /tmp/ppl.deb
RUN pip3 install -r requirements.txt

RUN apt-get purge -y curl initscripts
RUN rm /tmp/ppl.deb

ENTRYPOINT ["./entrypoint.sh"]
