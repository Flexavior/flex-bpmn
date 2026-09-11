FROM node:22-alpine AS build
WORKDIR /web
ARG VITE_API_BASE=http://localhost:9090
ENV VITE_API_BASE=$VITE_API_BASE
COPY frontend/package.json frontend/package-lock.json* /web/
RUN npm install
COPY frontend /web
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
