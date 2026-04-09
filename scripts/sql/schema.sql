BEGIN;

-- Minimal, app-agnostic schema to validate DB wiring.
-- You can replace/extend this later with your real tables/migrations.

CREATE TABLE IF NOT EXISTS public.app_meta (
  key text PRIMARY KEY,
  value text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.events (
  id bigserial PRIMARY KEY,
  kind text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_events_kind_created_at ON public.events (kind, created_at DESC);

-- Chat (topics + messages)
CREATE TABLE IF NOT EXISTS public.chat_topics (
  id uuid PRIMARY KEY,
  title text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.chat_messages (
  id uuid PRIMARY KEY,
  topic_id uuid NOT NULL REFERENCES public.chat_topics(id) ON DELETE CASCADE,
  role text NOT NULL,
  content text NOT NULL,
  agent text NULL,
  meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_topic_created_at
  ON public.chat_messages (topic_id, created_at ASC);

COMMIT;

