CREATE INDEX IF NOT EXISTS research_steps_parent_fk_idx
  ON public.research_steps (parent_step_id, session_id);
