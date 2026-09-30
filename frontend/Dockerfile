# Used by docker-compose for local development only -- runs the Vite dev
# server, not a production build. Vercel's hosted deployment does NOT use
# this file -- it runs `npm run build` natively from the repo (see README
# "Deployment").
FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
