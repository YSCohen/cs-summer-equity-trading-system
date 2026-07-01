#!/usr/bin/env nu

def main [...rest] {
    if ($rest | is-empty) {
        build trade-writer
        build db-syncer
        build price-cacher
    } else {
        $rest | each {build $in} | ignore
    }
}

def build [$name: string] {
    print $"building ($name) image..."

    (
        docker build --file Containerfile
        --platform linux/amd64,linux/arm64
        --build-arg BIN_NAME=($name)
        --tag ghcr.io/sm26-industrial-software-dev/($name):dev
        --push
        .
    )
}
