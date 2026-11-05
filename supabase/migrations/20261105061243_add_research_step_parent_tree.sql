ALTER TABLE public.research_steps
  ADD COLUMN IF NOT EXISTS parent_step_id uuid NULL;

ALTER TABLE public.research_steps
  ADD CONSTRAINT research_steps_id_session_unique UNIQUE (id, session_id);

ALTER TABLE public.research_steps
  ADD CONSTRAINT research_steps_parent_same_session_fkey
  FOREIGN KEY (parent_step_id, session_id)
  REFERENCES public.research_steps (id, session_id)
  ON DELETE SET NULL (parent_step_id);

ALTER TABLE public.research_steps
  ADD CONSTRAINT research_steps_no_self_parent
  CHECK (parent_step_id IS DISTINCT FROM id);

CREATE INDEX IF NOT EXISTS research_steps_parent_order_idx
  ON public.research_steps (session_id, parent_step_id, sequence_no);

WITH ordered AS (
  SELECT id,
         lag(id) OVER (PARTITION BY session_id ORDER BY sequence_no, created_at, id) AS previous_id
  FROM public.research_steps
)
UPDATE public.research_steps AS target
SET parent_step_id = ordered.previous_id
FROM ordered
WHERE target.id = ordered.id
  AND target.parent_step_id IS NULL
  AND ordered.previous_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.prevent_research_step_cycle()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
DECLARE
  creates_cycle boolean;
BEGIN
  IF NEW.parent_step_id IS NULL THEN
    RETURN NEW;
  END IF;

  WITH RECURSIVE parent_chain(id) AS (
    SELECT NEW.parent_step_id
    UNION
    SELECT step.parent_step_id
    FROM public.research_steps AS step
    JOIN parent_chain AS chain ON step.id = chain.id
    WHERE step.parent_step_id IS NOT NULL
  )
  SELECT EXISTS (
    SELECT 1 FROM parent_chain WHERE id = NEW.id
  ) INTO creates_cycle;

  IF creates_cycle THEN
    RAISE EXCEPTION 'A research step cannot be attached beneath one of its descendants';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS research_steps_prevent_cycle ON public.research_steps;
CREATE TRIGGER research_steps_prevent_cycle
BEFORE INSERT OR UPDATE OF parent_step_id
ON public.research_steps
FOR EACH ROW
EXECUTE FUNCTION public.prevent_research_step_cycle();
