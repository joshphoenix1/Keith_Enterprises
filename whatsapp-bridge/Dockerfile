FROM node:20-alpine
RUN apk add --no-cache git
WORKDIR /app
COPY package.json ./
RUN npm install --production
COPY index.js ./
RUN mkdir -p auth_state media
VOLUME ["/app/auth_state", "/app/media"]
EXPOSE 8085
CMD ["node", "index.js"]
