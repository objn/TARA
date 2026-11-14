# How to Run Tara Frontend

## Normal Run (Production)

This runs the production build in Docker with Nginx.

From the `stack` directory:

```sh
docker compose up --build -d frontend
```

Open <http://localhost:4200>.

To stop the frontend:

```sh
docker compose stop frontend
```

## Development Run (Testing)

Run Angular's development server locally with live reload.

1. Install Node.js 22.13+ and enable Corepack (`corepack enable`).
2. From the `tara-frontend` directory, install dependencies:

   ```sh
   pnpm install
   ```

3. Start the dev server:

   ```sh
   pnpm start
   ```

4. Open <http://localhost:4200>. Changes under `src/` reload in the browser.

Stop the server with `Ctrl+C`.
