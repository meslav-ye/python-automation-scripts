FROM ubuntu:22.04

# Install python3
RUN DEBIAN_FRONTEND=noninteractive \
  apt update \
  && apt upgrade -y \
  && apt install apt-transport-https ca-certificates curl software-properties-common git netcat net-tools ssh jq -y \
  && curl -fsSL https://get.docker.com | CHANNEL=stable sh \
  && apt-get -y install python3-pip 

RUN apt install npm -y 
RUN npm i -g git-changelog-command-line

# Install OCI CLI
RUN curl -L -O https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh \
    && chmod 755 install.sh \
    && ./install.sh --accept-all-defaults \
    && cp /root/bin/oci /usr/bin

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install kubectl
RUN apt-get update && \
    apt-get install -y curl && \
    curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x ./kubectl && \
    mv ./kubectl /usr/local/bin/kubectl

# Run k8s_cluster_autoscaling.py when the container launches
ENTRYPOINT ["python3", "k8s_cluster_autoscaling.py"]
