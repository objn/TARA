BEGIN;

INSERT INTO public.app_meta(key, value)
VALUES
  ('seeded_at', now()::text)
ON CONFLICT (key) DO UPDATE
SET value = EXCLUDED.value,
    updated_at = now();

INSERT INTO public.events(kind, payload)
VALUES
  ('system.start', jsonb_build_object('message', 'seed data inserted'))
ON CONFLICT DO NOTHING;

COMMIT;

