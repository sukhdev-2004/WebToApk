FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV ANDROID_HOME=/opt/android-sdk

ENV PATH=$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/build-tools/37.0.0:$PATH

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    openjdk-17-jdk \
    python3 \
    python3-pip \
    wget \
    unzip \
    git \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Android SDK
RUN mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools && \
    cd /tmp && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip && \
    unzip -q commandlinetools-linux-13114758_latest.zip && \
    mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools/latest && \
    mv cmdline-tools/* ${ANDROID_SDK_ROOT}/cmdline-tools/latest/ && \
    rm -rf /tmp/*

# Accept Android licenses and install required SDK components
RUN yes | sdkmanager --licenses > /dev/null || true && \
    sdkmanager \
    "platform-tools" \
    "platforms;android-36" \
    "build-tools;37.0.0"

# Create application directory
WORKDIR /app

# Copy Python requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

# Make Gradle wrapper executable
RUN chmod +x android_template/gradlew

# Render provides PORT
EXPOSE 10000

# Start FastAPI
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]