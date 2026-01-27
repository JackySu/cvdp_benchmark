FROM ubuntu:24.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    make \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for mi6
RUN pip3 install openai pydantic --break-system-packages

# Create directories
RUN mkdir -p /opt/mi6/bin /code/src

# Copy mi6 binary (will be copied during build)
COPY bin/mi6 /opt/mi6/bin/mi6
RUN chmod +x /opt/mi6/bin/mi6

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables (can be overridden at runtime)
ENV MI6_BASE_URL="https://api.deepseek.com/"
ENV MI6_MODEL="deepseek:deepseek-reasoner"
ENV MI6_API_KEY=""
ENV MI6_TIMEOUT="1200"

WORKDIR /code
RUN chmod -R 777 /code

ENTRYPOINT ["/entrypoint.sh"]
