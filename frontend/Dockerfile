FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_GITHUB_USER=your-username
ARG VITE_GITHUB_REPO=your-repo
ARG VITE_GITHUB_BRANCH=main

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_GITHUB_USER=$VITE_GITHUB_USER
ENV VITE_GITHUB_REPO=$VITE_GITHUB_REPO
ENV VITE_GITHUB_BRANCH=$VITE_GITHUB_BRANCH

RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
