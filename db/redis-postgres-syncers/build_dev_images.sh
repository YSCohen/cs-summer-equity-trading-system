#!/usr/bin/env bash

echo "building trade-writer image..."
docker build --file Containerfile -t ghcr.io/sm26-industrial-software-dev/trade-writer:dev --build-arg BIN_NAME=trade-writer --push .

echo "building db-syncer image..."
docker build --file Containerfile -t ghcr.io/sm26-industrial-software-dev/db-syncer:dev --build-arg BIN_NAME=db-syncer --push .

echo "building price-cacher image..."
docker build --file Containerfile -t ghcr.io/sm26-industrial-software-dev/price-cacher:dev --build-arg BIN_NAME=price-cacher --push .
