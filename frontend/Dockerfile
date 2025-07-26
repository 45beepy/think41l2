# Stage 1: Build the React application
# Use a Node.js image to build your React app
FROM node:18-alpine AS build

WORKDIR /app

# Copy package.json and yarn.lock (or package-lock.json) to install dependencies
# This caches dependencies, so if these files don't change, Docker can use the cache
COPY package.json ./
COPY yarn.lock ./ 

# Install dependencies. --frozen-lockfile for yarn to ensure reproducible builds.
# Use 'npm ci' if you are using npm and package-lock.json.
RUN yarn install --frozen-lockfile

# Copy the rest of the application code
COPY . .

# Build the React application for production
# This command creates the 'build' folder with optimized static assets
RUN yarn build # Or 'npm run build' if you used npm

# Stage 2: Serve the React application with Nginx
# Use a lightweight Nginx image
FROM nginx:stable-alpine

# Copy the Nginx configuration file
# This file tells Nginx how to serve the React app and proxy API requests
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built React app from the 'build' stage to Nginx's serving directory
COPY --from=build /app/build /usr/share/nginx/html

# Expose port 80 (standard HTTP port for web servers)
EXPOSE 80

# Command to start Nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]