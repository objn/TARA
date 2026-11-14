# Tara Frontend

Angular 20 application using Angular Three v4 for declarative Three.js scenes.

## Run with Docker Compose

From the `stack` directory:

```sh
docker compose up --build -d
```

Open the frontend at <http://localhost:4200>.

## Run locally

```sh
pnpm install
pnpm start
```

The Angular Three renderer is configured in `src/app/app.config.ts`; the starter scene is in `src/app/app.component.ts`.
