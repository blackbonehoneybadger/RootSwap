# ---- build stage ----
FROM node:22-alpine AS build

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_BOT_USERNAME=RootSwapBot
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_BOT_USERNAME=${VITE_BOT_USERNAME}

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- serve stage ----
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
