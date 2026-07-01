#!/usr/bin/env bash

echo "building trade-writer image..."
docker build --file Containerfile \
    --platform linux/amd64,linux/arm64 \
    --build-arg BIN_NAME=trade-writer \
    --tag ghcr.io/sm26-industrial-software-dev/trade-writer:dev \
    --push .

echo "building db-syncer image..."
docker build --file Containerfile \
    --platform linux/amd64,linux/arm64 \
    --build-arg BIN_NAME=db-syncer \
    --tag ghcr.io/sm26-industrial-software-dev/db-syncer:dev \
    --push .

echo "building price-cacher image..."
docker build --file Containerfile \
    --platform linux/amd64,linux/arm64 \
    --build-arg BIN_NAME=price-cacher \
    --tag ghcr.io/sm26-industrial-software-dev/price-cacher:dev \
    --push .
