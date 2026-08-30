import {createClient} from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

export const hasSupabaseConfig = Boolean(url && publishableKey);

if (!hasSupabaseConfig && import.meta.env.VITE_PREVIEW_MODE !== "true") {
  throw new Error("FinSight authentication is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY.");
}

export const supabase = createClient(
  url || "http://127.0.0.1:54321",
  publishableKey || "preview-publishable-key",
  {auth: {persistSession: true, autoRefreshToken: true, detectSessionInUrl: true}}
);
