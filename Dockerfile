FROM oven/bun:1-slim AS base
WORKDIR /usr/src/app

# Fonts
RUN apt-get update && apt-get install -y \
    fontconfig \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Python
RUN apt update && apt install python3 python3-pip make g++ -y

# install dependencies into temp directory
# this will cache them and speed up future builds
FROM base AS install
RUN mkdir -p /temp/dev
COPY package.json bun.lock /temp/dev/
RUN cd /temp/dev && bun install --frozen-lockfile

# install with --production (exclude devDependencies)
RUN mkdir -p /temp/prod
COPY package.json bun.lock /temp/prod/
RUN cd /temp/prod && bun install --frozen-lockfile --production

# copy production dependencies and source code into final image
FROM base AS release
COPY --from=install /temp/prod/node_modules node_modules
COPY . .

# make sure db directory exists and is owned by bun user
RUN mkdir -p /usr/src/app/db && chown bun:bun /usr/src/app/db

# run the app
USER bun
ENTRYPOINT [ "bun", "start" ]
