FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci

# Development stage
FROM base AS development
ENV NODE_ENV=development
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# Build stage
FROM base AS builder
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
